"""`ssl_certificate_default` — the phase that exists only inside the default server block.

The DEFAULT_SERVER_SSL_CERT override could not be one more `ssl_certificate` provider. That phase
runs in every service block too, and it runs there whenever no provider matched — so a provider
appended to it would hand the default server's certificate to any service whose own providers
stayed silent. The conception calls this out as the implementation trap; the fix is a phase the
default server is the only block to render.

"Only the default server renders it" is a claim about a TEMPLATE, not about Lua, because the
runner is a Jinja include shared by both callers (`confs/partials/ssl-certificate-by-lua.conf`) and
NGINX accepts a single `ssl_certificate_by_lua_block` per server, "is duplicate"
(`src/deps/src/lua-nginx-module/src/ngx_http_lua_ssl_certby.c:136`). So both templates are rendered
here for real and the Lua that comes out of each is EXECUTED against stub plugins, which is the
only way to show that the service block does not merely skip the phase — it does not contain it.
"""

import re
import shutil
import subprocess
from importlib import import_module
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, Undefined

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

CERT_BLOCK = re.compile(r"^[ \t]*ssl_certificate_by_lua_block[ \t]*\{\n(.*?)\n\}\n", re.S | re.M)

# Enough of the global configuration for the two templates to render; none of it is under test.
TEMPLATE_VARS = {
    # The REAL callable Templator injects (`gen/Templator.py:487`), not a stub:
    # `default-server-http.conf` now includes the default-server phase runners, which read the
    # reserved id and the curated plugin subset out of `utils/default_server.py` through `import()`,
    # and a lookalike would let this environment render an allowlist the product never renders.
    # (`has_variable` was already in this dict, as a stub -- left exactly as it was.)
    "import": import_module,
    "LISTEN_HTTP": "yes",
    "USE_PROXY_PROTOCOL": "no",
    "ALL_HTTP_PORTS": ["80"],
    "ALL_HTTPS_PORTS": ["443"],
    "USE_IPV6": "no",
    "SSL_PROTOCOLS": "TLSv1.2 TLSv1.3",
    "SSL_SESSION_CACHE_SIZE": "10m",
    "SSL_ECDH_CURVE": "X25519",
    "SSL_CIPHERS_CUSTOM": "",
    "SSL_CIPHERS_LEVEL": "modern",
    "HTTP2": "yes",
    "HTTP3": "no",
    "HTTP3_ALT_SVC_PORT": "443",
    "IS_LOADING": "no",
    "USE_CUSTOM_SSL": "no",
    "all": {},
    "has_variable": lambda *args: False,
    "resolve_ssl_ecdh_curve": lambda value: value,
}

HARNESS = """
local body_path, scenario = arg[1], arg[2]

local calls, applied = {}, nil
local service_status = nil
if scenario == "matched" then
    service_status = { "SERVICE-CERT", "SERVICE-KEY" }
end

local fake_plugin = {
    ssl_certificate = function()
        return { ret = true, msg = "service provider", status = service_status }
    end,
    ssl_certificate_default = function()
        return { ret = true, msg = "override", status = { "OVERRIDE-CERT", "OVERRIDE-KEY" } }
    end,
}

-- What order.json + get_phases produce once customcert declares the new method.
local order = {
    ssl_certificate = { "customcert" },
    ssl_certificate_default = { "customcert" },
}

local modules = {
    middleclass = {},
    cjson = {},
    ["bunkerweb.utils"] = {},
    ["bunkerweb.clusterstore"] = {},
    ["bunkerweb.logger"] = { new = function() return { log = function() end } end },
    ["bunkerweb.datastore"] = {
        new = function()
            return {
                get = function(_, key)
                    if key == "plugins_order" then
                        return order, "success"
                    end
                    return nil, "not found"
                end,
            }
        end,
    },
    ["bunkerweb.helpers"] = {
        require_plugin = function()
            return fake_plugin
        end,
        new_plugin = function(plugin_lua)
            return true, plugin_lua
        end,
        call_plugin = function(plugin_obj, phase)
            calls[#calls + 1] = phase
            return true, plugin_obj[phase]()
        end,
    },
    ["ngx.ssl"] = {
        server_name = function()
            return "unknown.test"
        end,
        clear_certs = function()
            return true
        end,
        set_cert = function(cert)
            applied = cert
            return true
        end,
        set_priv_key = function()
            return true
        end,
    },
}

_G.ngx = {
    ERR = "ERR",
    INFO = "INFO",
    shared = { internalstore = {} },
    req = { is_internal = function() return false end },
}

_G.require = function(name)
    local module = modules[name]
    if module == nil then
        error("unexpected require : " .. tostring(name))
    end
    return module
end

assert(loadfile(body_path))()
print(table.concat(calls, ",") .. "|" .. tostring(applied))
"""


def render(template: str, **extra) -> str:
    env = Environment(  # nosec B701 - NGINX configuration, exactly as Templator builds it
        loader=FileSystemLoader([CONFS.as_posix()]),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
        undefined=Undefined,
    )
    return env.get_template(template).render(**{**TEMPLATE_VARS, **extra})


def certificate_block(rendered: str) -> str:
    blocks = CERT_BLOCK.findall(rendered)
    assert len(blocks) == 1, f"expected exactly one ssl_certificate_by_lua_block, got {len(blocks)}"
    return blocks[0]


def run(tmp_path, block: str, scenario: str) -> tuple[list[str], str]:
    body = tmp_path / "block.lua"
    body.write_text(block, encoding="utf-8")
    harness = tmp_path / "harness.lua"
    harness.write_text(HARNESS, encoding="utf-8")
    result = subprocess.run([LUA, str(harness), str(body), scenario], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls, _, applied = result.stdout.strip().partition("|")
    return ([call for call in calls.split(",") if call], applied)


DEFAULT_SERVER = "default-server-http.conf"
SERVICE = "server-http/ssl-certificate-lua.conf"


@needs_lua
def test_the_default_server_falls_through_to_the_override(tmp_path):
    """No provider matched the unknown SNI, so the override is what the client is shown."""
    calls, applied = run(tmp_path, certificate_block(render(DEFAULT_SERVER)), "unmatched")
    assert calls == ["ssl_certificate", "ssl_certificate_default"]
    assert applied == "OVERRIDE-CERT"


@needs_lua
def test_a_matched_certificate_still_wins_in_the_default_server(tmp_path):
    """The override runs only after every SNI-indexed provider declined; it never preempts one."""
    calls, applied = run(tmp_path, certificate_block(render(DEFAULT_SERVER)), "matched")
    assert calls == ["ssl_certificate"]
    assert applied == "SERVICE-CERT"


@needs_lua
def test_a_service_block_never_reaches_the_override(tmp_path):
    """The trap the conception names: the override must not be a fallback for a real service."""
    block = certificate_block(render(SERVICE))
    assert "ssl_certificate_default" not in block  # not skipped at runtime -- not in the file
    calls, applied = run(tmp_path, block, "unmatched")
    assert calls == ["ssl_certificate"]
    assert applied == "nil"


def test_the_phase_is_declared_where_the_runtime_looks_for_it():
    """`order.json` alone is not enough: `helpers.order_plugins` drops any phase `get_phases()`
    does not list (`src/bw/lua/bunkerweb/helpers.lua`), so the two have to agree."""
    order = (ROOT / "src" / "common" / "core" / "order.json").read_text(encoding="utf-8")
    phases = (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua").read_text(encoding="utf-8")
    get_phases = re.search(r"utils\.get_phases = function\(\).*?^end$", phases, re.S | re.M)
    assert get_phases, "get_phases not found -- renamed or removed?"

    assert '"ssl_certificate_default"' in order
    assert '"ssl_certificate_default"' in get_phases.group(0)
