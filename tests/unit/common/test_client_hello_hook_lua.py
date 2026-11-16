"""Per-service TLS ClientHello hook for plugins (dev c5c0ab37e) and the ClientHello ban key (dev 961eb3adc).

A plugin that exports a module-level `client_hello(hello)` is called from `tlsdrop.hook`, i.e. from the
`ssl_client_hello_by_lua_block` of every service and of the default server, in `PLUGINS_ORDER_SSL_CLIENT_HELLO` order.
`"drop"` closes the handshake, `"detect"` only logs, anything else (or an error) lets it through. Nothing here may yield.

The harness is the one of `test_tlsdrop_lua.py`: the real `utils.lua` and `tlsdrop.lua` on plain Lua, `ngx.ssl` stubbed.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ban_lease_lua import needs_lua  # noqa: E402
from test_load_plugin import BASE, PLUGIN_PREAMBLE, _lua, _run_lua, HELPERS_LUA  # noqa: E402
from test_tlsdrop_lua import run_tls  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LANGS = ("", "de", "es", "fr", "zh")

# What the tests need on top of the tlsdrop harness: a plugin whose client_hello records its calls, and an order in
# the internalstore. `plugin(id, fn)` publishes the module the way `require(id .. "/" .. id)` finds it.
HELLO_EXTRA = r"""
local calls = {}
local function plugin(id, fn)
    package.loaded[id .. "/" .. id] = { client_hello = function(hello)
        calls[#calls + 1] = { id = id, hello = hello }
        return fn and fn(hello)
    end }
end
local function called()
    local ids = {}
    for _, call in ipairs(calls) do ids[#ids + 1] = call.id end
    return table.concat(ids, ",")
end
local function logged(level, needle)
    for _, entry in ipairs(logs) do
        if entry[1] == level and entry[2]:find(needle, 1, true) then return true end
    end
    return false
end
"""


def run_hello(body: str) -> None:
    run_tls(HELLO_EXTRA + body)


# ------------------------------------------------------------------------------------------- the contract


@needs_lua
def test_a_plugin_that_exports_client_hello_is_called_with_the_handshake():
    run_hello(r"""
plugin("p1")
assert(tlsdrop.register_client_hello_plugins({ "p1" })[1] == "p1")
assert(tlsdrop.hook("www", false, false, nil) == nil, "a plugin that says nothing lets the handshake through")
assert(called() == "p1" and #exits == 0)
local hello = calls[1].hello
assert(hello.service == "www" and hello.ip == IP, tostring(hello.ip))
assert(hello.raw == client.addr and hello.family == "inet")
assert(hello.quic == false and hello.proxy_protocol == false and hello.real_ip == false and hello.trusted == nil)
""")


@needs_lua
def test_the_default_server_hands_the_plugins_no_service():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
tlsdrop.hook(nil, false, false, nil)
assert(called() == "p1" and calls[1].hello.service == nil)
""")


@needs_lua
def test_plugins_run_in_the_order_they_were_registered_and_a_drop_ends_the_chain():
    run_hello(r"""
plugin("a"); plugin("b", function() return "drop", "flood\nnow" end); plugin("c")
assert(#tlsdrop.register_client_hello_plugins({ "a", "b", "c", "a" }) == 3, "a duplicate id registered twice")
assert(tlsdrop.hook("www", false, false, nil) == true, "the hook reports the closed handshake")
assert(called() == "a,b", called())
assert(exits[1] == ngx.ERROR and #exits == 1)
assert(logged(ngx.WARN, "plugin b dropped") and not logged(ngx.WARN, "\n"), "the reason is one log line")
""")


@needs_lua
def test_detect_only_logs_and_the_next_plugin_still_runs():
    run_hello(r"""
plugin("a", function() return "detect", "would drop" end); plugin("b")
tlsdrop.register_client_hello_plugins({ "a", "b" })
assert(tlsdrop.hook("www", false, false, nil) == nil and #exits == 0)
assert(called() == "a,b")
assert(logged(ngx.WARN, "would drop") and logged(ngx.WARN, "plugin a"))
""")


@needs_lua
def test_an_error_or_an_unknown_verdict_lets_the_handshake_through():
    run_hello(r"""
plugin("a", function() error("boom") end)
plugin("b", function() return "block", "x" end)
plugin("c", function() return true end)
plugin("d")
tlsdrop.register_client_hello_plugins({ "a", "b", "c", "d" })
assert(tlsdrop.hook("www", false, false, nil) == nil and #exits == 0)
assert(called() == "a,b,c,d", called())
assert(logged(ngx.ERR, "plugin a client_hello() failed"))
""")


@needs_lua
def test_a_failing_plugin_logs_once_a_minute_not_once_a_handshake():
    run_hello(r"""
plugin("a", function() error("boom") end)
tlsdrop.register_client_hello_plugins({ "a" })
for _ = 1, 5 do tlsdrop.hook("www", false, false, nil) end
local n = 0
for _, entry in ipairs(logs) do if entry[2]:find("client_hello() failed", 1, true) then n = n + 1 end end
assert(n == 1, n)
clock = clock + 61
tlsdrop.hook("www", false, false, nil)
n = 0
for _, entry in ipairs(logs) do if entry[2]:find("client_hello() failed", 1, true) then n = n + 1 end end
assert(n == 2, n)
""")


@needs_lua
def test_registration_keeps_only_modules_that_export_the_function():
    run_hello(r"""
plugin("good")
package.loaded["plain/plain"] = { new = function() end }          -- a plugin without client_hello
package.loaded["notfn/notfn"] = { client_hello = "yes" }          -- not a function
package.preload["broken/broken"] = function() error("syntax error in plugin") end
local ids = tlsdrop.register_client_hello_plugins({ "plain", "notfn", "missing", "broken", "good" })
assert(#ids == 1 and ids[1] == "good", table.concat(ids, ","))
assert(tlsdrop.is_client_hello_plugin("good") == true)
assert(tlsdrop.is_client_hello_plugin("plain") == false and tlsdrop.is_client_hello_plugin("missing") == false)
assert(logged(ngx.WARN, "broken"), "a module that fails to load is reported")
assert(not logged(ngx.WARN, "missing"), "a plugin without Lua code is not an error")
assert(tlsdrop.CLIENT_HELLO_PLUGIN_HOOK == 1, "plugins detect the hook through this flag")
""")


# ---------------------------------------------------------------------------- how it composes with the core drop


@needs_lua
def test_the_core_ban_drop_comes_first_and_plugins_are_not_called_for_a_dropped_client():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
ban("bans_ip_192.0.2.1", "manual", {})
assert(tlsdrop.hook("www", false, false, nil) == true and #exits == 1)
assert(called() == "", "a plugin saw a handshake the core had already closed")
""")


@needs_lua
def test_in_detect_mode_the_core_only_logs_and_the_plugins_still_run():
    run_hello(r"""
plugin("p1", function() return "drop", "ddos" end)
tlsdrop.register_client_hello_plugins({ "p1" })
ban("bans_ip_192.0.2.1", "manual", {})
internal_store.variables.global.SECURITY_MODE = "detect"
assert(tlsdrop.hook("www", false, false, nil) == true, "detect mode of the core does not stop a plugin drop")
assert(called() == "p1" and logged(ngx.WARN, "would drop banned IP"))
""")


@needs_lua
def test_plugins_run_when_the_core_drop_is_off():
    run_hello(r"""
internal_store.variables.global.BANS_TLS_DROP_REASONS = ""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
tlsdrop.hook("www", false, false, nil)
assert(called() == "p1")
""")


@needs_lua
def test_the_hook_without_plugins_does_nothing_more_than_before():
    run_hello(r"""
assert(tlsdrop.hook("www", false, false, nil) == nil and #exits == 0 and #calls == 0)
""")


# ------------------------------------------------------------------------------------- what the plugin is told


@needs_lua
def test_quic_is_flagged_and_an_unreadable_extension_skips_the_plugins():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
client.quic = "params"
tlsdrop.hook("www", false, false, nil)
assert(called() == "p1" and calls[1].hello.quic == true)
calls = {}
client.quic, client.quic_err = nil, "no such extension API"
assert(tlsdrop.hook("www", false, false, nil) == nil)
assert(#calls == 0, "an error reading the extension fails open without asking the plugins")
""")


@needs_lua
def test_an_unknown_peer_address_skips_the_plugins():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
client.addr, client.family = nil, nil
assert(tlsdrop.hook("www", false, false, nil) == nil and #calls == 0)
""")


@needs_lua
def test_behind_a_header_or_proxy_protocol_without_trusted_networks_the_ip_is_unknown():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
tlsdrop.hook("www", true, false, nil)
assert(called() == "p1" and calls[1].hello.ip == nil, "the peer is not the client here")
assert(calls[1].hello.proxy_protocol == true and calls[1].hello.real_ip == false)
""")


@needs_lua
def test_behind_a_trusted_proxy_the_ip_is_the_proxy_protocol_source_in_nginx_spelling():
    run_hello(r"""
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
client.addr = "\10\0\0\5"
client.pp = "2001:0DB8:0:0:0:0:0:1"
tlsdrop.hook("www", true, true, "10.0.0.0/8")
assert(calls[1].hello.ip == "2001:db8::1" and calls[1].hello.trusted == "10.0.0.0/8", tostring(calls[1].hello.ip))
""")


@needs_lua
def test_the_hook_never_reads_ngx_var_or_takes_a_lock_for_the_plugins():
    run_hello(r"""
ngx.var = setmetatable({}, { __index = function(_, key) error("ngx.var." .. key .. " read in ssl_client_hello") end })
plugin("p1")
tlsdrop.register_client_hello_plugins({ "p1" })
assert(tlsdrop.hook("www", false, false, nil) == nil and called() == "p1" and lock_calls == 0)
""")


# ------------------------------------------------------------------------------- the ban key (dev 961eb3adc)


@needs_lua
def test_an_ipv4_mapped_client_is_banned_and_judged_under_the_key_of_every_http_phase():
    run_tls(r"""
-- nginx leaves the peer of a dual-stack listener as ::ffff:a.b.c.d in $remote_addr, and an IPv4-mapped address is
-- its IPv4 address in every ban key (bunkerweb.ipaddr): the ClientHello reads the same identity as the HTTP phases
local NGINX_ADDR = "::ffff:192.0.2.1"
client.addr, client.family = string.rep("\0", 10) .. "\255\255\192\0\2\1", "inet6"
assert(utils.add_ban(NGINX_ADDR, "manual", 300, "www", "local", "global", {}) == true)
assert(main_store["bans_ip_192.0.2.1"] ~= nil and main_store["bans_ip_" .. NGINX_ADDR] == nil, "stored under the IPv4 identity")
assert(utils.is_banned(NGINX_ADDR, "www") == true, "the HTTP phases do not see their own ban")
local verdict, id, ip = tlsdrop.decide("www", false, false, nil)
assert(verdict == "drop" and id == "manual" and ip == "192.0.2.1", "ClientHello judged " .. tostring(ip))
assert(tlsdrop.hook("www", false, false, nil) == true and #exits == 1)
-- the dotted spelling is the same ban
assert(utils.is_banned("192.0.2.1", "www") == true)
""")


@needs_lua
def test_a_proxy_protocol_ipv4_tail_is_read_the_way_nginx_reads_it():
    run_tls(r"""
ban("bans_ip_10.1.2.3", "manual", {})
client.addr = "\10\0\0\5"
client.pp = "::ffff:010.001.002.003"
local verdict, _, ip = tlsdrop.decide("www", true, true, "10.0.0.0/8")
assert(verdict == "drop" and ip == "10.1.2.3", tostring(ip))
""")


# ------------------------------------------------------------------------- registration from the plugin order


@needs_lua
def test_the_first_handshake_of_a_worker_registers_the_plugins_of_the_order_once():
    run_hello(r"""
plugin("p1"); plugin("p2")
internal_store.plugins_order = { ssl_client_hello = { "p2", "p1" } }
tlsdrop.hook("www", false, false, nil)
assert(called() == "p2,p1", "order of PLUGINS_ORDER_SSL_CLIENT_HELLO: " .. called())
internal_store.plugins_order = { ssl_client_hello = { "p1" } }
calls = {}
tlsdrop.hook("www", false, false, nil)
assert(called() == "p2,p1", "the order is read once per worker, not per handshake")
""")


@needs_lua
def test_a_missing_order_is_retried_and_an_empty_one_is_final():
    run_hello(r"""
plugin("p1")
tlsdrop.hook("www", false, false, nil) -- no plugins_order in the internalstore yet (loading)
assert(#calls == 0)
internal_store.plugins_order = { ssl_client_hello = { "p1" } }
tlsdrop.hook("www", false, false, nil)
assert(called() == "p1", "a worker that started before the order existed never registered its plugins")
""")


@needs_lua
def test_an_order_without_the_phase_registers_nothing():
    run_hello(r"""
plugin("p1")
internal_store.plugins_order = { access = { "p1" } }
tlsdrop.hook("www", false, false, nil)
assert(#calls == 0)
""")


# --------------------------------------------------------------------------------------------- config plumbing


def test_the_phase_is_known_to_the_plugin_loader_and_the_order_machinery():
    phases = (ROOT / "src/bw/lua/bunkerweb/utils.lua").read_text(encoding="utf-8")
    get_phases = re.search(r"utils\.get_phases = function\(\).*?^end$", phases, re.S | re.M)
    assert get_phases and '"ssl_client_hello",' in get_phases.group(0)
    order = json.loads((ROOT / "src/common/core/order.json").read_text(encoding="utf-8"))
    assert order["ssl_client_hello"] == []


def test_the_order_setting_is_global_empty_by_default_and_shaped_like_its_siblings():
    settings = json.loads((ROOT / "src/common/settings.json").read_text(encoding="utf-8"))
    setting = settings["PLUGINS_ORDER_SSL_CLIENT_HELLO"]
    sibling = settings["PLUGINS_ORDER_INIT_WORKER"]
    assert setting["context"] == "global" and setting["default"] == "" and setting["type"] == "multivalue"
    assert setting["regex"] == sibling["regex"] and setting["id"] == "plugins-order-ssl-client-hello"
    assert len(setting["help"]) <= 512


def test_every_language_documents_the_order_setting_and_the_hook():
    for lang in LANGS:
        suffix = f".{lang}" if lang else ""
        readme = (ROOT / f"src/common/README{suffix}.md").read_text(encoding="utf-8")
        assert "`PLUGINS_ORDER_SSL_CLIENT_HELLO`" in readme, f"README{suffix}"
        base = ROOT / "docs" / lang if lang else ROOT / "docs"
        features = (base / "features.md").read_text(encoding="utf-8")
        assert "`PLUGINS_ORDER_SSL_CLIENT_HELLO`" in features, f"{lang or 'en'} features.md"
        plugins = (base / "plugins.md").read_text(encoding="utf-8")
        assert "client_hello(hello)" in plugins and "`ssl_client_hello`" in plugins, f"{lang or 'en'} plugins.md"


def test_the_readme_lines_and_the_generated_features_lines_agree():
    for lang in LANGS:
        suffix = f".{lang}" if lang else ""
        readme = (ROOT / f"src/common/README{suffix}.md").read_text(encoding="utf-8")
        line = next(item for item in readme.splitlines() if "PLUGINS_ORDER_INIT_WORKER" in item)
        base = ROOT / "docs" / lang if lang else ROOT / "docs"
        assert line in (base / "features.md").read_text(encoding="utf-8").splitlines(), lang or "en"


@needs_lua
def test_load_plugin_lists_the_phase_for_a_plugin_that_exports_client_hello_only():
    plugin = json.loads(json.dumps(BASE))
    plugin["stream"] = "no"
    preamble = PLUGIN_PREAMBLE.replace("--[[PLUGIN_TABLE]]", _lua(plugin))
    # the real phase list of utils.lua, so a phase missing from get_phases fails here
    phases = re.search(r"utils\.get_phases = function\(\)\s*return (\{.*?\n\t\})", (ROOT / "src/bw/lua/bunkerweb/utils.lua").read_text(encoding="utf-8"), re.S)
    assert phases
    preamble = preamble.replace("return { get_phases = function() return {} end }", "return { get_phases = function() return " + phases.group(1) + " end }")
    body = r"""
package.preload["myplug/myplug"] = function() return { new = function() end, client_hello = function() end } end
local ok, plugin_or_err = helpers.load_plugin("/plugin.json")
assert(ok, tostring(plugin_or_err))
local seen = {}
for _, phase in ipairs(plugin_or_err.phases) do seen[phase] = true end
assert(seen.ssl_client_hello, "a plugin exporting client_hello must get the ssl_client_hello phase")
assert(not seen.ssl_client_hello_default and not seen.access)

package.loaded["myplug/myplug"] = nil
package.preload["myplug/myplug"] = function() return { new = function() end, ssl_client_hello_default = function() end } end
ok, plugin_or_err = helpers.load_plugin("/plugin.json")
assert(ok, tostring(plugin_or_err))
seen = {}
for _, phase in ipairs(plugin_or_err.phases) do seen[phase] = true end
assert(seen.ssl_client_hello_default and not seen.ssl_client_hello, "the legacy method keeps its own phase")
"""
    # the harness above drops `local helpers = dofile(arg[1])` in the preamble: the body reuses it
    _run_lua(preamble + body, str(HELPERS_LUA))
