"""``helpers.load_plugin`` -- the manifest caps shared with ``Configurator.__validate_plugin``.

PX-A §2.2 : Python refused a malformed manifest (bad id, name > 128, description > 256, bad
version, bad stream, malformed settings incl. ``help`` > 512) and dropped the whole plugin, while
this Lua loader only checked that six fields *existed* -- so the plugin kept being ordered and
executed by NGINX with its settings/jobs/templates gone. This wave: the same fixtures are refused
here too, naming the same failing field, driven by a stand-alone interpreter the way
``test_ban_sync.py`` / ``test_order_plugins.py`` do it (``package.preload`` mocks, plain Lua 5.4).

``extensions`` stays Python-only (Lua never reads it) and jobs are not re-validated here (Python
already owns job dispatch) -- out of scope for this fixture set, by design (see the brief).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HELPERS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _lua(value) -> str:
    """Render a Python value as a Lua literal (test fixtures only, no cycles)."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        # ensure_ascii=False : a non-ASCII fixture must reach Lua as literal UTF-8 bytes, not a
        # \uXXXX escape -- Lua's string literals don't understand that JS/JSON-style escape.
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "{" + ", ".join(_lua(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{_lua(key)}] = {_lua(item)}" for key, item in value.items()) + "}"
    raise TypeError(f"no Lua literal for {value!r}")


PLUGIN_PREAMBLE = r"""
local PLUGIN_TABLE = --[[PLUGIN_TABLE]]

-- helpers.lua localises io.open and the cjson functions at load time, so both have to be
-- replaced before the module is loaded.
io.open = function(path)
    if path == "/plugin.json" then
        return { read = function() return "PLUGIN_JSON" end, close = function() end }
    end
    return nil, "no such file", 2
end

package.preload["cjson"] = function()
    return {
        decode = function(payload)
            if payload ~= "PLUGIN_JSON" then error("unexpected json payload") end
            return PLUGIN_TABLE
        end,
        encode = function(value)
            local parts = {}
            for _, item in ipairs(value) do
                table.insert(parts, tostring(item))
            end
            return "[" .. table.concat(parts, ",") .. "]"
        end,
    }
end
package.preload["resty.core.base"] = function() return { get_request = function() return nil end } end
package.preload["bunkerweb.ctx"] = function() return { apply_ref = function() end, stash_ref = function() end } end
package.preload["bunkerweb.utils"] = function()
    return { get_phases = function() return {} end }
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

local ok, plugin_or_err = helpers.load_plugin("/plugin.json")
"""


# A raw variant for the two cases the PLUGIN_TABLE machinery can't express: `cjson.decode` itself
# failing (malformed JSON) or succeeding with something that isn't a table (a scalar/boolean
# top-level JSON value). `--[[DECODE_BODY]]` is the body of the mocked `decode` function.
RAW_PREAMBLE = r"""
io.open = function(path)
    if path == "/plugin.json" then
        return { read = function() return "PLUGIN_JSON" end, close = function() end }
    end
    return nil, "no such file", 2
end

package.preload["cjson"] = function()
    return {
        decode = function(payload)
            --[[DECODE_BODY]]
        end,
        encode = function(value) return "[]" end,
    }
end
package.preload["resty.core.base"] = function() return { get_request = function() return nil end } end
package.preload["bunkerweb.ctx"] = function() return { apply_ref = function() end, stash_ref = function() end } end
package.preload["bunkerweb.utils"] = function()
    return { get_phases = function() return {} end }
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

local ok, plugin_or_err = helpers.load_plugin("/plugin.json")
"""


def _run_lua(chunk: str, *args: str) -> None:
    assert LUA is not None
    result = subprocess.run([LUA, "-", *args], input=chunk, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def _run_load_plugin(plugin: dict, body: str) -> None:
    preamble = PLUGIN_PREAMBLE.replace("--[[PLUGIN_TABLE]]", _lua(plugin))
    _run_lua(preamble + body, str(HELPERS_LUA))


def _run_load_plugin_raw(decode_body: str, body: str) -> None:
    preamble = RAW_PREAMBLE.replace("--[[DECODE_BODY]]", decode_body)
    _run_lua(preamble + body, str(HELPERS_LUA))


SETTING = {"context": "multisite", "default": "x", "help": "h", "id": "MY_SETTING", "label": "l", "regex": "^.*$", "type": "text"}

BASE = {
    "id": "myplug",
    "name": "My",
    "description": "d",
    "version": "1.0",
    "stream": "no",
    "settings": {"MY_SETTING": dict(SETTING)},
}


def _with_setting(**overrides) -> dict:
    plugin = json.loads(json.dumps(BASE))
    plugin["settings"]["MY_SETTING"].update(overrides)
    return plugin


def _refused(plugin: dict, needle: str) -> None:
    _run_load_plugin(
        plugin,
        f'assert(not ok, "expected refusal")\n' f"assert(plugin_or_err:find({_lua(needle)}, 1, true), plugin_or_err)\n",
    )


@needs_lua
class TestValidManifestLoads:
    def test_base_plugin_loads(self):
        _run_load_plugin(
            BASE,
            "assert(ok, tostring(plugin_or_err))\n" 'assert(plugin_or_err.id == "myplug", plugin_or_err.id)\n',
        )


@needs_lua
class TestMissingFieldsStillRefuses:
    """Pre-existing behaviour (six required fields) -- must keep working alongside the new caps."""

    def test_missing_field(self):
        plugin = dict(BASE)
        del plugin["stream"]
        _refused(plugin, "missing field(s)")


@needs_lua
class TestMalformedJsonIsRefusedNotFatal:
    """Criticos round 2, N1/N2 : both PRE-DATE this lane's manifest caps but sit one and two lines
    above them, in this lane's glob, and are far more likely in the field than a numeric `id` --
    a truncated or corrupt plugin.json, or a manifest whose top-level JSON value is a scalar. Both
    used to crash `load_plugin`, which runs inside `init_by_lua_block` with no `pcall` around the
    call site (`init-lua.conf`/`init-stream-lua.conf`) -- fatal to NGINX startup, not a dropped
    plugin."""

    def test_decode_error_is_refused_not_fatal(self):
        """N1 : `decode` erroring used to crash on `.. err` (a stale, always-nil local from the
        earlier io.open call) instead of the pcall's actual error message."""
        _run_load_plugin_raw(
            'error("bad json")',
            'assert(not ok, "expected refusal")\n' 'assert(plugin_or_err:find("invalid JSON", 1, true), plugin_or_err)\n',
        )

    def test_scalar_manifest_is_refused_not_fatal(self):
        """N2 : a top-level JSON value that isn't an object (`123`, `true`, `null`) decodes fine
        but crashed the very next line, which indexes it like a table."""
        _run_load_plugin_raw(
            "return 123",
            'assert(not ok, "expected refusal")\n' 'assert(plugin_or_err:find("is not an object", 1, true), plugin_or_err)\n',
        )


@needs_lua
class TestPluginLevelCaps:
    def test_invalid_id_characters(self):
        _refused(dict(BASE, id="bad id!"), "id of plugin")

    def test_id_too_long(self):
        _refused(dict(BASE, id="a" * 65), "id of plugin")

    def test_name_too_long(self):
        _refused(dict(BASE, name="a" * 129), "name of plugin myplug is 129 bytes, max 128")

    def test_description_too_long(self):
        _refused(dict(BASE, description="a" * 257), "description of plugin myplug is 257 bytes, max 256")

    def test_invalid_version(self):
        _refused(dict(BASE, version="not-a-version"), "version of plugin myplug")

    def test_invalid_stream(self):
        _refused(dict(BASE, stream="maybe"), "stream of plugin myplug is maybe")

    def test_id_with_trailing_newline_is_refused(self):
        """C2 : Lua's anchored pattern never lets a trailing newline through the way Python's
        ``$`` used to -- this fixture is the mirror of the Python-side regression test."""
        _refused(dict(BASE, id="myplug\n"), "id of plugin")

    def test_id_with_non_ascii_is_refused(self):
        """C2 : Lua's ``%w`` is ASCII-only -- this must refuse just like Python now does."""
        _refused(dict(BASE, id="pluginé"), "id of plugin")

    def test_name_length_is_measured_in_utf8_bytes(self):
        """C3 : 65 "e"-with-acute characters are 130 UTF-8 bytes -- Lua's ``#`` already counted
        bytes, this asserts Python agrees (see the Python-side sibling test)."""
        _refused(dict(BASE, name="é" * 65), "130 bytes, max 128")


@needs_lua
class TestPerSettingCaps:
    def test_missing_key(self):
        plugin = _with_setting()
        del plugin["settings"]["MY_SETTING"]["help"]
        _refused(plugin, "setting MY_SETTING of plugin myplug is missing key(s) help")

    def test_invalid_setting_id(self):
        plugin = _with_setting()
        plugin["settings"]["not valid"] = plugin["settings"].pop("MY_SETTING")
        _refused(plugin, "id of setting not valid of plugin myplug is invalid")

    def test_invalid_context(self):
        _refused(_with_setting(context="nowhere"), "context of setting MY_SETTING of plugin myplug is nowhere")

    def test_default_too_long(self):
        _refused(_with_setting(default="a" * 4097), "default of setting MY_SETTING of plugin myplug is 4097 bytes, max 4096")

    def test_help_too_long(self):
        """The exact regression from PX-A §2.2 : an over-long ``help`` string -- the same fixture
        as the Python side's ``test_help_too_long`` (640 chars), refused here too."""
        _refused(_with_setting(help="a" * 640), "help of setting MY_SETTING of plugin myplug is 640 bytes, max 512")

    def test_help_length_is_measured_in_utf8_bytes(self):
        """C3 : same non-ASCII byte-vs-char gap as the plugin name, on the setting side."""
        _refused(_with_setting(help="é" * 300), "600 bytes, max 512")

    def test_label_too_long(self):
        _refused(_with_setting(label="a" * 257), "label of setting MY_SETTING of plugin myplug is 257 bytes, max 256")

    def test_regex_too_long(self):
        _refused(_with_setting(regex="a" * 1025), "regex of setting MY_SETTING of plugin myplug is 1025 bytes, max 1024")

    def test_invalid_type(self):
        _refused(_with_setting(type="not-a-type"), "type of setting MY_SETTING of plugin myplug is not-a-type")


@needs_lua
class TestNonStringFieldsAreRefusedNotFatal:
    """C1 (blocker) : ``load_plugin`` runs inside ``init_by_lua_block`` (init-lua.conf), which has
    no ``pcall`` around it -- an uncaught Lua error here is fatal to NGINX startup, not a single
    dropped plugin the way an unexpected Python type is (caught by ``__load_plugin``'s
    ``except BaseException``). Every field the manifest caps index or measure must be type-checked
    before that happens."""

    def test_numeric_id_is_refused_not_fatal(self):
        _refused(dict(BASE, id=12345), "id of plugin")

    def test_numeric_name_is_refused_not_fatal(self):
        _refused(dict(BASE, name=129), "name of plugin myplug must be a string")

    def test_numeric_version_is_refused_not_fatal(self):
        _refused(dict(BASE, version=1.0), "version of plugin myplug must be a string")

    def test_settings_as_a_list_is_refused_not_fatal(self):
        """A JSON array decodes to a Lua table with integer keys, not setting ids."""
        _refused(dict(BASE, settings=["not", "an", "object"]), "settings of plugin myplug must be an object")

    def test_setting_value_not_an_object_is_refused_not_fatal(self):
        _refused(dict(BASE, settings={"MY_SETTING": "not-an-object"}), "setting MY_SETTING of plugin myplug must be an object")

    def test_numeric_setting_default_is_refused_not_fatal(self):
        _refused(_with_setting(default=0), "default of setting MY_SETTING of plugin myplug must be a string")
