"""Behaviour of ``src/bw/lua/bunkerweb/mmdb.lua``, the real file run under plain Lua.

The module opens the country and ASN databases the jobs write under ``/var/cache/bunkerweb/jobs`` and hands
the handles to callers (``utils.get_country`` / ``get_asn``). ``geoip.mmdb`` is the OS boundary: a stand-in
whose ``load_database`` serves in-memory databases by path and returns ``nil, err`` for a missing file the
way the real loader does.
"""

import pytest
from _lua_core_helpers import BW_MODULES, LUA, module_path, run_core  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("MMDB", BW_MODULES / "mmdb.lua")

COUNTRY = "/var/cache/bunkerweb/jobs/country.mmdb"
ASN = "/var/cache/bunkerweb/jobs/asn.mmdb"

GEOIP = """
LOADED = {}
local function database(rows)
    return { lookup = function(_, ip)
        local row = rows[ip]
        if row == nil then return nil, "invalid ip " .. ip end
        return row
    end }
end
DATABASES = {
    [COUNTRY] = database({ ["1.1.1.1"] = { country = { iso_code = "AU" } } }),
    [ASN] = database({ ["1.1.1.1"] = { autonomous_system_number = 13335 } }),
}
package.loaded["geoip.mmdb"] = {
    load_database = function(path)
        LOADED[#LOADED + 1] = path
        local db = DATABASES[path]
        if not db then return nil, "no such file " .. path end
        return db
    end,
}
"""


def run(body, **env):
    return run_core(MODULE, GEOIP + body, COUNTRY=COUNTRY, ASN=ASN, **env)


class TestLoading:
    def test_both_databases_are_opened_from_the_jobs_cache(self):
        assert sorted(run("dofile(MODULE) emit(LOADED)")) == sorted([COUNTRY, ASN])

    def test_each_handle_serves_its_own_database(self):
        out = run("""
local mmdb = dofile(MODULE)
emit({ country = mmdb.country_db:lookup("1.1.1.1"), asn = mmdb.asn_db:lookup("1.1.1.1") })
""")
        assert out == {"country": {"country": {"iso_code": "AU"}}, "asn": {"autonomous_system_number": 13335}}

    def test_a_lookup_error_reaches_the_caller_untouched(self):
        out = run("""
local mmdb = dofile(MODULE)
local row, err = mmdb.country_db:lookup("9.9.9.9")
emit({ row = row == nil, err = err })
""")
        assert out == {"row": True, "err": "invalid ip 9.9.9.9"}


class TestMissingDatabase:
    def test_a_missing_country_database_leaves_only_that_handle_nil(self):
        out = run("""
DATABASES[COUNTRY] = nil
local mmdb = dofile(MODULE)
emit({ country = mmdb.country_db == nil, asn = mmdb.asn_db ~= nil })
""")
        assert out == {"country": True, "asn": True}

    def test_a_missing_asn_database_leaves_only_that_handle_nil(self):
        out = run("""
DATABASES[ASN] = nil
local mmdb = dofile(MODULE)
emit({ country = mmdb.country_db ~= nil, asn = mmdb.asn_db == nil })
""")
        assert out == {"country": True, "asn": True}

    def test_no_database_at_all_still_loads_the_module(self):
        out = run("""
DATABASES = {}
local mmdb = dofile(MODULE)
emit({ country = mmdb.country_db == nil, asn = mmdb.asn_db == nil })
""")
        assert out == {"country": True, "asn": True}
