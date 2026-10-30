"""Resizing the worker LRU from DATASTORE_LRU_SIZE must keep the bootstrap entries and never shrink the cache.

``DATASTORE_LRU_SIZE`` swapped the per-worker LRU for a new, empty one on first use: the init-time bootstrap keys written
before the setting was readable were lost and startup deadlocked. A size at or below the default also made the LRU smaller
than the bootstrap set. This test drives the real ``datastore.lua`` against a capacity-bound LRU stand-in and pins both.
Refs: #3618.
"""

import pytest
from _lua_core_helpers import run_core  # type: ignore
from _t2_helpers import BW_MODULES, LUA

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = BW_MODULES / "datastore.lua"

SETUP = r"""
-- Capacity-bound stand-in for resty.lrucache: evicts the oldest key beyond ``size``; get_keys/get/set mirror the real API.
package.preload["resty.lrucache"] = function()
    local M = {}
    M.__index = M
    function M.new(size) return setmetatable({ size = size, order = {}, vals = {}, flags = {} }, M) end
    function M:set(key, value, ttl, flags)
        if self.vals[key] == nil then
            self.order[#self.order + 1] = key
            if #self.order > self.size then self.vals[table.remove(self.order, 1)] = nil end
        end
        self.vals[key], self.flags[key] = value, flags
    end
    function M:get(key) return self.vals[key], nil, self.flags[key] end
    function M:get_keys() local ks = {} for _, k in ipairs(self.order) do if self.vals[k] ~= nil then ks[#ks + 1] = k end end return ks end
    return M
end
VARIABLES_READY, LRU_SETTING = false, "5000"
package.loaded["bunkerweb.utils"] = {
    get_variable = function(name)
        if name == "DATASTORE_LRU_SIZE" and VARIABLES_READY then return LRU_SETTING end
        return nil, "not found"
    end,
}
local datastore = dofile(MODULE)
local store = datastore:new({})
"""


def test_bootstrap_entries_written_before_the_setting_is_readable_survive_the_resize():
    out = run_core(
        MODULE,
        SETUP + r"""
for i = 1, 3 do store:set("plugin_" .. i, "bootstrap-" .. i, nil, true) end
VARIABLES_READY = true
local first_read = store:get("plugin_1", true) or "MISSING"   -- first call after the setting appears triggers the resize
local kept = {}
for i = 1, 3 do kept[i] = store:get("plugin_" .. i, true) or "MISSING" end
emit({ first = first_read, kept = kept })
""",
    )
    assert out["first"] == "bootstrap-1"
    assert out["kept"] == ["bootstrap-1", "bootstrap-2", "bootstrap-3"]


def test_a_size_at_or_below_the_default_never_shrinks_the_cache():
    out = run_core(
        MODULE,
        SETUP + r"""
LRU_SETTING = "500"
VARIABLES_READY = true
for i = 1, 800 do store:set("k" .. i, i, nil, true) end
local present = 0
for i = 1, 800 do if store:get("k" .. i, true) ~= nil then present = present + 1 end end
emit({ present = present })
""",
    )
    assert out["present"] == 800
