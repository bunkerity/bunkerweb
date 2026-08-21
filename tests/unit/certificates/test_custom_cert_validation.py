"""`check_cert` — the gate that decides whether an operator-supplied pair reaches the fleet.

Before this fix the job ran `openssl x509 -noout -in <cert>` and nothing else: a check on the
CERTIFICATE ALONE. The private key was written to a temporary file, handed to nobody, and deleted.
So a malformed, encrypted or simply mismatched key passed the gate, was cached, was pushed to every
instance, and only failed later in Lua -- where a service that cannot load its certificate silently
falls back to the default one. The operator's first signal is a browser warning on the wrong
certificate, with nothing in any log naming the key.

The pairing check itself already exists in 1.7 and is already used by the inventory path
(`db_methods/certificates.py` -> `certificate_utils.parse_certificate`). This job was the one
caller still doing its own weaker thing.

Expiry deliberately does NOT block: refusing an expired certificate withdraws one that is currently
being served and drops the service to the default certificate, which is worse than serving expired.
That is asserted here so a later "tighten the validation" change has to argue with a test.

`custom-cert.py` builds a `Job` at import (which would reach for a database) and ends in
`sys_exit`, so the module is loaded through the AST filter used by the other job tests.
"""

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, NoEncryption, PrivateFormat

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "customcert" / "jobs" / "custom-cert.py"


def _load_job_definitions():
    """Keep the module-level imports, assignments and defs; discard the executable body."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    jobs_module = ModuleType("jobs")
    jobs_module.Job = Mock()
    logger_module = ModuleType("logger")
    logger_module.getLogger = Mock(return_value=Mock())
    module = ModuleType("bw_custom_cert")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, {"jobs": jobs_module, "logger": logger_module}):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


CUSTOM_CERT = _load_job_definitions()


@pytest.fixture
def job(monkeypatch):
    """A JOB whose cache calls succeed, so a rejection can only come from the validation."""
    monkeypatch.setattr(CUSTOM_CERT.JOB, "cache_hash", Mock(return_value=None), raising=False)
    monkeypatch.setattr(CUSTOM_CERT.JOB, "cache_file", Mock(return_value=(True, "")), raising=False)
    CUSTOM_CERT.LOGGER.reset_mock()
    return CUSTOM_CERT.JOB


def _key(kind="ec"):
    return ec.generate_private_key(ec.SECP256R1()) if kind == "ec" else rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _cert(key, *, not_before=None, not_after=None, cn="www.example.com") -> bytes:
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, cn)])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or now - timedelta(days=1))
        .not_valid_after(not_after or now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(Encoding.PEM)


def _key_pem(key, password: bytes = None) -> bytes:
    encryption = BestAvailableEncryption(password) if password else NoEncryption()
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, encryption)


def _rejects(result) -> bool:
    """`check_cert` returns (False, reason) on refusal and (bool, "") when it accepts."""
    accepted, _ = result
    return accepted is False


# ---------------------------------------------------------------------------------------------
# The defect: the key was never looked at
# ---------------------------------------------------------------------------------------------


def test_a_key_that_does_not_match_the_certificate_is_refused(job):
    """The whole point. Both halves parse; they belong to different key pairs."""
    cert = _cert(_key())
    accepted, reason = CUSTOM_CERT.check_cert(cert, _key_pem(_key()), "www.example.com")

    assert accepted is False, "a mismatched pair was accepted and would be pushed to the fleet"
    assert "match" in str(reason).lower(), reason
    job.cache_file.assert_not_called()


def test_an_encrypted_private_key_is_refused_and_says_so(job):
    """NGINX cannot use a passphrase-protected key without a passphrase file, so this can only fail."""
    key = _key()
    accepted, reason = CUSTOM_CERT.check_cert(_cert(key), _key_pem(key, b"hunter2"), "www.example.com")

    assert accepted is False
    assert "encrypted" in str(reason).lower(), reason
    job.cache_file.assert_not_called()


def test_a_malformed_private_key_is_refused(job):
    key = _key()
    accepted, reason = CUSTOM_CERT.check_cert(_cert(key), b"-----BEGIN PRIVATE KEY-----\nnot a key\n-----END PRIVATE KEY-----\n", "x")

    assert accepted is False
    assert str(reason), "a refusal with no reason tells the operator nothing"
    job.cache_file.assert_not_called()


# ---------------------------------------------------------------------------------------------
# Controls: the gate must still accept what it always accepted
# ---------------------------------------------------------------------------------------------


def test_a_valid_pair_is_accepted_and_cached(job):
    """Without this, a fix that refuses everything would pass every test above."""
    key = _key()
    accepted, reason = CUSTOM_CERT.check_cert(_cert(key), _key_pem(key), "www.example.com")

    assert accepted is True, reason
    assert reason == ""
    assert job.cache_file.call_count == 2, "cert.pem and key.pem should both be cached"


def test_an_rsa_pair_is_accepted_too(job):
    """The pairing check compares public keys, so it must not be curve-specific."""
    key = _key("rsa")
    accepted, reason = CUSTOM_CERT.check_cert(_cert(key), _key_pem(key), "www.example.com")

    assert accepted is True, reason


def test_a_malformed_certificate_is_still_refused(job):
    """Non-regression: this is the one case the old openssl subprocess did catch."""
    assert _rejects(CUSTOM_CERT.check_cert(b"-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----\n", _key_pem(_key()), "x"))
    job.cache_file.assert_not_called()


def test_a_missing_half_is_refused_before_anything_is_parsed(job):
    assert _rejects(CUSTOM_CERT.check_cert(b"", _key_pem(_key()), "x"))
    assert _rejects(CUSTOM_CERT.check_cert(_cert(_key()), b"", "x"))


# ---------------------------------------------------------------------------------------------
# Expiry warns, never blocks
# ---------------------------------------------------------------------------------------------


def test_an_expired_but_matching_pair_is_still_accepted_with_a_warning(job):
    """Withdrawing a certificate that is being served drops the service to the default one."""
    key = _key()
    now = datetime.now(timezone.utc)
    expired = _cert(key, not_before=now - timedelta(days=400), not_after=now - timedelta(days=1))

    accepted, reason = CUSTOM_CERT.check_cert(expired, _key_pem(key), "www.example.com")

    assert accepted is True, f"expiry must not block: {reason}"
    warnings = " ".join(str(call) for call in CUSTOM_CERT.LOGGER.warning.call_args_list)
    assert "expired" in warnings.lower(), f"an expired certificate was accepted silently: {warnings}"


def test_a_not_yet_valid_pair_is_accepted_with_a_warning(job):
    key = _key()
    now = datetime.now(timezone.utc)
    future = _cert(key, not_before=now + timedelta(days=2), not_after=now + timedelta(days=400))

    accepted, _ = CUSTOM_CERT.check_cert(future, _key_pem(key), "www.example.com")

    assert accepted is True
    warnings = " ".join(str(call) for call in CUSTOM_CERT.LOGGER.warning.call_args_list)
    assert "valid" in warnings.lower(), f"a not-yet-valid certificate was accepted silently: {warnings}"


# ---------------------------------------------------------------------------------------------
# Anti-drift: the job must not grow its own second validator
# ---------------------------------------------------------------------------------------------


def _code_without_comments() -> str:
    """The job's source with comment tokens removed.

    The comment explaining why the subprocess check is gone contains the word `openssl`, so a
    plain substring search cannot tell that sentence apart from the thing it forbids -- it fails
    on the fixed file and would pass on a file that deleted the explanation. `tokenize` removes
    exactly the comments and nothing else; a regex would also have to reason about strings.
    """
    import io
    import tokenize

    source = JOB_PATH.read_text(encoding="utf-8")
    tokens = [token for token in tokenize.generate_tokens(io.StringIO(source).readline) if token.type != tokenize.COMMENT]
    return tokenize.untokenize((token.type, token.string) for token in tokens)


def test_the_job_uses_the_shared_validator_and_not_a_subprocess():
    """1.7 has one certificate validator and the DB layer already routes through it.

    dev's fix for this defect (`01fe6059b`) added a second module, `certificate_validation.py`.
    1.7 already had `certificate_utils.parse_certificate`, used by `db_methods/certificates.py`
    and `customcert/api/router.py`, so the port reuses it. This test fails if either the
    subprocess check comes back or a competing validator appears.
    """
    code = _code_without_comments()

    assert "parse_certificate" in code, "the job no longer routes through the shared validator"
    assert "certificate_validation" not in code, "a second certificate validator was introduced"
    assert "openssl" not in code, "the certificate-only subprocess check came back"
    assert "NamedTemporaryFile" not in code, "the pair is being written to disk to be validated again"
