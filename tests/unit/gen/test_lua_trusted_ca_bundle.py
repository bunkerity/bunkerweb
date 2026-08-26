"""REDIS_SSL_CA has to reach the Lua request path, and must never be able to brick a boot.

`clusterstore.lua` talks to Redis/Valkey over an OpenResty cosocket, and a cosocket has no
per-connection trust store: it verifies against the single file `lua_ssl_trusted_certificate`
names. So the only way REDIS_SSL_CA can reach the request path is by joining that file --
`gen/main.py` appends it onto the shipped root bundle and `confs/{http,stream}.conf` point the
directive at the result, which push-configs ships to every instance.

Three properties are pinned here, and each one is a way this could go badly wrong:

* **Append, never replace.** The same trust store is what antibot, BunkerNet and CrowdSec verify
  their outbound HTTPS against. A bundle that carried only the operator's CA would break all three
  across the fleet, and it would look like a Redis feature working.
* **Unset is byte-identical.** The directive keeps naming the baked-in bundle, so a deployment that
  never sets REDIS_SSL_CA renders exactly what it rendered before this existed -- including when
  the setting is absent from the config dicts entirely, which is what the scheduler's
  `db.get_non_default_settings()` path produces.
* **A bad value stops generation.** `lua_ssl_trusted_certificate` pointing at a missing or
  malformed file makes NGINX *refuse to start*. Failing here leaves the fleet on the configuration
  it already has; shipping the bundle anyway takes the fleet down.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
# The real shipped bundle, not a stand-in: "append, never replace" is only meaningful against the
# 100-plus public roots that actually travel in the image.
ROOT_CA = ROOT / "src" / "bw" / "misc" / "root-ca.pem"

BAKED_IN_DIRECTIVE = 'lua_ssl_trusted_certificate "/usr/share/bunkerweb/misc/root-ca.pem";'
BUNDLE_DIRECTIVE = 'lua_ssl_trusted_certificate "/etc/nginx/lua-trusted-ca.pem";'

# A self-signed CA with a century of validity, inline so the suite needs neither the `openssl`
# binary nor a crypto dependency. Loading a CA does not check its dates, but a long-lived one keeps
# the failure mode unambiguous if that ever changes.
TEST_CA = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIDMTCCAhmgAwIBAgIUJafj0UX3dCOraVsgdpfHVuCbOcIwDQYJKoZIhvcNAQEL\n"
    "BQAwJzElMCMGA1UEAwwcQnVua2VyV2ViIHVuaXQtdGVzdCBSZWRpcyBDQTAgFw0y\n"
    "NjA4MjYxNTM2NDRaGA8yMTI2MDgwMjE1MzY0NFowJzElMCMGA1UEAwwcQnVua2Vy\n"
    "V2ViIHVuaXQtdGVzdCBSZWRpcyBDQTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCC\n"
    "AQoCggEBAJ+EEr/8ZZTTXwEChiU0ecF1YkuJVLmZfhToakqzkSxSuJueNkPF6PBp\n"
    "nvZyapmVx9MXt57GZ+KRTJ6Kcrip/Sk6fRSeGisM74NMJlpsVbsssXOpQwhP3GcG\n"
    "cCm7p6ei6MjkTHLFDSaG9Y8j6KzXCzajJO8cz9Zn9EF8lOBRANS6UM7m8AZqR5OF\n"
    "woKUAupw+vvpvXImesgRFOGSFn8CR8+AZj6r6lsAnoAhN0Ah8HE/TKmSe+QQqL2E\n"
    "xIoR3FJGLA/+OxBrbX8pisq79h3/Uxn631B6g/llRIoWFAyKVZj/3hK5OIWTHg1O\n"
    "NPQAl6MQDQg5t/swMK0E84Jcub4qr8kCAwEAAaNTMFEwHQYDVR0OBBYEFKqRhSxt\n"
    "pUkjXkVItcGsa4Rg42b2MB8GA1UdIwQYMBaAFKqRhSxtpUkjXkVItcGsa4Rg42b2\n"
    "MA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQELBQADggEBAD86+c/VRWIehsXr\n"
    "7Wzt/TK7AuI5ftGn/bdBSTRD56oqOjfbkePQFS3zaARafbvphhte7KrxOSs/aTPP\n"
    "GCUwbgtQ2CBLL3Q+Dp18+/OlZzMvXynxqNjO9jDgVFDqIBVlYMbOUpry+x3nuUm8\n"
    "WZ0uYyAmSuZZFf1rlA0E2DTo3FZDFuP0MpcGGC26b6eaKEdEF2zCnTnxwkzcp9Uu\n"
    "tDUSzuYjAzjeATEDBVg97eyHLa1Y1sYLsNC3jaPFKbBMei5CaQG0/OXN5RGjObzo\n"
    "S9B01GaUYHxTJk3ZmJ8yXB9ruu9fY2JzjHMl9yEXAX2dworO5XrTM5zpYSdWWKjF\n"
    "/GKulsg=\n"
    "-----END CERTIFICATE-----\n"
)


@pytest.fixture(scope="module")
def gen_main():
    """Load `src/common/gen/main.py` by path under a unique name.

    `main` is far too generic to import bare: several suites are collected in one interpreter and
    the module that wins would be whichever sys.path entry came first. The file's real work is
    behind `if __name__ == "__main__"`, so executing it here only defines the helpers.
    """
    for extra in ("src/common/gen", "src/common/utils", "src/common/api"):
        path = str(ROOT / extra)
        if path not in sys.path:
            sys.path.insert(0, path)
    spec = importlib.util.spec_from_file_location("bw_gen_main", ROOT / "src" / "common" / "gen" / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shipped_roots(gen_main, monkeypatch):
    """Point the generator at the repo's root bundle; /usr/share/bunkerweb does not exist here."""
    monkeypatch.setattr(gen_main, "LUA_TRUSTED_CA_SOURCE", ROOT_CA)
    return ROOT_CA


def _ca_count(pem: str) -> int:
    from ssl import PROTOCOL_TLS_CLIENT, SSLContext

    context = SSLContext(PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=pem)
    return len(context.get_ca_certs())


# --------------------------------------------------------------------------------------
# gen/main.py :: write_lua_trusted_ca_bundle
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "   ", None], ids=["empty", "blank", "none"])
def test_nothing_is_written_when_the_setting_is_not_set(gen_main, shipped_roots, tmp_path, value):
    gen_main.write_lua_trusted_ca_bundle(value, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_operator_ca_is_appended_and_the_roots_survive(gen_main, shipped_roots, tmp_path):
    ca_file = tmp_path / "redis-ca.pem"
    ca_file.write_text(TEST_CA)
    output = tmp_path / "out"
    output.mkdir()

    gen_main.write_lua_trusted_ca_bundle(str(ca_file), output)

    bundle = (output / gen_main.LUA_TRUSTED_CA_BUNDLE).read_bytes()
    roots = shipped_roots.read_bytes()

    # The operator CA is there ...
    assert TEST_CA.strip().encode() in bundle
    # ... and so is every certificate that was there before, byte for byte. Compared as BYTES on
    # purpose: the shipped bundle is CRLF-terminated, and reading it as text normalises 1794 line
    # endings, so a text-mode round trip would rewrite the roots while still "containing" them.
    assert bundle.startswith(roots)
    assert _ca_count(bundle.decode()) == _ca_count(roots.decode()) + 1


def test_a_missing_ca_file_stops_generation(gen_main, shipped_roots, tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(SystemExit) as exc:
        gen_main.write_lua_trusted_ca_bundle(str(tmp_path / "nope.pem"), output)
    assert exc.value.code == 1
    assert list(output.iterdir()) == [], "a half-written bundle is exactly the boot-breaker this guards"


def test_a_ca_file_that_is_not_a_certificate_stops_generation(gen_main, shipped_roots, tmp_path):
    """The operator's file is validated ALONE, and it has to be.

    OpenSSL ignores non-PEM text that trails a valid bundle, so validating only the concatenation
    would accept this file and ship a trust store that does not trust the Redis/Valkey CA at all --
    verification would then fail at runtime with a certificate error nobody could explain.
    """
    ca_file = tmp_path / "redis-ca.pem"
    ca_file.write_text("this is a private key, or a README, or nothing at all\n")
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(SystemExit) as exc:
        gen_main.write_lua_trusted_ca_bundle(str(ca_file), output)
    assert exc.value.code == 1
    assert list(output.iterdir()) == []


def test_a_truncated_pem_block_stops_generation(gen_main, shipped_roots, tmp_path):
    ca_file = tmp_path / "redis-ca.pem"
    ca_file.write_text("-----BEGIN CERTIFICATE-----\nZm9v\n-----END CERTIFICATE-----\n")
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(SystemExit) as exc:
        gen_main.write_lua_trusted_ca_bundle(str(ca_file), output)
    assert exc.value.code == 1


def test_a_missing_root_bundle_stops_generation(gen_main, monkeypatch, tmp_path):
    """The worker had no root-ca.pem until this feature added one to its image.

    Appending to a bundle that is not there would silently produce a trust store holding ONLY the
    operator's CA -- antibot, BunkerNet and CrowdSec would then fail every HTTPS call on the fleet.
    Refusing to generate is the only safe answer.
    """
    monkeypatch.setattr(gen_main, "LUA_TRUSTED_CA_SOURCE", tmp_path / "absent-root-ca.pem")
    ca_file = tmp_path / "redis-ca.pem"
    ca_file.write_text(TEST_CA)
    output = tmp_path / "out"
    output.mkdir()

    with pytest.raises(SystemExit) as exc:
        gen_main.write_lua_trusted_ca_bundle(str(ca_file), output)
    assert exc.value.code == 1
    assert list(output.iterdir()) == []


# --------------------------------------------------------------------------------------
# confs/{http,stream}.conf :: the directive
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("conf", ["http.conf", "stream.conf"])
def test_the_directive_is_unchanged_when_the_setting_is_unset(render_tree, conf):
    rendered = render_tree()[conf]
    assert BAKED_IN_DIRECTIVE in rendered
    assert "lua-trusted-ca" not in rendered


@pytest.mark.parametrize("conf", ["http.conf", "stream.conf"])
def test_the_directive_names_the_combined_bundle_when_the_setting_is_set(render_tree, conf):
    rendered = render_tree(REDIS_SSL_CA="/etc/bunkerweb/redis-ca.pem")[conf]
    assert BUNDLE_DIRECTIVE in rendered
    assert BAKED_IN_DIRECTIVE not in rendered


@pytest.mark.parametrize("conf", ["http.conf", "stream.conf"])
def test_a_setting_absent_from_the_config_falls_back_to_the_baked_in_bundle(conf):
    """The guard has to fail CLOSED, and the obvious spelling does not.

    The scheduler renders from `db.get_non_default_settings()`, so a setting left at its default is
    absent from the config dict; Templator's custom Undefined then answers `!= ""` with **True**
    (jinja2's `Undefined.__eq__` compares types, so an undefined value is never equal to a string).
    A `{% if REDIS_SSL_CA != "" %}` guard would therefore name a bundle that was never written, and
    NGINX refuses to start on a missing `lua_ssl_trusted_certificate` -- on every instance in the
    fleet, at the next reload.

    Rendered with REDIS_SSL_CA removed from the config, the defaults AND the full config, which is
    stricter than any real path and is the case that separates the two spellings. Everything else
    is the genuine Configurator output, because the templates need the rest of it to render at all.
    """
    import logging
    import tempfile

    import Templator as T  # type: ignore  # src/common/gen is on sys.path via this suite's conftest
    from Configurator import Configurator  # type: ignore

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        try:
            plugins = sandbox / "plugins"
            plugins.mkdir()
            pro_plugins = sandbox / "pro-plugins"
            pro_plugins.mkdir()
            output = sandbox / "out"
            output.mkdir()

            config = Configurator(
                str(ROOT / "src" / "common" / "settings.json"),
                str(ROOT / "src" / "common" / "core"),
                str(plugins),
                str(pro_plugins),
                {},
                logging.getLogger("absent-redis-ssl-ca"),
            ).get_config(None)
            assert config.pop("REDIS_SSL_CA", None) is not None, "the setting vanished from the manifests -- this test no longer tests anything"

            T.Templator(
                str(ROOT / "src" / "common" / "confs"),
                str(ROOT / "src" / "common" / "core"),
                str(plugins),
                str(pro_plugins),
                str(output),
                "/etc/nginx",
                config,
                dict(config),
                dict(config),
            ).render()
            rendered = (output / conf).read_text()
        finally:
            T.sep = original_sep

    assert BAKED_IN_DIRECTIVE in rendered
    assert "lua-trusted-ca" not in rendered
