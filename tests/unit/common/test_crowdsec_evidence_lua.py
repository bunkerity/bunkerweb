"""The CrowdSec relay keeps its existing verdict and adds investigation evidence."""

from pathlib import Path
import shutil
import subprocess

import pytest

from test_crowdsec_challenge_lua import CHALLENGE_PREFIX, field, run
from test_crowdsec_init_health_lua import run as run_plugin

ROOT = Path(__file__).resolve().parents[3]
BOUNCER = ROOT / "src/common/core/crowdsec/lib/bouncer.lua"
PLUGIN = ROOT / "src/common/core/crowdsec/crowdsec.lua"


def test_allow_preserves_relay_and_returns_evidence():
    source = BOUNCER.read_text()
    assert "function csmod.Allow(ip, no_render, antibot_provider, challengePrefix)" in source
    assert "appsec_evidence" in source
    assert "verdict, antibot_provider, evidence" in source


def test_access_tags_evidence_for_the_report():
    source = PLUGIN.read_text()
    assert "evidence.connection = connection_id(scope, bouncer)" in source
    assert "evidence.service_scope = scope" in source
    assert "evidence.instance = ngx.var.hostname" in source


def test_appsec_evidence_reaches_seventh_return_without_moving_verdict():
    output = run(f"""
local ok, _, _, _, verdict, provider, evidence = csmod.Allow("1.2.3.4", false, nil, "{CHALLENGE_PREFIX}")
print("EVIDENCE=" .. tostring(ok) .. "|" .. tostring(verdict.action) .. "|" .. tostring(provider) .. "|" .. tostring(evidence.source))
""")
    assert field(output, "EVIDENCE") == "true|challenge|nil|appsec"


def test_transport_failure_uses_failure_policy_source():
    output = run(
        f"""
local _, _, _, _, verdict, _, evidence = csmod.Allow("1.2.3.4", false, nil, "{CHALLENGE_PREFIX}")
print("SOURCE=" .. tostring(verdict.source) .. "|" .. tostring(evidence.source))
""",
        appsec_err="connection refused",
        conf={"APPSEC_FAILURE_ACTION": "deny"},
    )
    assert field(output, "SOURCE") == "appsec|failure_policy"


def test_failure_policy_evidence_keeps_appsec_workflow_source():
    result = run_plugin("""
local p = plugin()
assert(p:init().ret)
p.is_request = true
p.variables.USE_CROWDSEC = "yes"
p.ctx.bw.remote_addr = "1.2.3.4"
local response = p:access()
assert(response.status == 403)
print("WORKFLOW_SOURCE=" .. tostring(p.ctx.bw.crowdsec_source))
print("REPORT_SOURCE=" .. tostring(response.data.source))
""")
    assert result.returncode == 0, result.stderr
    assert field(result.stdout, "WORKFLOW_SOURCE") == "appsec"
    assert field(result.stdout, "REPORT_SOURCE") == "failure_policy"


def test_scalar_appsec_response_falls_back_without_serving_unchecked():
    output = run(
        f"""
local ok, _, banned, _, verdict, _, evidence = csmod.Allow("1.2.3.4", false, nil, "{CHALLENGE_PREFIX}")
print("FALLBACK=" .. tostring(ok) .. "|" .. tostring(banned) .. "|" .. tostring(verdict.action) .. "|" .. tostring(evidence.source))
""",
        appsec_json="bad response",
    )
    assert field(output, "FALLBACK") == "true|true|ban|failure_policy"


@pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")
def test_decision_cache_keeps_distinct_decisions_when_metadata_is_full():
    module = ROOT / "src/common/core/crowdsec/lib/decision_cache.lua"
    script = f"""
local encoded, next_id = {{}}, 0
package.loaded["cjson"] = {{ array_mt = {{}},
  encode = function(value) next_id = next_id + 1; encoded[next_id] = value; return tostring(next_id) end,
  decode = function(value) return encoded[tonumber(value)] end,
}}
package.loaded["crowdsec.cache_partition"] = {{ hash = function(value) return value end }}
ngx = {{ time = function() return 100 end }}
local function dict(fail)
  local values = {{}}
  return {{
    get = function(_, key) return values[key] end,
    safe_set = function(_, key, value) if fail then return nil end; values[key] = value; return true end,
    delete = function(_, key) values[key] = nil end,
  }}
end
local cache = dofile("{module}").new(dict(false), dict(true))
local first = {{ id = 1, type = "captcha", scope = "Ip", value = "1.2.3.4", duration = "1h" }}
local second = {{ id = 2, type = "ban", scope = "Ip", value = "1.2.3.4", duration = "1h" }}
assert(cache.update("ip-key", first, "captcha", 3600))
assert(cache.update("ip-key", second, "ban", 3600))
local remediation, evidence = cache.get("ip-key")
assert(remediation == "ban" and evidence.metadata_available == false)
assert(cache.update("ip-key", second, "ban", nil, true))
assert(cache.get("ip-key") == "captcha")
"""
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
