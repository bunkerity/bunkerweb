"""``helpers.order_plugins`` — origin precedence, declared order, and the sealed ``plugins_order`` key.

Three behaviours are asserted against the real Lua, driven by a stand-alone interpreter the way
``test_ban_sync.py`` does it (``package.preload`` mocks, plain Lua 5.4 — no global ``unpack``):

* the per-phase default list is PRO, then external, then core in ``order.json`` order, then the
  remaining core alphabetically — the operator's ``PLUGINS_ORDER_<PHASE>`` still has the last word;
* a plugin's own ``order`` block in ``plugin.json`` reorders that default list through a stable
  topological sort, and never hard-fails (unknown id ignored, cycle dropped, both warned about);
* ``plugins_order`` is sealed once init has written it, so a plugin can no longer rewrite the
  computed order from its ``init()`` and silently override the operator setting.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HELPERS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua"
DATASTORE_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "datastore.lua"
MIDDLECLASS_LUA = ROOT / "src" / "bw" / "lua" / "middleclass.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# KEEP IN SYNC with utils.get_phases() (src/bw/lua/bunkerweb/utils.lua) and
# Configurator.__valid_order_phases -- three hand-copies of the same list.
PHASES = [
    "init",
    "init_worker",
    "set",
    "rewrite",
    "access",
    "content",
    "ssl_client_hello_default",
    "ssl_certificate",
    "ssl_certificate_default",
    "header",
    "log",
    "preread",
    "log_stream",
    "log_default",
    "timer",
    "init_workers",
]


def _lua(value) -> str:
    """Render a Python value as a Lua literal (test fixtures only, no cycles)."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "{" + ", ".join(_lua(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{_lua(key)}] = {_lua(item)}" for key, item in value.items()) + "}"
    raise TypeError(f"no Lua literal for {value!r}")


ORDER_PREAMBLE = r"""
local ORDER_JSON = --[[ORDER_JSON]]

-- helpers.lua localises io.open and the cjson functions at load time, so both have to be
-- replaced before the module is loaded.
io.open = function(path)
    if path == "/usr/share/bunkerweb/core/order.json" then
        return { read = function() return "ORDER_JSON" end, close = function() end }
    end
    return nil, "no such file", 2
end

package.preload["cjson"] = function()
    return {
        decode = function(payload)
            if payload ~= "ORDER_JSON" then error("unexpected json payload") end
            return ORDER_JSON
        end,
        encode = function() return "<encoded>" end,
    }
end
package.preload["resty.core.base"] = function() return { get_request = function() return nil end } end
package.preload["bunkerweb.ctx"] = function() return { apply_ref = function() end, stash_ref = function() end } end
package.preload["bunkerweb.utils"] = function()
    return { get_phases = function() return --[[PHASES]] end }
end

ngx = {
    config = { subsystem = "http" },
    shared = {},
    var = {},
    req = {},
    now = function() return 0 end,
    update_time = function() end,
}

local helpers = dofile(arg[1])

local function eq(got, want, label)
    got = got or {}
    local shown = table.concat(got, ",")
    assert(#got == #want, label .. " : got " .. #got .. " ids (" .. shown .. "), want " .. #want)
    for i = 1, #want do
        assert(got[i] == want[i], label .. " : [" .. i .. "] = " .. tostring(got[i]) .. ", want " .. want[i] .. " (" .. shown .. ")")
    end
end

local function warned(warnings, needle)
    for _, warning in ipairs(warnings or {}) do
        if warning:find(needle, 1, true) then return true end
    end
    return false
end
"""


def _run_lua(chunk: str, *args: str) -> None:
    assert LUA is not None
    result = subprocess.run([LUA, "-", *args], input=chunk, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def _run_order(order_json: dict, plugins: list, variables: dict, body: str) -> None:
    preamble = ORDER_PREAMBLE.replace("--[[ORDER_JSON]]", _lua(order_json)).replace("--[[PHASES]]", _lua(PHASES))
    head = (
        f"local plugins = {_lua(plugins)}\nlocal variables = {_lua(variables)}\n"
        "local ok, orders, missing, warnings = helpers.order_plugins(plugins, variables)\nassert(ok, tostring(orders))\n"
    )
    _run_lua(preamble + head + body, str(HELPERS_LUA))


def _plugin(pid: str, phases: list, ptype: str = "core", order=None) -> dict:
    plugin = {"id": pid, "phases": phases, "type": ptype}
    if order is not None:
        plugin["order"] = order
    return plugin


@needs_lua
class TestOriginPrecedence:
    def test_pro_then_external_then_core(self):
        """PRO first, then external, then core in order.json order, then the rest alphabetically."""
        _run_order(
            {"access": ["whitelist", "blacklist"]},
            [
                _plugin("blacklist", ["access"]),
                _plugin("whitelist", ["access"]),
                _plugin("zzz_core", ["access"]),
                _plugin("aaa_core", ["access"]),
                _plugin("ext_b", ["access"], "external"),
                _plugin("ext_a", ["access"], "external"),
                _plugin("pro_b", ["access"], "pro"),
                _plugin("pro_a", ["access"], "pro"),
            ],
            {},
            'eq(orders["access"], {"pro_a", "pro_b", "ext_a", "ext_b", "whitelist", "blacklist", "aaa_core", "zzz_core"}, "access")\n',
        )

    def test_missing_type_is_treated_as_core(self):
        """A plugin table without ``type`` must not jump ahead of a real core plugin."""
        _run_order(
            {"access": ["whitelist"]},
            [
                {"id": "untyped", "phases": ["access"]},
                _plugin("whitelist", ["access"]),
                _plugin("pro_a", ["access"], "pro"),
            ],
            {},
            'eq(orders["access"], {"pro_a", "whitelist", "untyped"}, "access")\n',
        )

    def test_manifest_cannot_claim_an_origin_it_lacks(self):
        """``type`` is whatever the loader set; a core plugin listed in order.json stays core."""
        _run_order(
            {"init": ["sessions"]},
            [_plugin("sessions", ["init"]), _plugin("ext", ["init"], "external")],
            {},
            'eq(orders["init"], {"ext", "sessions"}, "init")\n',
        )


@needs_lua
class TestDeclaredOrder:
    def test_before_moves_a_plugin_up(self):
        _run_order(
            {"access": ["first", "second"]},
            [_plugin("first", ["access"]), _plugin("second", ["access"], order={"access": {"before": ["first"]}})],
            {},
            'eq(orders["access"], {"second", "first"}, "access")\nassert(#warnings == 0, "no warning expected")\n',
        )

    def test_after_moves_a_plugin_down(self):
        _run_order(
            {"access": ["first", "second"]},
            [_plugin("first", ["access"], order={"access": {"after": ["second"]}}), _plugin("second", ["access"])],
            {},
            'eq(orders["access"], {"second", "first"}, "access")\n',
        )

    def test_a_pro_plugin_can_declare_itself_after_a_core_one(self):
        """The origin default puts PRO first; the declaration is what overrides it."""
        _run_order(
            {"ssl_certificate": ["certificates"]},
            [
                _plugin("certificates", ["ssl_certificate"]),
                _plugin("acme", ["ssl_certificate"], "pro", order={"ssl_certificate": {"after": ["certificates"]}}),
            ],
            {},
            'eq(orders["ssl_certificate"], {"certificates", "acme"}, "ssl_certificate")\n',
        )

    def test_ties_keep_the_default_list_order(self):
        """Stable sort: plugins with no constraint keep their default-list position."""
        _run_order(
            {"access": ["a", "b", "c", "d"]},
            [
                _plugin("a", ["access"]),
                _plugin("b", ["access"]),
                _plugin("c", ["access"]),
                _plugin("d", ["access"], order={"access": {"before": ["c"]}}),
            ],
            {},
            'eq(orders["access"], {"a", "b", "d", "c"}, "access")\n',
        )

    def test_unknown_id_is_warned_and_ignored(self):
        # Distinctive ids on purpose: a single letter matches the warning's own prose.
        _run_order(
            {"access": ["plug_a", "plug_b"]},
            [_plugin("plug_a", ["access"], order={"access": {"before": ["ghost"]}}), _plugin("plug_b", ["access"])],
            {},
            'eq(orders["access"], {"plug_a", "plug_b"}, "access")\n'
            'assert(#warnings == 1, "exactly one warning expected, got " .. #warnings)\n'
            'assert(warned(warnings, "plugin plug_a declares order.access.before = ghost"), "warning must name plugin, phase, side and id : " .. warnings[1])\n',
        )

    def test_id_that_does_not_implement_the_phase_is_warned_and_ignored(self):
        _run_order(
            {"access": ["plug_a"], "log": ["plug_b"]},
            [_plugin("plug_a", ["access"], order={"access": {"after": ["plug_b"]}}), _plugin("plug_b", ["log"])],
            {},
            'eq(orders["access"], {"plug_a"}, "access")\n'
            'assert(#warnings == 1, "exactly one warning expected, got " .. #warnings)\n'
            'assert(warned(warnings, "plugin plug_a declares order.access.after = plug_b"), "warning must name plugin, phase, side and id : " .. warnings[1])\n',
        )

    def test_cycle_is_warned_and_dropped(self):
        _run_order(
            {"access": ["plug_a", "plug_b", "plug_c"]},
            [
                _plugin("plug_a", ["access"], order={"access": {"before": ["plug_b"]}}),
                _plugin("plug_b", ["access"], order={"access": {"before": ["plug_a"]}}),
                _plugin("plug_c", ["access"]),
            ],
            {},
            'eq(orders["access"], {"plug_a", "plug_b", "plug_c"}, "access")\n'
            'assert(#warnings == 1, "exactly one warning expected, got " .. #warnings)\n'
            'assert(warned(warnings, "between plug_a, plug_b"), "cycle warning must name both plugins : " .. warnings[1])\n',
        )

    def test_cycle_only_drops_the_offending_plugins(self):
        """A cycle between a and b must not cost c its own, perfectly valid, declaration."""
        _run_order(
            {"access": ["a", "b", "c", "d"]},
            [
                _plugin("a", ["access"], order={"access": {"before": ["b"]}}),
                _plugin("b", ["access"], order={"access": {"before": ["a"]}}),
                _plugin("c", ["access"]),
                _plugin("d", ["access"], order={"access": {"before": ["c"]}}),
            ],
            {},
            'eq(orders["access"], {"a", "b", "d", "c"}, "access")\n',
        )

    def test_cycle_warning_does_not_name_the_plugins_stuck_behind_it(self):
        """``d`` declares ``after a`` and ``before c``: it is unemittable while a<->b deadlocks, but
        it is not on the cycle. Naming it sends the operator editing an innocent manifest, and
        dropping its constraints loses an order that is satisfiable as soon as the cycle is cut."""
        # Ids are deliberately distinctive: a single letter would match the warning's own prose.
        _run_order(
            {"access": ["cyc_a", "cyc_b", "inno_c", "inno_d"]},
            [
                _plugin("cyc_a", ["access"], order={"access": {"before": ["cyc_b"]}}),
                _plugin("cyc_b", ["access"], order={"access": {"before": ["cyc_a"]}}),
                _plugin("inno_c", ["access"]),
                _plugin("inno_d", ["access"], order={"access": {"after": ["cyc_a"], "before": ["inno_c"]}}),
            ],
            {},
            'eq(orders["access"], {"cyc_a", "cyc_b", "inno_d", "inno_c"}, "access")\n'
            'assert(#warnings == 1, "exactly one cycle warning expected, got " .. #warnings)\n'
            'assert(warnings[1]:find("cyc_a, cyc_b", 1, true), "the warning must name the cycle : " .. warnings[1])\n'
            'assert(not warnings[1]:find("inno_c", 1, true), "the warning must not name inno_c : " .. warnings[1])\n'
            'assert(not warnings[1]:find("inno_d", 1, true), "the warning must not name inno_d : " .. warnings[1])\n',
        )

    def test_both_alias_spellings_are_merged_not_overwritten(self):
        """Lua randomises the string hash seed, so a last-writer-wins merge would drop a different
        declaration on every restart."""
        # Fixture order matters: with h1,h2,h3 the merged result and the "header wins" result are
        # the same list, so the test would pass ~45% of the time against the unfixed code. With
        # h1,h3,h2 the three outcomes are merged=h2,h3,h1 / header=h3,h1,h2 / headers=h1,h2,h3.
        _run_order(
            {"headers": ["h1", "h3", "h2"]},
            [
                _plugin("h1", ["header"]),
                _plugin("h2", ["header"]),
                _plugin("h3", ["header"], order={"header": {"before": ["h1"]}, "headers": {"after": ["h2"]}}),
            ],
            {},
            'eq(orders["header"], {"h2", "h3", "h1"}, "header")\n',
        )

    def test_self_reference_is_a_cycle_not_a_crash(self):
        _run_order(
            {"access": ["a", "b"]},
            [_plugin("a", ["access"], order={"access": {"before": ["a"]}}), _plugin("b", ["access"])],
            {},
            'eq(orders["access"], {"a", "b"}, "access")\nassert(#warnings > 0, "a self reference must warn")\n',
        )

    def test_headers_alias_targets_the_header_phase(self):
        _run_order(
            {"headers": ["headers", "cors"]},
            [_plugin("headers", ["header"]), _plugin("cors", ["header"], order={"headers": {"before": ["headers"]}})],
            {},
            'eq(orders["header"], {"cors", "headers"}, "header")\n',
        )

    def test_unknown_phase_key_is_ignored(self):
        _run_order(
            {"access": ["a", "b"]},
            [_plugin("a", ["access"], order={"not_a_phase": {"before": ["b"]}}), _plugin("b", ["access"])],
            {},
            'eq(orders["access"], {"a", "b"}, "access")\n',
        )

    def test_malformed_block_never_refuses_the_plugin(self):
        """Python warns and drops a malformed ``order``; Lua must simply ignore it."""
        _run_order(
            {"access": ["a", "b"]},
            [{"id": "a", "phases": ["access"], "type": "core", "order": "nonsense"}, _plugin("b", ["access"])],
            {},
            'eq(orders["access"], {"a", "b"}, "access")\n',
        )


@needs_lua
class TestWildcardOrder:
    """``"*"`` inside a declared ``before``/``after`` list -- lane PLUG-ORDER-b. Means "every other
    plugin implementing this phase that is not itself constrained relative to me", so a core
    dependency head (``sessions``, ``ssl``, ``whitelist``, ...) can pin itself to the front of a
    phase without a numeric priority or a new manifest key."""

    def test_before_star_moves_a_plugin_to_the_front(self):
        _run_order(
            {"access": ["a", "b", "c"]},
            [
                _plugin("a", ["access"]),
                _plugin("b", ["access"]),
                _plugin("c", ["access"], order={"access": {"before": ["*"]}}),
            ],
            {},
            'eq(orders["access"], {"c", "a", "b"}, "access")\n',
        )

    def test_after_star_moves_a_plugin_to_the_back(self):
        _run_order(
            {"access": ["a", "b", "c"]},
            [
                _plugin("a", ["access"], order={"access": {"after": ["*"]}}),
                _plugin("b", ["access"]),
                _plugin("c", ["access"]),
            ],
            {},
            'eq(orders["access"], {"b", "c", "a"}, "access")\n',
        )

    def test_two_before_star_plugins_keep_the_default_list_order(self):
        """Both want to be first : nothing to arbitrate between them, so no edge is added and the
        default list order (origin bucket, then order.json, then alphabetical) stands."""
        _run_order(
            {"access": ["x", "y", "z"]},
            [
                _plugin("z", ["access"]),
                _plugin("x", ["access"], order={"access": {"before": ["*"]}}),
                _plugin("y", ["access"], order={"access": {"before": ["*"]}}),
            ],
            {},
            'eq(orders["access"], {"x", "y", "z"}, "access")\nassert(#warnings == 0, "no warning expected")\n',
        )

    def test_two_after_star_plugins_keep_the_default_list_order(self):
        """``x`` and ``y`` both want to be last : nothing to arbitrate between them, so no edge is
        added between them and their default-list order is kept -- but ``z``, unconstrained, is
        still pulled in front of both (that is what ``after *`` means)."""
        _run_order(
            {"access": ["x", "y", "z"]},
            [
                _plugin("x", ["access"], order={"access": {"after": ["*"]}}),
                _plugin("y", ["access"], order={"access": {"after": ["*"]}}),
                _plugin("z", ["access"]),
            ],
            {},
            'eq(orders["access"], {"z", "x", "y"}, "access")\n',
        )

    def test_before_star_vs_after_star_pair_is_trivially_consistent(self):
        """Both independently want the same edge (p before q), so it is added without conflict."""
        _run_order(
            {"access": ["m"]},
            [
                _plugin("m", ["access"]),
                _plugin("p", ["access"], order={"access": {"before": ["*"]}}),
                _plugin("q", ["access"], order={"access": {"after": ["*"]}}),
            ],
            {},
            'eq(orders["access"], {"p", "m", "q"}, "access")\n',
        )

    def test_explicit_before_beats_a_wildcard(self):
        """A plugin declaring ``before: [<pinned id>]`` still wins over the pinned plugin's own
        ``before: ["*"]`` -- explicit beats wildcard. ``plain`` has no declaration at all and is
        the discriminator : it sits ahead of ``pin`` in the default list, and only ``pin``'s
        wildcard (correctly honoured) pulls it behind -- a build that treats ``"*"`` as inert
        would leave it in front, same as an unfixed baseline."""
        _run_order(
            {"access": ["plain", "pin", "rebel"]},
            [
                _plugin("plain", ["access"]),
                _plugin("pin", ["access"], order={"access": {"before": ["*"]}}),
                _plugin("rebel", ["access"], order={"access": {"before": ["pin"]}}),
            ],
            {},
            'eq(orders["access"], {"rebel", "pin", "plain"}, "access")\n',
        )

    def test_wildcard_is_never_reported_as_a_missing_id(self):
        _run_order(
            {"access": ["a", "b"]},
            [_plugin("a", ["access"], order={"access": {"before": ["*"]}}), _plugin("b", ["access"])],
            {},
            'eq(orders["access"], {"a", "b"}, "access")\nassert(#warnings == 0, "the wildcard itself must never warn")\n',
        )

    def test_wildcard_contradicted_by_an_explicit_opposite_id_warns_once_and_drops(self):
        """A plugin declaring both ``before: ["*"]`` and ``after: [x]`` for the same phase
        contradicts itself : ``id -> x`` from the wildcard, ``x -> id`` from the explicit
        ``after``. The existing cycle machinery catches it -- no separate wildcard check needed."""
        _run_order(
            {"access": ["plug_a", "plug_x"]},
            [
                _plugin("plug_a", ["access"], order={"access": {"before": ["*"], "after": ["plug_x"]}}),
                _plugin("plug_x", ["access"]),
            ],
            {},
            'eq(orders["access"], {"plug_a", "plug_x"}, "access")\n'
            'assert(#warnings == 1, "exactly one cycle warning expected, got " .. #warnings)\n'
            'assert(warned(warnings, "between plug_a, plug_x"), "the contradiction must be reported as a cycle : " .. warnings[1])\n',
        )

    def test_pinned_core_heads_hold_against_an_unadapted_pro_bundle(self):
        """The brief's required proof : a fake PRO set {acme, antiddos, ldap, openidc, saml}
        implementing access/init/header, none of them adapted (no ``order`` block of their own).
        The pinned core heads (``sessions``, ``ssl``/``whitelist``, ``headers``/``cors``/
        ``antibot``/``misc``) keep the 1.6/order.json order among themselves, the PRO plugins
        follow the pinned heads (alphabetically, the default-list tie-break) and precede the
        remaining, unpinned core plugins."""
        order_json = {
            "init": ["sessions", "whitelist", "blacklist"],
            "access": ["ssl", "whitelist", "letsencrypt", "blacklist", "greylist"],
            "headers": ["headers", "cors", "antibot", "misc"],
        }
        pro_ids = ["acme", "antiddos", "ldap", "openidc", "saml"]
        plugins = [_plugin(pid, ["access", "init", "header"], "pro") for pid in pro_ids]
        plugins += [
            _plugin("sessions", ["init"], order={"init": {"before": ["*"]}}),
            _plugin("ssl", ["access"], order={"access": {"before": ["*"]}}),
            _plugin("whitelist", ["access", "init"], order={"access": {"before": ["*"]}}),
            _plugin("letsencrypt", ["access"], order={"access": {"before": ["*"]}}),
            _plugin("blacklist", ["access", "init"]),
            _plugin("greylist", ["access"]),
            _plugin("headers", ["header"], order={"header": {"before": ["*"]}}),
            _plugin("cors", ["header"], order={"header": {"before": ["*"]}}),
            _plugin("antibot", ["header"], order={"header": {"before": ["*"]}}),
            _plugin("misc", ["header"], order={"header": {"before": ["*"]}}),
        ]
        _run_order(
            order_json,
            plugins,
            {},
            'eq(orders["access"], {"ssl", "whitelist", "letsencrypt", '
            '"acme", "antiddos", "ldap", "openidc", "saml", "blacklist", "greylist"}, "access")\n'
            'eq(orders["init"], {"sessions", '
            '"acme", "antiddos", "ldap", "openidc", "saml", "whitelist", "blacklist"}, "init")\n'
            'eq(orders["header"], {"headers", "cors", "antibot", "misc", '
            '"acme", "antiddos", "ldap", "openidc", "saml"}, "header")\n',
        )


@needs_lua
class TestOperatorOverrideStillWins:
    def test_override_beats_origin_and_declaration(self):
        _run_order(
            {"access": ["core_a"]},
            [
                _plugin("core_a", ["access"]),
                _plugin("pro_a", ["access"], "pro", order={"access": {"before": ["core_a"]}}),
            ],
            {"global": {"PLUGINS_ORDER_ACCESS": "core_a"}},
            'eq(orders["access"], {"core_a", "pro_a"}, "access")\n',
        )

    def test_per_site_override_is_unchanged(self):
        _run_order(
            {"access": ["core_a"]},
            [_plugin("core_a", ["access"]), _plugin("pro_a", ["access"], "pro")],
            {"global": {}, "www.example.com": {"PLUGINS_ORDER_ACCESS": "core_a"}},
            'eq(orders["access"], {"pro_a", "core_a"}, "global access")\n'
            'eq(orders.per_site["www.example.com"]["access"], {"core_a", "pro_a"}, "per site access")\n',
        )

    def test_unknown_override_id_is_still_reported_as_missing(self):
        _run_order(
            {"access": ["core_a"]},
            [_plugin("core_a", ["access"])],
            {"global": {"PLUGINS_ORDER_ACCESS": "ghost core_a"}},
            'eq(orders["access"], {"core_a"}, "access")\nassert(missing.global["access"]["ghost"], "ghost must be reported missing")\n',
        )


SEAL_PREAMBLE = r"""
package.preload["middleclass"] = function() return dofile(arg[2]) end

local logs = {}
package.preload["bunkerweb.logger"] = function()
    return { new = function(_, _) return { log = function(_, _, message) table.insert(logs, message) end } end }
end

package.preload["resty.lrucache"] = function()
    return {
        new = function()
            local store, flags = {}, {}
            return {
                -- resty.lrucache returns value, stale_value, flags and takes (key, value, ttl, flags).
                get = function(_, key) return store[key], nil, flags[key] end,
                set = function(_, key, value, _, flag) store[key], flags[key] = value, flag end,
                delete = function(_, key) store[key], flags[key] = nil, nil end,
                flush_all = function() store, flags = {}, {} end,
                get_keys = function()
                    local keys = {}
                    for key in pairs(store) do keys[#keys + 1] = key end
                    return keys
                end,
            }
        end,
    }
end

package.preload["bunkerweb.utils"] = function() return { get_variable = function() return nil end } end

ngx = {
    ERR = 3,
    WARN = 4,
    config = { subsystem = "http" },
    shared = { datastore = {}, internalstore = {} },
    time = function() return 0 end,
}

local cdatastore = dofile(arg[1])
STORE = cdatastore:new(ngx.shared.internalstore)

local function logged(needle)
    for _, message in ipairs(logs) do
        if message:find(needle, 1, true) then return true end
    end
    return false
end
"""


def _run_seal(body: str, *extra: str) -> None:
    _run_lua(SEAL_PREAMBLE + body, str(DATASTORE_LUA), str(MIDDLECLASS_LUA), *extra)


@needs_lua
class TestPluginsOrderSeal:
    def test_init_write_then_seal_then_refusal(self):
        _run_seal("""
local ok = STORE:set("plugins_order", "from-init", nil, true)
assert(ok, "the init write must succeed")
STORE.class.seal("plugins_order")
local refused, err = STORE:set("plugins_order", "from-plugin", nil, true)
assert(refused == false, "a post-init write must be refused")
assert(err and err ~= "success", "the refusal must carry an error")
assert(STORE:get("plugins_order", true) == "from-init", "the init value must survive")
assert(logged("plugins_order"), "the refusal must be logged with the key")
""")

    def test_other_keys_are_untouched(self):
        _run_seal("""
STORE:set("plugins_order", "from-init", nil, true)
assert(STORE.class.seal("plugins_order"))
assert(STORE:set("variables", "v", nil, true), "an unsealed key must still be writable")
assert(STORE:get("variables", true) == "v")
""")

    def test_delete_of_a_sealed_key_is_refused(self):
        """Otherwise the refusal is one ``delete`` away from being pointless."""
        _run_seal("""
STORE:set("plugins_order", "from-init", nil, true)
STORE.class.seal("plugins_order")
local refused = STORE:delete("plugins_order", true)
assert(refused == false, "deleting a sealed key must be refused")
assert(STORE:get("plugins_order", true) == "from-init")
""")

    def test_delete_all_skips_a_sealed_key(self):
        """``delete_all`` is a pattern sweep that bypasses ``delete`` -- ``^plugin`` matches
        ``plugins_order`` too, so the seal has to reach it as well."""
        _run_seal("""
STORE:set("plugins_order", "from-init", nil, true)
STORE:set("plugin_misc", "meta", nil, true)
STORE.class.seal("plugins_order")
assert(STORE:delete_all("^plugin", true))
assert(STORE:get("plugins_order", true) == "from-init", "the sealed key must survive the sweep")
assert(STORE:get("plugin_misc", true) == nil, "the sweep must still delete everything else")
""")

    def test_shared_dict_write_is_refused_too(self):
        _run_seal("""
STORE:set("plugins_order", "from-init", nil, true)
assert(STORE.class.seal("plugins_order"))
local refused = STORE:set_with_retries("plugins_order", "x")
assert(refused == false, "set_with_retries must honour the seal")
""")

    def test_flush_lru_preserves_a_sealed_key(self):
        """Losing ``plugins_order`` fails OPEN: every phase runner bails out of the whole phase
        when the read misses, so a flush would be a wider hole than the write the seal refuses."""
        _run_seal("""
STORE:set("plugins_order", "from-init", nil, true)
STORE:set("variables", "v", nil, true)
STORE.class.seal("plugins_order")
assert(STORE:flush_lru())
assert(STORE:get("plugins_order", true) == "from-init", "the sealed key must survive the flush")
assert(STORE:get("variables", true) == nil, "the flush must still clear everything else")
""")

    def test_seal_refuses_a_key_that_holds_nothing(self):
        """Plugin chunks are required during init_by_lua, before the order is computed: sealing an
        absent key would make init's own write fail and leave the instance with no order at all."""
        _run_seal("""
assert(STORE.class.seal("plugins_order") == false, "sealing an absent key must be refused")
assert(STORE:set("plugins_order", "from-init", nil, true), "init must still be able to write")
assert(STORE.class.seal("plugins_order") == true, "sealing a written key must work")
""")

    def test_refusal_names_the_calling_plugin(self, tmp_path):
        """``<id>/<id>.lua`` is how a plugin's Lua half is required, so the stack names it."""
        plugin_dir = tmp_path / "acme"
        plugin_dir.mkdir()
        (plugin_dir / "acme.lua").write_text('STORE:set("plugins_order", "hijacked", nil, true)\n')
        _run_seal(
            """
STORE:set("plugins_order", "from-init", nil, true)
STORE.class.seal("plugins_order")
dofile(arg[3])
assert(STORE:get("plugins_order", true) == "from-init", "the hijack must not land")
assert(logged("acme"), "the refusal must name the calling plugin")
""",
            str(plugin_dir / "acme.lua"),
        )
