"""The default server's three phase runners, EXECUTED.

Until conception option (b) the default server block ran `ssl_client_hello_default`, the shared
`ssl_certificate` runner and `log_default`, and nothing else -- no `set`, no `access`, no `header`.
So no multisite plugin ever executed on default-server traffic, and "configure the default server
like a service" could not mean anything. The three runners added there are deliberately NOT copies
of their service-block siblings: they carry a curated allowlist and they rebind the request context
to the reserved service id.

Both of those are claims about behaviour, not about text, so the rendered Lua is executed under a
stand-alone interpreter against stub plugins. A grep would pass on a runner whose allowlist is
built and then never consulted.
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

TEMPLATE_VARS = {
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
    # The three runners are rendered in multisite mode only (PO ruling 2026-09-06): single-site has
    # no per-service materialisation and no per-site variables table, so they would resolve the
    # curated chains against the GLOBAL values. `test_they_are_not_rendered_in_single_site` below is
    # the other direction.
    "MULTISITE": "yes",
    "UI_HOST": "",
    "all": {},
    "has_variable": lambda *args: False,
    "resolve_ssl_ecdh_curve": lambda value: value,
    # Templator's own Jinja global. The runners read the reserved id and the curated subset straight
    # out of `utils/default_server.py` through it, which is what stops the Lua table and the Python
    # constant from drifting.
    "import": import_module,
}

# `whitelist` is in the curated subset, `blacklist` is not. Both are real plugin ids and both
# implement every phase under test, so the only thing that can separate them is the allowlist.
HARNESS = """
local body_path = arg[1]

local calls = {}
local bound, restored = nil, nil

local fake_plugin = {
    set = function() return { ret = true, msg = "ok" } end,
    access = function() return { ret = true, msg = "ok" } end,
    header = function() return { ret = true, msg = "ok" } end,
}

local order = {
    global = {
        set = { "whitelist", "blacklist" },
        access = { "whitelist", "blacklist" },
        header = { "whitelist", "blacklist" },
    },
}

local ctx = { bw = { server_name = "_", remote_addr = "10.0.0.1" } }

local modules = {
    middleclass = {},
    cjson = {},
    ["bunkerweb.utils"] = {
        is_whitelisted = function() return false end,
        is_ip_whitelisted = function() return false, "ok" end,
        is_banned = function() return false end,
        set_reason = function() end,
        get_deny_status = function() return 403 end,
        get_security_mode = function() return "block" end,
    },
    ["bunkerweb.clusterstore"] = {},
    ["bunkerweb.cachestore"] = { new = function() return { update = function() return true end } end },
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
        fill_ctx = function() return true, "ok", nil, ctx end,
        save_ctx = function(saved) restored = saved.bw.server_name end,
        require_plugin = function() return fake_plugin end,
        new_plugin = function(plugin_lua) return true, plugin_lua end,
        call_plugin = function(plugin_obj, phase)
            calls[#calls + 1] = phase
            bound = ctx.bw.server_name
            return true, plugin_obj[phase]()
        end,
    },
}

_G.ngx = {
    ERR = "ERR",
    INFO = "INFO",
    WARN = "WARN",
    NOTICE = "NOTICE",
    OK = 0,
    HTTP_MOVED_TEMPORARILY = 302,
    HTTP_BAD_REQUEST = 400,
    HTTP_TOO_MANY_REQUESTS = 429,
    HTTP_NOT_ALLOWED = 405,
    shared = { internalstore = {} },
    var = { server_name = "_" },
    req = { is_internal = function() return false end },
    exit = function() end,
    redirect = function() end,
}

_G.require = function(name)
    local module = modules[name]
    if module == nil then
        error("unexpected require : " .. tostring(name))
    end
    return module
end

assert(loadfile(body_path))()
print(#calls .. "|" .. tostring(bound) .. "|" .. tostring(restored) .. "|" .. tostring(ctx.bw.server_name))
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


def lua_block(rendered: str, directive: str) -> str:
    """The body of one `*_by_lua_block`, brace-matched.

    A regex up to the first `}` would stop inside the first Lua table; these bodies are ~100 lines
    with nested blocks, so the match has to count.
    """
    match = re.search(re.escape(directive) + r"[^\n{]*\{", rendered)
    assert match, f"{directive} not found in the rendered template"
    start = rendered.index("{", match.end() - 1)
    depth = 0
    for index in range(start, len(rendered)):
        if rendered[index] == "{":
            depth += 1
        elif rendered[index] == "}":
            depth -= 1
            if depth == 0:
                return rendered[start + 1 : index]  # noqa: E203
    raise AssertionError(f"unbalanced braces after {directive}")


def run(tmp_path, block: str):
    body = tmp_path / "block.lua"
    body.write_text(block, encoding="utf-8")
    harness = tmp_path / "harness.lua"
    harness.write_text(HARNESS, encoding="utf-8")
    result = subprocess.run([LUA, str(harness), str(body)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    called, bound, restored, final = result.stdout.strip().split("|")
    return int(called), bound, restored, final


RUNNERS = ("set_by_lua_block", "access_by_lua_block", "header_filter_by_lua_block")


@needs_lua
@pytest.mark.parametrize("directive", RUNNERS)
def test_a_refused_plugin_is_not_invoked(tmp_path, directive):
    """`blacklist` sits next to `whitelist` in every phase order the stub returns. One is in the
    curated subset and one is not, so exactly one call is the whole assertion."""
    called, _, _, _ = run(tmp_path, lua_block(render("default-server-http.conf"), directive))
    assert called == 1


@needs_lua
@pytest.mark.parametrize("directive", RUNNERS)
def test_the_context_is_bound_to_the_reserved_id_during_the_call(tmp_path, directive):
    """PO ruling 1. Without this the plugin resolves its settings against `ngx.var.server_name`,
    which is the literal `_` here, and every value the operator sets on the Default server page is
    silently ignored."""
    _, bound, _, _ = run(tmp_path, lua_block(render("default-server-http.conf"), directive))
    assert bound == "default-server"


@needs_lua
@pytest.mark.parametrize("directive", RUNNERS)
def test_the_marker_is_restored_before_the_context_is_saved(tmp_path, directive):
    """`log_default` runs later on this same saved context, and `badbehavior.lua:76` propagates a
    default-server ban to every service precisely by testing for `_`. A rebind that leaks past
    `save_ctx` silently scopes those bans to one pseudo-service."""
    _, _, restored, final = run(tmp_path, lua_block(render("default-server-http.conf"), directive))
    assert restored == "_"
    assert final == "_"


@needs_lua
@pytest.mark.parametrize("directive", RUNNERS)
def test_the_service_block_siblings_have_no_allowlist(tmp_path, directive):
    """The restriction belongs to the default server, never to the product."""
    sibling = {
        "set_by_lua_block": "server-http/set-lua.conf",
        "access_by_lua_block": "server-http/access-lua.conf",
        "header_filter_by_lua_block": "server-http/header-lua.conf",
    }[directive]
    assert "allowed_plugins" not in render(sibling)


def test_no_curated_plugin_leaves_a_phase_through_ngx_exit():
    """The invariant the runners' context restore rests on, and the one thing they cannot enforce.

    The rebind is undone by an in-place assignment on the way out of the runner. A curated plugin
    that called `ngx.exit` itself would end the request from inside the plugin loop, skip that
    assignment, and leave `ctx.bw.server_name` as the reserved id for `log_default` -- where
    `badbehavior.lua:76` reads `_` to decide that a default-server ban applies to every service, so
    the leak silently narrows a fleet-wide ban to one pseudo-service.

    Every curated plugin returns through `self:ret` today. This is what notices when one stops.
    """
    default_server = import_module("default_server")
    checked = []
    offenders = []
    for plugin_id in default_server.DEFAULT_SERVER_PLUGINS:
        source = ROOT / "src" / "common" / "core" / plugin_id / f"{plugin_id}.lua"
        if not source.is_file():
            continue
        checked.append(plugin_id)
        body = source.read_text(encoding="utf-8")
        if re.search(r"ngx\.exit|[^\w.]exit\(", body):
            offenders.append(plugin_id)
    # Guards the guard: a typo in the path above would make the loop check nothing and pass.
    assert len(checked) >= 5, f"only checked {checked}"
    assert offenders == [], f"curated plugins calling exit(): {offenders}"


def test_they_are_not_rendered_in_single_site():
    """The gate itself, on the template rather than through the whole tree (that is
    `tests/unit/gen/test_default_server_multisite_only.py`). The three runners resolve every curated
    plugin's settings per-service, and `MULTISITE=no` has no per-service settings and no
    `variables["default-server"]` table -- so they would run the chains against the GLOBAL values,
    which is a NEW 301 and a NEW whitelist chain on catch-all traffic for a deployment that never
    asked for either."""
    block = render("default-server-http.conf", MULTISITE="no")
    assert "set_by_lua_block $default_server_dummy_set" not in block
    assert "access_by_lua_block" not in block
    assert "header_filter_by_lua_block" not in block
    # The certificate phase is built from four GLOBAL settings and must survive: it is what the
    # documentation tells a single-site operator to use.
    assert block.count("ssl_certificate_by_lua_block {") == 1
