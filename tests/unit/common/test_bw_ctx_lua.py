"""Behaviour of ``src/bw/lua/bunkerweb/ctx.lua``, the real file run under plain Lua.

The module carries ``ngx.ctx`` from the main request into a subrequest: ``stash_ref`` records the ctx
reference in the ``$ctx_ref`` variable and ``apply_ref`` swaps the stashed table back into ``ngx.ctx``.
The OpenResty boundary is a stand-in: ``resty.core.base`` (current request, no-ctx sentinel), ``ffi`` (the
C call that returns the reference) and the Lua registry table that holds the saved contexts. ``ngx.ctx`` is
lazy like in OpenResty: reading it counts as loading it.
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("CTX", BW_MODULES / "ctx.lua")

SETUP = """
REQUEST = REQUEST == nil and {} or REQUEST   -- a test passes REQUEST = false for "no request"
FFI_REF = FFI_REF or 7
FFI_CALLS = {}
CTX_LOADS = 0
NO_CTX = -100
package.loaded["resty.core.base"] = {
    get_request = function() return REQUEST or nil end,
    FFI_NO_REQ_CTX = NO_CTX,
}
package.loaded["resty.core.ctx"] = true
package.loaded["ffi"] = {
    C = {
        ngx_http_lua_ffi_get_ctx_ref = function() FFI_CALLS[#FFI_CALLS + 1] = "http" return FFI_REF end,
        ngx_stream_lua_ffi_get_ctx_ref = function() FFI_CALLS[#FFI_CALLS + 1] = "stream" return FFI_REF end,
    },
    new = function() return {} end,
}
setmetatable(ngx, { __index = function(_, key)
    if key == "ctx" then CTX_LOADS = CTX_LOADS + 1 return { loaded_lazily = true } end
end })
debug.getregistry().ngx_lua_ctx_tables = { [7] = { marker = "saved at 7" }, [9] = { marker = "saved at 9" } }
ctx = dofile(MODULE)

local function state() return { var = ngx.var.ctx_ref, logs = LOGS, ffi = table.concat(FFI_CALLS, ","), loads = CTX_LOADS, current = rawget(ngx, "ctx") } end
"""


def run(body, **env):
    subsystem = env.pop("subsystem", "http")
    out = run_core(MODULE, SETUP + body, subsystem=subsystem, **env)
    out["logs"] = out["logs"] or []  # the JSON stand-in writes an empty Lua table as {}
    return out


class TestStashRef:
    def test_the_reference_of_the_current_ctx_is_stored_in_the_variable(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() emit(state())')
        assert out["var"] == 7
        assert out["ffi"] == "http"
        assert out["logs"] == []

    def test_an_unloaded_ngx_ctx_is_loaded_first(self):
        assert run('ngx.var.ctx_ref = "" ctx.stash_ref() emit(state())')["loads"] == 1

    def test_a_ctx_passed_in_is_not_loaded_again(self):
        assert run('ngx.var.ctx_ref = "" ctx.stash_ref({}) emit(state())')["loads"] == 0

    def test_a_second_stash_keeps_the_first_reference(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() FFI_REF = 9 ctx.stash_ref() emit(state())')
        assert out["var"] == 7
        assert out["ffi"] == "http"

    def test_an_already_stashed_reference_is_left_alone_without_loading_the_ctx(self):
        out = run('ngx.var.ctx_ref = "5" ctx.stash_ref() emit(state())')
        assert out["var"] == "5"
        assert out["ffi"] == ""
        assert out["loads"] == 0

    def test_an_undeclared_variable_is_not_stashed(self):
        out = run("ctx.stash_ref() emit(state())")
        assert out.get("var") is None
        assert out["ffi"] == ""

    def test_no_request_is_logged_and_nothing_is_stashed(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() emit(state())', REQUEST=False)
        assert out["logs"] == [["ERR", "[CTX] could not stash ngx.ctx ref: no request found"]]
        assert out["var"] == ""
        assert out["ffi"] == ""

    def test_a_request_without_a_ctx_is_logged_and_the_variable_stays_empty(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() emit(state())', FFI_REF=-100)
        assert out["logs"] == [["ERR", "[CTX] could not stash ngx.ctx ref: no ctx found"]]
        assert out["var"] == ""

    def test_the_stream_subsystem_asks_the_stream_module_for_the_reference(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() emit(state())', subsystem="stream")
        assert out["ffi"] == "stream"
        assert out["var"] == 7


class TestApplyRef:
    def test_the_saved_ctx_replaces_ngx_ctx_and_the_variable_is_cleared(self):
        out = run('ngx.var.ctx_ref = "7" ctx.apply_ref() emit(state())')
        assert out["current"] == {"marker": "saved at 7"}
        assert out["var"] == ""
        assert out["logs"] == []

    def test_the_reference_is_read_as_a_number_from_the_variable_text(self):
        assert run('ngx.var.ctx_ref = "9" ctx.apply_ref() emit(state())')["current"] == {"marker": "saved at 9"}

    def test_a_stashed_ctx_round_trips(self):
        out = run('ngx.var.ctx_ref = "" ctx.stash_ref() ngx.var.ctx_ref = tostring(ngx.var.ctx_ref) ctx.apply_ref() emit(state())')
        assert out["current"] == {"marker": "saved at 7"}
        assert out["var"] == ""

    @pytest.mark.parametrize("value", ['""', "nil"])
    def test_an_empty_or_missing_reference_changes_nothing(self, value):
        out = run(f"ngx.var.ctx_ref = {value} ctx.apply_ref() emit(state())")
        assert out.get("current") is None
        assert out["logs"] == []

    def test_a_reference_that_is_not_a_number_is_ignored_and_kept(self):
        out = run('ngx.var.ctx_ref = "abc" ctx.apply_ref() emit(state())')
        assert out.get("current") is None
        assert out["var"] == "abc"
        assert out["logs"] == []

    def test_an_unknown_reference_is_logged_and_the_variable_is_kept(self):
        out = run('ngx.var.ctx_ref = "99" ctx.apply_ref() emit(state())')
        assert out["logs"] == [["ERR", "[CTX] could not apply ngx.ctx: no ctx found"]]
        assert out.get("current") is None
        assert out["var"] == "99"

    def test_no_request_is_logged_and_the_ctx_is_not_replaced(self):
        out = run('ngx.var.ctx_ref = "7" ctx.apply_ref() emit(state())', REQUEST=False)
        assert out["logs"] == [["ERR", "[CTX] could not apply ngx.ctx: no request found"]]
        assert out.get("current") is None
        assert out["var"] == "7"
