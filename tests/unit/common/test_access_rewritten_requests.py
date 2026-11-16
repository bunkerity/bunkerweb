"""A request rewritten by a custom config must go through the access phase (dev a71fb5122).

A ``rewrite`` in a ``server-http`` custom config sets ``r->internal`` (nginx ``ngx_http_script.c``,
``ngx_http_script_regex_start_code``), and ``server.conf`` used to include the custom configs BEFORE
``set-lua.conf``. So on a rewritten request ``set`` never ran (the rewrite ends the server rewrite
phase first) and ``access-lua.conf`` returned early on ``is_internal()``: bans, lists, rate limit,
antibot, authentication and the ModSecurity reason handling were all off for that request.

The fix has three parts and each one is pinned here:

* ``set-lua.conf`` is included first, so it runs on the original request;
* ``access-lua.conf`` runs for an internal request that is a rewrite of a request whose ``set`` ran
  and whose access has not run yet, and for nothing else;
* the variables the set phase writes are no longer redeclared by a later include.

The second part is the one that can double-process or over-skip, so the *rendered* ``set`` and
``access`` blocks are executed under a stand-alone ``lua`` against stubbed plugins, over the request
lifetimes nginx really produces. Two facts of nginx drive those lifetimes:

* an internal redirect (``error_page`` to a URI, ``index``, ``try_files``, ``ngx.exec``) and a named
  location both clear the Lua request context (``ngx_memzero(r->ctx)``), so ``ngx.ctx`` starts empty;
* 1.7's ``set-lua.conf`` rebuilds ``ngx.ctx.bw`` on the internal path (``fill_ctx()``, so the
  ``$bw_*`` log variables survive the redirect), so "``ngx.ctx.bw`` exists" does NOT mean "this is a
  rewrite". Dev's gate (``not bw_ctx or bw_ctx.access_done``) relied on it meaning exactly that.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, Undefined

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# Every phase of one request, as nginx runs them. `reset` is an internal redirect or a named
# location: the Lua request context is cleared. A step's boolean is `ngx.req.is_internal()`.
SCENARIOS = {
    # A plain request.
    "original": (("set", False), ("access", False)),
    # `rewrite ... last;` / `break;`: same Lua context, `r->internal` set, `set` ran before the rewrite.
    "rewritten": (("set", False), ("access", True)),
    # The same request meeting a second internal re-entry of the access phase must not be checked twice.
    "rewritten_then_access_again": (("set", False), ("access", True), ("access", True)),
    # `error_page 403 /page` after the access phase denied the request: the redirect re-runs `set`.
    "error_page_after_access": (("set", False), ("access", False), ("reset",), ("set", True), ("access", True)),
    # `index` / `try_files` after a rewrite that was already checked.
    "redirect_after_rewritten_access": (("set", False), ("access", True), ("reset",), ("set", True), ("access", True)),
    # A phase before access (ModSecurity, an `if` in a custom config) denied: the error page is internal.
    "error_page_before_access": (("set", False), ("reset",), ("set", True), ("access", True)),
    # `error_page 403 @named`: no server rewrite phase, so no `set`, and a fresh context.
    "named_location": (("set", False), ("access", False), ("reset",), ("access", True)),
    # `auth_request` and `ngx.location.capture`: a subrequest has a fresh context of its own.
    "subrequest": (("reset",), ("set", True), ("access", True)),
}

# What the access phase must do over each lifetime: how many times the plugin chain and the ban
# check ran, and whether the request carries the "was rewritten" mark CrowdSec reads.
EXPECTED = {
    "original": (1, False),
    "rewritten": (1, True),
    "rewritten_then_access_again": (1, True),
    "error_page_after_access": (1, False),
    "redirect_after_rewritten_access": (1, True),
    "error_page_before_access": (0, None),
    "named_location": (1, False),
    "subrequest": (0, None),
}

HARNESS = """
local set_path, access_path, steps_spec = arg[1], arg[2], arg[3]

local plugin_calls, ban_checks, builds = 0, 0, 0
local rewritten_mark = "nil"

local fake_plugin = {
    set = function() return { ret = true, msg = "ok" } end,
    access = function() plugin_calls = plugin_calls + 1 return { ret = true, msg = "ok" } end,
}
local order = { global = { set = { "p" }, access = { "p" } } }

local modules = {
    middleclass = {},
    cjson = {},
    ["bunkerweb.utils"] = {
        is_whitelisted = function() return false end,
        is_ip_whitelisted = function() return false, "ok" end,
        is_banned = function() ban_checks = ban_checks + 1 return false end,
        set_reason = function() end,
        get_deny_status = function() return 403 end,
        get_security_mode = function() return "block" end,
        save_session = function() return true, "saved" end,
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
        -- The shipped fill_ctx builds `ngx.ctx.bw` only when it is absent, and nothing else matters here.
        fill_ctx = function()
            local ctx = ngx.ctx
            if not ctx.bw then
                ctx.bw = { remote_addr = "203.0.113.9", server_name = "www.example.com" }
                builds = builds + 1
            end
            return true, "ok", nil, ctx
        end,
        export_ctx_vars = function() return true end,
        save_ctx = function() end,
        require_plugin = function() return fake_plugin end,
        new_plugin = function(plugin_lua) return true, plugin_lua end,
        call_plugin = function(plugin_obj, phase) return true, plugin_obj[phase]() end,
    },
}

local internal = false
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
    ctx = {},
    shared = { internalstore = {} },
    var = { server_name = "www.example.com" },
    req = { is_internal = function() return internal end },
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

for step in steps_spec:gmatch("[^,]+") do
    local phase, flag = step:match("^(%a+):?(%a*)$")
    if phase == "reset" then
        ngx.ctx = {}
    else
        internal = flag == "true"
        local before = plugin_calls
        assert(loadfile(phase == "set" and set_path or access_path))()
        -- The mark of the request whose access phase actually ran (the context may be reset after it).
        if plugin_calls > before then
            rewritten_mark = tostring(ngx.ctx.bw.rewritten)
        end
    end
end

print(plugin_calls .. "|" .. ban_checks .. "|" .. rewritten_mark)
"""


def env() -> Environment:
    return Environment(  # nosec B701 - NGINX configuration, exactly as Templator builds it
        loader=FileSystemLoader([CONFS.as_posix()]),
        lstrip_blocks=True,
        trim_blocks=True,
        keep_trailing_newline=True,
        undefined=Undefined,
    )


def lua_block(template: str, directive: str) -> str:
    """The body of one `*_by_lua_block`, brace-matched (a regex up to the first `}` stops inside a table)."""
    rendered = env().get_template(template).render()
    match = re.search(re.escape(directive) + r"[^\n{]*\{", rendered)
    assert match, f"{directive} not found in {template}"
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


def run(tmp_path, scenario: str):
    (tmp_path / "set.lua").write_text(lua_block("server-http/set-lua.conf", "set_by_lua_block"), encoding="utf-8")
    (tmp_path / "access.lua").write_text(lua_block("server-http/access-lua.conf", "access_by_lua_block"), encoding="utf-8")
    (tmp_path / "harness.lua").write_text(HARNESS, encoding="utf-8")
    steps = ",".join(":".join(str(part).lower() for part in step) for step in SCENARIOS[scenario])
    result = subprocess.run(
        [str(LUA), str(tmp_path / "harness.lua"), str(tmp_path / "set.lua"), str(tmp_path / "access.lua"), steps],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls, bans, rewritten = result.stdout.strip().split("|")
    return int(calls), int(bans), {"true": True, "false": False, "nil": None}[rewritten]


@needs_lua
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_the_access_phase_runs_exactly_once_for_a_request_and_never_for_an_internal_redirect(tmp_path, scenario):
    """The ban check and the plugin chain both run once or not at all: twice is a request processed
    twice, and zero for a rewritten request is the bypass."""
    calls, bans, _ = run(tmp_path, scenario)
    expected_runs = EXPECTED[scenario][0]
    assert (calls, bans) == (expected_runs, expected_runs), scenario


@needs_lua
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_only_a_rewritten_request_carries_the_rewritten_mark(tmp_path, scenario):
    """CrowdSec's `ENABLE_INTERNAL=false` skip must still apply to every genuinely internal request."""
    _, _, rewritten = run(tmp_path, scenario)
    assert rewritten == EXPECTED[scenario][1], scenario


def render_server_conf(**settings) -> str:
    context = {
        "SERVER_NAME": "www.example.com",
        "MULTISITE": "no",
        "LISTEN_HTTP": "yes",
        "USE_PROXY_PROTOCOL": "no",
        "USE_IPV6": "no",
        "DISABLE_DEFAULT_SERVER": "no",
        "IS_LOADING": "no",
        "NGINX_PREFIX": "/etc/nginx/www.example.com/",
        "USE_REVERSE_PROXY": "no",
        "LETS_ENCRYPT_PASSTHROUGH": "no",
        "REVERSE_PROXY_CUSTOM_HOST": "",
        "all": {"HTTP_PORT": "8080"},
    }
    context.update(settings)
    return env().get_template("server-http/server.conf").render(**context)


def test_the_set_phase_is_included_before_the_custom_configs():
    """A `rewrite` in a custom config ends the server rewrite phase: whatever is included after it
    never runs for that request, `set-lua.conf` included."""
    rendered = render_server_conf()
    set_at = rendered.index("set-lua.conf")
    custom_at = rendered.index("/etc/bunkerweb/configs/server-http/*.conf")
    plugins_at = rendered.index("server-http/*.conf;", custom_at + 1)
    assert set_at < custom_at < plugins_at
    assert rendered.count("set-lua.conf") == 1


def test_the_set_phase_still_follows_the_variable_defaults():
    """`set $ctx_ref ''` and the `$bw_*` defaults re-assign on every rewrite phase; the runner has to
    come after them or it exports into variables that are then blanked."""
    rendered = render_server_conf()
    assert rendered.index("set $bw_asn_org ''") < rendered.index("set-lua.conf")
    assert rendered.index("set $ctx_ref ''") < rendered.index("set-lua.conf")


@pytest.mark.parametrize(
    "settings, declared",
    [
        ({"USE_REVERSE_PROXY": "yes", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "backend.local"}, True),
        ({"USE_REVERSE_PROXY": "yes", "LETS_ENCRYPT_PASSTHROUGH": "no", "REVERSE_PROXY_CUSTOM_HOST": "backend.local"}, False),
        ({"USE_REVERSE_PROXY": "no", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "backend.local"}, False),
        ({"USE_REVERSE_PROXY": "yes", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": ""}, False),
        ({"USE_REVERSE_PROXY": "yes", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "$http_host"}, False),
        ({"USE_REVERSE_PROXY": "yes", "LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "api-$host"}, False),
    ],
)
def test_the_passthrough_host_variable_is_declared_before_the_set_phase(settings, declared):
    """letsencrypt's `set()` overwrites `$bw_reverse_proxy_host` on a passed-through ACME challenge. A
    declaration included after the set phase would put the custom host straight back."""
    rendered = render_server_conf(**settings)
    line = 'set $bw_reverse_proxy_host "backend.local";'
    assert (line in rendered) is declared
    if declared:
        assert rendered.count("set $bw_reverse_proxy_host ") == 1
        assert rendered.index(line) < rendered.index("set-lua.conf")


def test_no_plugin_include_redeclares_a_variable_the_set_phase_writes():
    """These includes now come after the set phase. A `set $x` there re-assigns what `set()` wrote:
    `$is_whitelisted` and `$bw_reverse_proxy_host` were the two such declarations."""
    written_by_set = re.compile(r"^\s*set\s+\$(is_whitelisted|bw_reverse_proxy_host|reason|reason_data|ctx_ref|bw_\w+)\b", re.M)
    offenders = [
        path.relative_to(ROOT).as_posix() for path in CORE.glob("*/confs/server-http/*.conf") if written_by_set.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_server_block_still_declares_is_whitelisted_once():
    assert render_server_conf().count("set $is_whitelisted 'no';") == 1
    assert not (CORE / "whitelist" / "confs" / "server-http" / "whitelist.conf").exists()


# --- CrowdSec: ENABLE_INTERNAL=false must still check a rewritten request -------------------------

BOUNCER = (CORE / "crowdsec" / "lib" / "bouncer.lua").read_text(encoding="utf-8")

CROWDSEC_HARNESS = """
local internal, rewritten = arg[1] == "true", arg[2] == "true"
ngx = {
  ctx = { bw = { rewritten = rewritten or nil } },
  req = { is_internal = function() return internal end },
}
runtime = { conf = { ENABLED = "true", ENABLE_INTERNAL = "false" } }
csmod = {}
%s
-- No challenge namespace: a request that is checked is refused with this message, one that is
-- skipped as internal answers `internal`. The branch under test is the one in front of it.
local ok, msg = csmod.Allow("203.0.113.9", true, nil, nil)
print(tostring(ok) .. "|" .. tostring(msg))
"""


def allow_source() -> str:
    body = re.search(r"^function csmod\.Allow\(.*?^end$", BOUNCER, re.M | re.S)
    assert body, "csmod.Allow() is gone from bouncer.lua"
    return body.group(0)


@needs_lua
@pytest.mark.parametrize(
    "internal, rewritten, outcome",
    [
        ("false", "false", "false|missing CrowdSec challenge namespace"),
        ("true", "false", "true|internal"),
        ("true", "true", "false|missing CrowdSec challenge namespace"),
    ],
)
def test_crowdsec_skips_genuinely_internal_requests_only(tmp_path, internal, rewritten, outcome):
    script = tmp_path / "allow.lua"
    script.write_text(CROWDSEC_HARNESS % allow_source(), encoding="utf-8")
    result = subprocess.run([str(LUA), str(script), internal, rewritten], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == outcome
