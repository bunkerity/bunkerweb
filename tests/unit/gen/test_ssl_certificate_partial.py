"""Shared certificate partial stays include-only and parses as Lua."""

import subprocess
from pathlib import Path
from shutil import which

import pytest
from importlib import import_module

from Templator import Templator  # type: ignore
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"

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
    "SERVER_NAME": "app1.example.com",
    "USE_REAL_IP": "no",
    "REAL_IP_HEADER": "X-Forwarded-For",
    "REAL_IP_FROM": "",
    "USE_IPV6": "no",
    "MULTISITE": "yes",
    "DISABLE_DEFAULT_SERVER": "no",
    "IS_LOADING": "no",
    "LISTEN_HTTP": "yes",
    "DENY_HTTP_STATUS": "444",
    "all": {"HTTP_PORT": "8080", "HTTPS_PORT": "8443"},
    "resolve_ssl_ecdh_curve": lambda value: value,
    "import": import_module,
    "has_variable": Templator.has_variable,
}


def render(template: str, **overrides) -> str:
    env = Environment(
        loader=FileSystemLoader(str(CONFS)),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template(template).render({**DEFAULTS, **overrides})


@pytest.mark.parametrize("template", ("server-http/ssl-certificate-lua.conf",))
def test_the_runner_is_included_once_not_twice(template):
    assert render(template).count("ssl_certificate_by_lua_block {") == 1


def test_the_partial_is_not_a_configuration_file_of_its_own():
    source = (ROOT / "src" / "common" / "gen" / "Templator.py").read_text(encoding="utf-8")
    body = source.split("def _categorize_templates", 1)[1].split("def ", 1)[0]
    assert '"partials"' not in body, "partials/ became a render context; the runner would be written out on its own"


@pytest.mark.skipif(which("lua") is None and which("luajit") is None, reason="no stand-alone lua/luajit on PATH")
@pytest.mark.parametrize("default_server_phase", (False, True))
def test_the_extracted_block_is_valid_lua(tmp_path, default_server_phase):
    rendered = render("partials/ssl-certificate-by-lua.conf", default_server_certificate_phase=default_server_phase)
    body = rendered.split("ssl_certificate_by_lua_block {\n", 1)[1].rstrip()
    assert body.endswith("}")
    script = tmp_path / "block.lua"
    script.write_text(body[:-1], encoding="utf-8")
    lua = which("lua") or which("luajit")
    result = subprocess.run([lua, "-e", f"local ok, err = loadfile('{script}'); if not ok then error(err) end"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
