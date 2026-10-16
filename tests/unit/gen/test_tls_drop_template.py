"""The TLS drop hook as the two server templates render it (CrowdSec port, lane C).

`ssl_client_hello_by_lua_block` carries the hook in the per-service server block and in the default
server. What the templates decide, and nothing else can, is the argument list of the call:

  * the service name (the default server passes none),
  * whether PROXY protocol / real IP are on,
  * the networks allowed to send a PROXY header -- only when `USE_PROXY_PROTOCOL`, `USE_REAL_IP` and
    `REAL_IP_HEADER == proxy_protocol` all hold, built from the same files `real-ip.conf` feeds to
    `set_real_ip_from` (the realip job's `combined.list`, then `REAL_IP_FROM`). Anything else renders
    `nil`, which the Lua reads as "client IP unknown: skip".

The environment is the one `Templator` builds (`test_ssl_certificate_partial.render`: same whitespace
flags), with `import` swapped for one that serves a fake `pathlib`, so a `combined.list` can exist.
"""

import re
import subprocess
from importlib import import_module
from shutil import which

import pytest
from jinja2 import Environment, FileSystemLoader

from test_ssl_certificate_partial import CONFS, DEFAULTS  # type: ignore

SERVICE_TEMPLATE = "server-http/ssl-certificate-lua.conf"
DEFAULT_TEMPLATE = "default-server-http.conf"
REAL_IP = {"USE_PROXY_PROTOCOL": "yes", "USE_REAL_IP": "yes", "REAL_IP_HEADER": "proxy_protocol", "REAL_IP_FROM": "10.0.0.0/8"}


def render(template: str, files: dict | None = None, **overrides) -> str:
    files = files or {}
    opened: list[str] = []

    class FakePath:
        def __init__(self, path):
            self.path = str(path)
            opened.append(self.path)

        def is_file(self):
            return self.path in files

        def read_text(self):
            return files[self.path]

    class FakePathlib:
        Path = FakePath

    def fake_import(name):
        return FakePathlib if name == "pathlib" else import_module(name)

    env = Environment(loader=FileSystemLoader(str(CONFS)), lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    variables = {
        **DEFAULTS,
        "SERVER_NAME": "app1.example.com www.example.com",
        "import": fake_import,
        **overrides,
    }
    rendered = env.get_template(template).render(variables)
    render.opened = opened  # type: ignore[attr-defined]
    return rendered


def hook_call(rendered: str) -> str:
    calls = re.findall(r'require\("bunkerweb\.tlsdrop"\)\.hook\(.*\)', rendered)
    assert len(calls) == 1, calls
    return calls[0]


def test_the_dummy_block_is_replaced_by_the_hook_in_a_service_block():
    got = render(SERVICE_TEMPLATE)
    assert "dummy block" not in got
    assert hook_call(got) == 'require("bunkerweb.tlsdrop").hook("app1.example.com", false, false, nil)'
    assert got.count("ssl_client_hello_by_lua_block {") == 1
    assert re.search(r"ssl_client_hello_by_lua_block \{\n\treturn require\(", got), "the hook result must be returned: true means the handshake was closed"


def test_the_default_server_passes_no_service_and_returns_when_it_dropped():
    got = render(DEFAULT_TEMPLATE)
    assert hook_call(got) == 'require("bunkerweb.tlsdrop").hook(nil, false, false, nil)'
    # run before anything else in the phase, and a drop ends the phase
    block = got.split("ssl_client_hello_by_lua_block {", 1)[1]
    assert block.index('require("bunkerweb.tlsdrop")') < block.index('internalstore:get("plugins_order", true)')
    assert re.search(r"hook\(nil, false, false, nil\) then\n\s+return\n\s+end", got)
    # the strict-SNI phase is still there
    assert 'call_plugin(plugin_obj, "ssl_client_hello_default")' in got


@pytest.mark.parametrize("template", (SERVICE_TEMPLATE, DEFAULT_TEMPLATE))
def test_proxy_protocol_and_real_ip_flags_reach_the_call(template):
    got = render(template, USE_PROXY_PROTOCOL="yes", USE_REAL_IP="no")
    assert ", true, false, nil)" in hook_call(got)
    got = render(template, USE_PROXY_PROTOCOL="no", USE_REAL_IP="yes", REAL_IP_HEADER="X-Forwarded-For")
    assert ", false, true, nil)" in hook_call(got)


@pytest.mark.parametrize("template", (SERVICE_TEMPLATE, DEFAULT_TEMPLATE))
@pytest.mark.parametrize("broken", ("USE_PROXY_PROTOCOL", "USE_REAL_IP", "REAL_IP_HEADER"))
def test_the_trusted_list_needs_all_three_conditions(template, broken):
    full = render(template, **REAL_IP)
    assert hook_call(full).endswith(', true, true, "10.0.0.0/8")')
    off = {**REAL_IP, broken: "no" if broken != "REAL_IP_HEADER" else "X-Forwarded-For"}
    got = hook_call(render(template, **off))
    assert got.endswith(", nil)"), got


def test_the_trusted_list_is_the_realip_job_list_then_real_ip_from_in_a_single_site():
    files = {"/var/cache/bunkerweb/realip/combined.list": "192.0.2.0/24\n2001:db8::/32\n"}
    got = hook_call(render(SERVICE_TEMPLATE, files=files, MULTISITE="no", **REAL_IP))
    assert got.endswith(', true, true, "192.0.2.0/24 2001:db8::/32 10.0.0.0/8")'), got
    assert render.opened == ["/var/cache/bunkerweb/realip/combined.list"]  # type: ignore[attr-defined]


def test_multisite_reads_the_service_list_like_real_ip_conf_does():
    files = {
        "/var/cache/bunkerweb/realip/app1.example.com/combined.list": "198.51.100.0/24\n",
        "/var/cache/bunkerweb/realip/combined.list": "203.0.113.0/24\n",
    }
    got = hook_call(render(SERVICE_TEMPLATE, files=files, MULTISITE="yes", **REAL_IP))
    assert '"198.51.100.0/24 10.0.0.0/8"' in got
    assert "203.0.113.0/24" not in got, "the global list leaked into a service block"
    assert render.opened == ["/var/cache/bunkerweb/realip/app1.example.com/combined.list"]  # type: ignore[attr-defined]


def test_the_default_server_always_reads_the_global_list():
    files = {
        "/var/cache/bunkerweb/realip/combined.list": "203.0.113.0/24\n",
        "/var/cache/bunkerweb/realip/app1.example.com/combined.list": "198.51.100.0/24\n",
    }
    got = hook_call(render(DEFAULT_TEMPLATE, files=files, MULTISITE="yes", **REAL_IP))
    assert got.endswith(', true, true, "203.0.113.0/24 10.0.0.0/8")'), got


def test_a_missing_list_leaves_real_ip_from_alone_and_an_empty_setting_an_empty_string():
    got = hook_call(render(SERVICE_TEMPLATE, **REAL_IP))
    assert got.endswith(', true, true, "10.0.0.0/8")')
    got = hook_call(render(SERVICE_TEMPLATE, **{**REAL_IP, "REAL_IP_FROM": ""}))
    assert got.endswith(', true, true, "")'), "an empty list is a string the Lua reads as 'trust nobody', not nil"


def test_nothing_is_read_from_disk_unless_the_proxy_protocol_conditions_hold():
    render(SERVICE_TEMPLATE)
    assert render.opened == []  # type: ignore[attr-defined]
    render(DEFAULT_TEMPLATE, USE_PROXY_PROTOCOL="yes", USE_REAL_IP="yes", REAL_IP_HEADER="X-Forwarded-For")
    assert render.opened == []  # type: ignore[attr-defined]


@pytest.mark.skipif(which("lua") is None and which("luajit") is None, reason="no stand-alone lua/luajit on PATH")
@pytest.mark.parametrize("template", (SERVICE_TEMPLATE, DEFAULT_TEMPLATE))
@pytest.mark.parametrize("proxy", (False, True))
def test_the_rendered_client_hello_block_is_valid_lua(tmp_path, template, proxy):
    files = {"/var/cache/bunkerweb/realip/combined.list": "192.0.2.0/24\n"}
    got = render(template, files=files, MULTISITE="no", **(REAL_IP if proxy else {}))
    body = got.split("ssl_client_hello_by_lua_block {\n", 1)[1]
    depth, end = 1, None
    for index, char in enumerate(body):
        depth += char == "{"
        depth -= char == "}"
        if depth == 0:
            end = index
            break
    assert end is not None
    script = tmp_path / "block.lua"
    script.write_text(body[:end], encoding="utf-8")
    lua = which("lua") or which("luajit")
    result = subprocess.run([lua, "-e", f"local ok, err = loadfile('{script}'); if not ok then error(err) end"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
