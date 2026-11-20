"""mTLS must keep verifying client certificates while no CA bundle has been distributed yet.

``mtls.conf`` used to drop ``ssl_verify_client`` (and the depth) whenever the cached ``ca.pem`` was
absent -- on the first start before the scheduler had distributed a bundle, and permanently once a
configured CA failed validation and its cache was deleted -- so an mTLS-protected service silently
accepted clients with no certificate. The templates now keep the verification directives and point
``ssl_client_certificate`` / ``ssl_trusted_certificate`` at a shipped placeholder CA that nothing can
be validated against, in the HTTP and in the stream server block alike.

Refs: 1.6.13 to 1.6.15rc1 review (mTLS fail-open), mTLS CA distribution.
"""

import re
from pathlib import Path

import pytest

from _t4_helpers import ROOT, full_renderer

PLACEHOLDER = "/usr/share/bunkerweb/core/mtls/misc/placeholder-ca.pem"
BLOCKS = {"http": "server-http/mtls.conf", "stream": "server-stream/mtls.conf"}


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def render_block(render, kind, **variables):
    """The mTLS directives of the ``kind`` ("http" or "stream") server block, comments removed, as a list.

    ``mtls.conf`` is rendered per server block, so the service is single-site; the name is one no
    scheduler ever cached a CA bundle for, which is the "nothing distributed yet" state.
    """
    base = {"MULTISITE": "no", "SERVER_NAME": "no-cached-ca.example.com", "USE_MTLS": "yes", "MTLS_VERIFY_CLIENT": "on"}
    if kind == "stream":
        base["SERVER_TYPE"] = "stream"
    tree = render(**(base | variables))
    return [line.strip() for line in tree[BLOCKS[kind]].splitlines() if line.strip() and not line.strip().startswith("#")]


@pytest.mark.parametrize("kind", BLOCKS)
@pytest.mark.parametrize("mode", ["on", "optional"])
def test_verification_stays_enforced_without_a_cached_ca(render, kind, mode):
    """The strict modes keep ``ssl_verify_client`` when there is no CA bundle (the fail-open bug)."""
    directives = render_block(render, kind, MTLS_VERIFY_CLIENT=mode)
    assert f"ssl_verify_client {mode};" in directives


@pytest.mark.parametrize("kind", BLOCKS)
def test_a_missing_ca_points_at_the_placeholder_and_keeps_depth(render, kind):
    """No client can chain to the placeholder, so a missing bundle rejects clients instead of admitting them."""
    directives = render_block(render, kind, MTLS_VERIFY_DEPTH="3")
    assert directives == [
        f"ssl_client_certificate {PLACEHOLDER};",
        f"ssl_trusted_certificate {PLACEHOLDER};",
        "ssl_verify_client on;",
        "ssl_verify_depth 3;",
    ]


@pytest.mark.parametrize("kind", BLOCKS)
def test_optional_no_ca_never_gets_the_placeholder(render, kind):
    """``optional_no_ca`` asks for a certificate without a CA on purpose: no placeholder is injected."""
    directives = render_block(render, kind, MTLS_VERIFY_CLIENT="optional_no_ca")
    assert "ssl_verify_client optional_no_ca;" in directives
    assert not [line for line in directives if "ssl_client_certificate" in line or "ssl_trusted_certificate" in line]


@pytest.mark.parametrize("kind", BLOCKS)
def test_disabled_mtls_renders_nothing(render, kind):
    assert render_block(render, kind, USE_MTLS="no") == []


@pytest.mark.parametrize("kind", BLOCKS)
def test_a_cached_ca_replaces_the_placeholder(render, monkeypatch, kind):
    """Control: the placeholder is only the fallback, a distributed bundle (and its CRL) still wins."""
    cache = "/var/cache/bunkerweb/mtls/with-cached-ca.example.com/"
    real_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: str(self).startswith(cache) or real_is_file(self))
    directives = render_block(render, kind, SERVER_NAME="with-cached-ca.example.com")
    assert directives == [
        f"ssl_client_certificate {cache}ca.pem;",
        f"ssl_trusted_certificate {cache}ca.pem;",
        f"ssl_crl {cache}crl.pem;",
        "ssl_verify_client on;",
        "ssl_verify_depth 2;",
    ]


def test_the_placeholder_the_templates_name_ships_and_is_a_certificate():
    """The rendered path maps onto a file of the source tree, and nginx can parse a certificate out of it."""
    shipped = ROOT / "src" / "common" / "core" / "mtls" / "misc" / "placeholder-ca.pem"
    assert shipped.is_file()
    assert re.search(r"-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----", shipped.read_text())
