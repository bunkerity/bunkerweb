"""mTLS conf rendering — `USE_MTLS=yes` must never leave TLS unprotected.

`mtls/confs/server-{http,stream}/mtls.conf` are rendered by the Scheduler (or the Worker), while
NGINX opens `MTLS_CA_CERTIFICATE` / `MTLS_CRL` on the BunkerWeb instance. The two do not share a
filesystem in a split deployment, so the templates deliberately do **not** probe the paths: a probe
answers about the wrong host and used to disable client verification silently for a CA that was
correctly mounted where NGINX reads it.

These tests pin that decision. They render the shipped templates with plain Jinja — no Templator,
no daemon, no filesystem — because "the render host cannot see the file" is the case under test.
"""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

CONFS = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "mtls" / "confs"
KINDS = ("server-http", "server-stream")

# Guaranteed absent on the machine running the tests: this host stands in for a render host that
# does not have the operator's CA. See `test_probe_would_discriminate_on_file_presence_only`.
ABSENT_CA = "/nonexistent/definitely-not-here/ca.pem"
ABSENT_CRL = "/nonexistent/definitely-not-here/crl.pem"

DEFAULTS = {
    "USE_MTLS": "no",
    "MTLS_CA_CERTIFICATE": "",
    "MTLS_VERIFY_CLIENT": "on",
    "MTLS_CRL": "",
    "MTLS_VERIFY_DEPTH": "2",
}


def render(kind: str, **overrides) -> str:
    env = Environment(  # same knobs as Templator._build_environment
        loader=FileSystemLoader(str(CONFS / kind)),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template("mtls.conf").render({**DEFAULTS, **overrides})


def directives(text: str) -> list:
    """Only what NGINX acts on — comments and blank lines are not configuration."""
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


@pytest.mark.parametrize("kind", KINDS)
class TestFailClosed:
    """`USE_MTLS=yes` with no usable CA must refuse TLS, never serve it unverified."""

    @pytest.mark.parametrize("mode", ["on", "optional"])
    def test_empty_ca_refuses_the_handshake(self, kind, mode):
        got = directives(render(kind, USE_MTLS="yes", MTLS_VERIFY_CLIENT=mode))
        assert "ssl_reject_handshake on;" in got
        # Emitting ssl_verify_client here would be an NGINX config error (no CA), and omitting both
        # is the silent degrade this replaced: NGINX defaults to `ssl_verify_client off`.
        assert not any(d.startswith("ssl_verify_client") for d in got)

    def test_whitespace_only_ca_counts_as_empty(self, kind):
        got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE="   "))
        assert "ssl_reject_handshake on;" in got

    def test_optional_no_ca_stays_usable(self, kind):
        """`optional_no_ca` performs no CA validation by design — diagnostics, not a degrade."""
        got = directives(render(kind, USE_MTLS="yes", MTLS_VERIFY_CLIENT="optional_no_ca"))
        assert "ssl_verify_client optional_no_ca;" in got
        assert "ssl_reject_handshake on;" not in got

    def test_disabled_emits_nothing(self, kind):
        assert directives(render(kind, MTLS_CA_CERTIFICATE=ABSENT_CA)) == []


@pytest.mark.parametrize("kind", KINDS)
class TestNoRenderHostProbe:
    """The paths are emitted on configuration, never on what the *render* host can stat."""

    def test_ca_absent_here_is_still_emitted(self, kind):
        got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE=ABSENT_CA))
        assert f"ssl_client_certificate {ABSENT_CA};" in got
        assert "ssl_verify_client on;" in got
        assert "ssl_reject_handshake on;" not in got

    def test_crl_absent_here_is_still_emitted(self, kind):
        got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE=ABSENT_CA, MTLS_CRL=ABSENT_CRL))
        assert f"ssl_crl {ABSENT_CRL};" in got

    def test_crl_not_configured_is_not_emitted(self, kind):
        got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE=ABSENT_CA))
        assert not any(d.startswith("ssl_crl") for d in got)

    def test_ssl_trusted_certificate_is_not_emitted(self, kind):
        """Redundant: `ssl_client_certificate` is the same trust store and also advertises its CAs."""
        got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE=ABSENT_CA))
        assert not any(d.startswith("ssl_trusted_certificate") for d in got)

    def test_template_has_no_filesystem_probe(self, kind):
        import re

        # Strip Jinja comments first: the template's own comment explains why there is no probe,
        # and a plain substring search cannot tell that sentence apart from the thing it forbids.
        src = re.sub(r"\{#.*?#\}", "", (CONFS / kind / "mtls.conf").read_text(encoding="utf-8"), flags=re.S)

        # Assert the GATEWAY, not a list of spellings. Templator exposes `import(...)` as the only
        # way a template reaches Python, so every filesystem probe must pass through it -- while
        # enumerating `.is_file()` / `.exists()` / `pathlib` leaves `os.path.isfile` wide open.
        # Measured: a mutant using os.path.isfile passed the enumerated form (2 passed) and was
        # caught only by the render cases below (15 failed). A marker with one known-good case is
        # a marker that has only ever been tested against deletion.
        assert "import(" not in src, "this template must not reach the render host's filesystem -- see the block comment in it"
        assert ".is_file()" not in src and ".exists()" not in src and "pathlib" not in src


def test_probe_would_discriminate_on_file_presence_only(tmp_path):
    """Control: the absent-path cases above must fail for the *right* reason.

    With a CA that exists on this host, a presence-probing template renders correctly — so the
    difference between pass and fail is exactly one variable, whether the render host holds the
    file. Without this control, those cases would only prove that a made-up path is missing.
    """
    present_ca = tmp_path / "ca.pem"
    present_ca.write_text("", encoding="utf-8")
    for kind in KINDS:
        for ca in (str(present_ca), ABSENT_CA):
            got = directives(render(kind, USE_MTLS="yes", MTLS_CA_CERTIFICATE=ca))
            assert f"ssl_client_certificate {ca};" in got, f"{kind}: {ca} not emitted"


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"USE_MTLS": "yes"},
        {"USE_MTLS": "yes", "MTLS_VERIFY_CLIENT": "optional"},
        {"USE_MTLS": "yes", "MTLS_VERIFY_CLIENT": "optional_no_ca"},
        {"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE": ABSENT_CA},
        {"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE": ABSENT_CA, "MTLS_CRL": ABSENT_CRL},
        {"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE": ABSENT_CA, "MTLS_VERIFY_DEPTH": "5"},
    ],
)
def test_http_and_stream_stay_in_lockstep(overrides):
    """The two templates differ only in prose. A fix applied to one and not the other is a defect."""
    assert directives(render("server-http", **overrides)) == directives(render("server-stream", **overrides))
