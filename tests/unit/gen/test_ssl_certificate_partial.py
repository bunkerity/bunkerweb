"""F-LE-3 part B: the ssl_certificate phase runner reaches the default server too.

An SNI that matches no server block lands on the default server, which had only the internal
`/var/lib/bunkerweb/default-server-cert.pem` to show it. A wildcard certificate the operator
configured for `*.example.com` therefore never reached `sub.example.com` unless that exact name was
also a configured `SERVER_NAME` -- the smaller half of what the row exists to fix. The runner that
resolves it lived inline in `server-http/ssl-certificate-lua.conf`; it now lives in
`partials/ssl-certificate-by-lua.conf` and both callers include it.

What is asserted is the intent, not the current text:

  * both server blocks and the default server run the phase, so the two cannot drift apart again;
  * the static `ssl_certificate` stays on the default server -- when no plugin resolves anything
    the runner returns without calling `set_cert` and NGINX falls back to it. Removing it as
    "superseded" would leave the default server with no certificate at all;
  * the partial is never rendered as a configuration file of its own.

The byte-identity of the extraction itself was proven separately, by rendering both templates
across 13824 variable combinations before and after and diffing: 0 differences on
`server-http/ssl-certificate-lua.conf`. See `.cache/results-2026-08-20/lane-b-certificates.md`.
"""

import subprocess
from pathlib import Path
from shutil import which

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
PARTIAL = CONFS / "partials" / "ssl-certificate-by-lua.conf"

DEFAULTS = {
    "SSL_PROTOCOLS": "TLSv1.2 TLSv1.3",
    "SSL_SESSION_CACHE_SIZE": "10m",
    "SSL_CIPHERS_CUSTOM": "",
    "SSL_CIPHERS_LEVEL": "modern",
    "SSL_ECDH_CURVE": "X25519",
    "HTTP2": "yes",
    "HTTP3": "no",
    "HTTP3_ALT_SVC_PORT": "443",
    "USE_PROXY_PROTOCOL": "no",
    "USE_IPV6": "no",
    "MULTISITE": "yes",
    "DISABLE_DEFAULT_SERVER": "no",
    "IS_LOADING": "no",
    "LISTEN_HTTP": "yes",
    "DENY_HTTP_STATUS": "444",
    "all": {"HTTP_PORT": "8080", "HTTPS_PORT": "8443"},
    "resolve_ssl_ecdh_curve": lambda value: value,
}


def render(template: str, **overrides) -> str:
    env = Environment(  # same knobs as Templator._load_jinja_env
        loader=FileSystemLoader(str(CONFS)),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template(template).render({**DEFAULTS, **overrides})


CALLERS = ("server-http/ssl-certificate-lua.conf", "default-server-http.conf")


@pytest.mark.parametrize("template", CALLERS)
def test_the_phase_runner_is_rendered(template):
    """Both callers, one rule. A caller that stops running the phase serves whatever static
    certificate it happens to have, for every name, with no error anywhere."""
    got = render(template)
    assert "ssl_certificate_by_lua_block {" in got
    # Not just the opening directive: the include has to bring the body with it.
    assert 'call_plugin(plugin_obj, "ssl_certificate")' in got
    assert "set_priv_key(ret.status[2])" in got


@pytest.mark.parametrize("template", CALLERS)
def test_the_runner_is_included_once_not_twice(template):
    assert render(template).count("ssl_certificate_by_lua_block {") == 1


@pytest.mark.parametrize("template", CALLERS)
def test_the_static_certificate_stays_as_the_fallback(template):
    """The runner returns without calling `set_cert` when no plugin resolves anything, so NGINX
    falls back to these. They are not superseded by the hook."""
    got = render(template)
    assert "ssl_certificate /var/lib/bunkerweb/default-server-cert.pem;" in got
    assert "ssl_certificate_key /var/lib/bunkerweb/default-server-cert.key;" in got


def test_the_default_server_still_runs_the_client_hello_phase():
    """`DISABLE_DEFAULT_SERVER_STRICT_SNI` closes an unknown SNI in `ssl_client_hello_default`,
    a phase earlier than the certificate hook. Losing it would let the new hook serve a name the
    operator asked to refuse."""
    got = render("default-server-http.conf")
    assert "ssl_client_hello_by_lua_block {" in got
    assert 'call_plugin(plugin_obj, "ssl_client_hello_default")' in got


def test_the_partial_is_not_a_configuration_file_of_its_own():
    """`Templator._categorize_templates` keys on the template's top directory and drops anything
    whose context it does not know, so `partials/` is include-only. If that ever changes, the
    runner would be written to /etc/nginx as a bare Lua block outside any server context."""
    # Read the categories off the method rather than restating them here.
    source = (ROOT / "src" / "common" / "gen" / "Templator.py").read_text(encoding="utf-8")
    body = source.split("def _categorize_templates", 1)[1].split("def ", 1)[0]
    assert '"partials"' not in body, "partials/ became a render context; the runner would be written out on its own"


@pytest.mark.skipif(which("lua") is None and which("luajit") is None, reason="no stand-alone lua/luajit on PATH")
def test_the_extracted_block_is_valid_lua(tmp_path):
    """It is Lua inside an NGINX directive, so nothing else in the tree would catch a syntax error
    until an instance failed to start."""
    body = PARTIAL.read_text(encoding="utf-8").split("ssl_certificate_by_lua_block {\n", 1)[1].rstrip()
    assert body.endswith("}")
    script = tmp_path / "block.lua"
    script.write_text(body[:-1], encoding="utf-8")
    lua = which("lua") or which("luajit")
    result = subprocess.run([lua, "-e", f"local ok, err = loadfile('{script}'); if not ok then error(err) end"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_the_partial_carries_no_jinja():
    """It is included into two different contexts. A conditional in here would silently mean two
    different things depending on which caller's variables were in scope."""
    text = PARTIAL.read_text(encoding="utf-8")
    body = text.split("-#}\n", 1)[1]
    for marker in ("{%", "{{"):
        assert marker not in body, f"{marker} in the shared runner body"
