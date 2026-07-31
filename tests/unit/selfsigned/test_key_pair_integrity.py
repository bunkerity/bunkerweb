"""`key_matches_certificate` — the check that stops a mismatched pair looking valid forever.

Everything else in `generate_cert`'s validity gate (`openssl x509 -checkend`, the algorithm, the
subject, the dates) is a property of the CERTIFICATE ALONE. A certificate paired with the wrong
private key therefore passed every one of them, the job logged "is valid", and nginx failed every
TLS handshake for that server until someone intervened by hand.

The pair comes apart because the job persists the two halves one after the other
(`cache_file("cert.pem")` then `cache_file("key.pem")`): a process killed between the two commits
a new certificate against the old key. At-least-once delivery makes that window reachable more
often, but a half-restored backup or a hand-edited file produces the same state.

`self-signed.py` builds a `Job` at import, which would reach for a database, so the module is
loaded with `jobs` and `logger` stubbed.
"""

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

ROOT = Path(__file__).resolve().parents[3]


JOB_PATH = ROOT / "src" / "common" / "core" / "selfsigned" / "jobs" / "self-signed.py"


def _load_job_definitions():
    """Load the job's DEFINITIONS without running it.

    A BunkerWeb job is a script, not a library: importing `self-signed.py` executes the whole
    thing and ends in `sys_exit(status)`, which aborts pytest's collection outright -- and on
    the way there it would shell out to `openssl` and write certificates into the real cache
    directory. So keep only the module-level imports, assignments and function definitions and
    discard the executable body (the `try:` block that does the work).
    """
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    jobs_module = ModuleType("jobs")
    jobs_module.Job = Mock()
    logger_module = ModuleType("logger")
    logger_module.getLogger = Mock(return_value=Mock())
    module = ModuleType("bw_self_signed")
    # `JOB = Job(LOGGER, __file__)` survives the filter (it is an Assign), and exec() supplies
    # no __file__ of its own.
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, {"jobs": jobs_module, "logger": logger_module}):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


SELF_SIGNED = _load_job_definitions()


def _make_pair(tmp_path, name="cert", key=None):
    """Write a real self-signed cert plus its key, returning (cert_object, key_path)."""
    key = key or ec.generate_private_key(ec.SECP256R1(), default_backend())
    subject = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "www.example.com")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256(), default_backend())
    )
    key_path = tmp_path / f"{name}-key.pem"
    key_path.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
    return certificate, key_path


class TestMatchingPair:
    def test_a_genuine_pair_matches(self, tmp_path):
        certificate, key_path = _make_pair(tmp_path)
        assert SELF_SIGNED.key_matches_certificate(key_path, certificate) is True

    def test_an_rsa_pair_matches_too(self, tmp_path):
        """The job supports rsa-* as well as ec-*; comparing DER SubjectPublicKeyInfo is
        algorithm-agnostic, so pin that rather than assuming EC."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        certificate, key_path = _make_pair(tmp_path, key=key)
        assert SELF_SIGNED.key_matches_certificate(key_path, certificate) is True


class TestBrokenPair:
    def test_the_certificate_of_one_pair_against_the_key_of_another_is_rejected(self, tmp_path):
        """Exactly what a kill between the two `cache_file` calls commits: a fresh certificate
        sitting next to the previous run's key. Both files are individually well-formed and the
        certificate is entirely valid, which is why no other check catches it."""
        _, old_key_path = _make_pair(tmp_path, name="old")
        new_certificate, _ = _make_pair(tmp_path, name="new")

        assert SELF_SIGNED.key_matches_certificate(old_key_path, new_certificate) is False

    def test_a_key_of_a_different_algorithm_is_rejected(self, tmp_path):
        certificate, _ = _make_pair(tmp_path, name="ec")
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        _, rsa_key_path = _make_pair(tmp_path, name="rsa", key=rsa_key)

        assert SELF_SIGNED.key_matches_certificate(rsa_key_path, certificate) is False


class TestUnreadableKey:
    """Regenerating is always the right answer here -- the material is self-signed and
    disposable -- so anything unreadable must report a mismatch rather than raise."""

    def test_a_corrupt_key_is_treated_as_a_mismatch(self, tmp_path):
        certificate, _ = _make_pair(tmp_path)
        corrupt = tmp_path / "corrupt-key.pem"
        corrupt.write_bytes(b"-----BEGIN PRIVATE KEY-----\nnot base64 at all\n-----END PRIVATE KEY-----\n")

        assert SELF_SIGNED.key_matches_certificate(corrupt, certificate) is False

    def test_a_truncated_key_is_treated_as_a_mismatch(self, tmp_path):
        certificate, key_path = _make_pair(tmp_path)
        truncated = tmp_path / "truncated-key.pem"
        truncated.write_bytes(key_path.read_bytes()[:80])

        assert SELF_SIGNED.key_matches_certificate(truncated, certificate) is False

    def test_a_missing_key_is_treated_as_a_mismatch(self, tmp_path):
        certificate, _ = _make_pair(tmp_path)
        assert SELF_SIGNED.key_matches_certificate(tmp_path / "nope.pem", certificate) is False


class TestWiredIntoTheGate:
    def test_the_validity_gate_actually_consults_the_key(self):
        """The function is only worth anything if `generate_cert` calls it. A pure-source check
        is weak, but the alternative -- driving `generate_cert` -- needs openssl, a Job cache and
        a filesystem layout, and would test the harness more than the rule."""
        source = JOB_PATH.read_text(encoding="utf-8")
        gate = source.split("def generate_cert(", 1)[1]
        assert "key_matches_certificate(key_path, certificate)" in gate
        # It must be able to REJECT: reached as a negated branch beside the other regeneration
        # reasons, not merely called and discarded.
        assert "elif not key_matches_certificate(" in gate
