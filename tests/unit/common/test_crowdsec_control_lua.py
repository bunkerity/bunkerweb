"""Control requests validate locally before reaching the Local API."""

from pathlib import Path
import shutil
import subprocess

import pytest

from test_crowdsec_init_health_lua import field, run

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/crowdsec/crowdsec.lua"
BOUNCER = ROOT / "src/common/core/crowdsec/lib/bouncer.lua"
CONTROL = ROOT / "src/common/core/crowdsec/control.lua"


def test_control_delegates_to_dev_layout():
    assert CONTROL.exists()
    assert not (CONTROL.parent / "lib/control.lua").exists()
    assert "function control.run" in CONTROL.read_text()
    assert 'local http = require "resty.http"' in CONTROL.read_text()
    assert 'return require("crowdsec.control").run(runtime.conf, runtime.cache, action, params)' in BOUNCER.read_text()


def test_api_routes_all_six_operations():
    source = PLUGIN.read_text()
    for operation in ("connections", "decisions", "alerts", "unban", "allowlists", "allowlistcheck"):
        assert f'operation == "{operation}"' in source


def test_plugin_api_forwards_structured_control_data():
    api = (ROOT / "src/bw/lua/bunkerweb/api.lua").read_text()
    plugin_dispatch = api.split('ok, ret = call_plugin(plugin_obj, "api")', 1)[1]
    assert 'resp["data"] = ret.data' in plugin_dispatch


@pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")
def test_control_rejects_invalid_input_without_an_http_client():
    script = f"""
package.loaded["cjson.safe"] = {{ new = function()
  return {{ array_mt = {{}}, null = {{}}, decode_array_with_array_mt = function() end }}
end }}
package.loaded["resty.http"] = {{ new = function() error("HTTP must not be called") end }}
local control = dofile("{CONTROL}")
local conf = {{ API_URL = "http://127.0.0.1:8080", MANAGEMENT_LOGIN = "login", MANAGEMENT_PASSWORD = "secret" }}
local _, _, pagination = control.run(conf, nil, "decisions", {{ limit = 201 }})
assert(pagination == 400)
local _, _, unban = control.run(conf, nil, "unban", {{ decision_id = -1, value = "1.2.3.4" }})
assert(unban == 400)
local _, _, unknown = control.run(conf, nil, "unknown", {{}})
assert(unknown == 400)
"""
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")
def test_api_control_rejects_bad_and_unknown_connections():
    result = run("""
local p = plugin()
assert(p:init().ret)
p.ctx.bw.uri = "/crowdsec/decisions"
BODY_PARAMS = { connection = "short" }
show("BAD_ID", p:api())
BODY_PARAMS = { connection = string.rep("b", 64) }
show("UNKNOWN_CONNECTION", p:api())
p.ctx.bw.uri = "/crowdsec/noexist"
show("UNKNOWN_ROUTE", p:api())
""")
    assert result.returncode == 0, result.stderr
    assert field(result.stdout, "BAD_ID").endswith("|400")
    assert field(result.stdout, "UNKNOWN_CONNECTION").endswith("|404")
    assert field(result.stdout, "UNKNOWN_ROUTE") == "false|success|nil"
