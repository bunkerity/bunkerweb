"""CrowdSec control: an already-gone decision converges instead of failing, and decisions say what the bouncer does with them.

The unban flow deletes every ban decision of an IP and counts "already gone" as success, so the control `unban`
operation answers 200 with `already_absent` when the selected decision is no longer active (it used to answer 409,
which the flow could not tell apart from "the decision changed"). `decisions` carries the `remediation` the bouncer
enforces, so the preview lists only the decisions that block the IP.

The harness runs control.lua under a plain `lua` with a scripted Local API: `resty.http` is replaced by a router over
canned decision lists, and `cjson.safe` by a decoder that maps a canned body name to a Lua table.
"""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "src/common/core/crowdsec/control.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = r"""
local array_mt = {}
local function arr(items) return setmetatable(items, array_mt) end
local state = { calls = {}, selected = arr({}), listing = arr({}), remaining = arr({}), delete_reply = { nbDeleted = 1 }, fail_remaining = false }
local json = {
  array_mt = array_mt,
  null = {},
  decode_array_with_array_mt = function() end,
  encode = function() return "{}" end,
  decode = function(body) return state.bodies[body] end,
}
package.loaded["cjson.safe"] = { new = function() return json end }
ngx = {
  time = function() return 1000 end,
  now = function() return 1000 end,
  encode_args = function(t)
    local keys = {}
    for key in pairs(t) do keys[#keys + 1] = key end
    table.sort(keys)
    local out = {}
    for _, key in ipairs(keys) do out[#out + 1] = key .. "=" .. tostring(t[key]) end
    return table.concat(out, "&")
  end,
}
local function body_of(opts)
  if opts.path:find("watchers/login", 1, true) then return "LOGIN" end
  if opts.method == "DELETE" then return "DELETE_REPLY" end
  if (opts.query or ""):find("contains=false", 1, true) then return "SELECTED" end
  if state.fail_remaining and state.deleted_once then return nil end
  return "LISTING"
end
package.loaded["resty.http"] = { new = function()
  local client = {}
  function client.set_timeout() end
  function client.parse_uri(_, uri)
    local path, query = uri:match("^https?://[^/]+(/[^?]*)%??(.*)$")
    return { "http", "127.0.0.1", 8080, path, query }
  end
  function client.connect() return true end
  function client.close() end
  function client.request(_, opts)
    state.calls[#state.calls + 1] = opts.method .. " " .. opts.path
    if opts.method == "DELETE" then state.deleted_once = true end
    local name = body_of(opts)
    if not name then return nil end
    local sent = false
    return { status = 200, headers = {}, body_reader = function()
      if sent then return nil end
      sent = true
      return name
    end }
  end
  return client
end }
state.bodies = {
  LOGIN = { token = "management-token" },
  SELECTED = state.selected,
  LISTING = state.listing,
  DELETE_REPLY = state.delete_reply,
}
local control = dofile(CONTROL_PATH)
local conf = {
  API_URL = "http://127.0.0.1:8080", API_KEY = "key", MANAGEMENT_LOGIN = "login", MANAGEMENT_PASSWORD = "secret",
  BOUNCING_ON_TYPE = "all", FALLBACK_REMEDIATION = "ban", MODE = "live", CACHE_EXPIRATION = 1,
}
local function item(id, scope, value, kind) return { id = id, scope = scope, value = value, type = kind or "ban", origin = "crowdsec" } end
local function show(name, value) print(name .. "=" .. tostring(value)) end
local function calls() return table.concat(state.calls, ",") end
"""


def run(body: str):
    script = f'CONTROL_PATH = "{CONTROL}"\n{HARNESS}\n{body}'
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_a_decision_that_is_no_longer_active_converges_as_already_absent():
    out = run("""
state.selected[1] = nil
state.listing[1] = item(7, "Ip", "1.2.3.4", "captcha")
local reply, err, status = control.run(conf, nil, "unban", { decision_id = 5, scope = "Ip", value = "1.2.3.4", decision_type = "ban" })
show("STATUS", status)
show("REMOVED", reply.removed)
show("ABSENT", reply.already_absent)
show("REMAINING", #reply.remaining_decisions)
show("CALLS", calls())
""")
    assert out["STATUS"] == "200"
    assert (out["REMOVED"], out["ABSENT"], out["REMAINING"]) == ("false", "true", "1")
    assert "DELETE" not in out["CALLS"]  # nothing to delete: no write to the Local API


def test_an_absent_decision_whose_verification_fails_is_a_502():
    out = run("""
state.bodies.LISTING = nil
local reply, err, status = control.run(conf, nil, "unban", { decision_id = 5, scope = "Ip", value = "1.2.3.4", decision_type = "ban" })
show("STATUS", status)
show("REPLY", reply)
show("ERR", err)
""")
    assert out["STATUS"] == "502"
    assert out["REPLY"] == "nil"


def test_a_decision_whose_type_changed_is_still_a_409():
    out = run("""
state.selected[1] = item(5, "Ip", "1.2.3.4", "captcha")
local _, _, status = control.run(conf, nil, "unban", { decision_id = 5, scope = "Ip", value = "1.2.3.4", decision_type = "ban" })
show("STATUS", status)
""")
    assert out["STATUS"] == "409"


def test_deleting_an_active_decision_still_reports_removed():
    out = run("""
state.selected[1] = item(5, "Ip", "1.2.3.4")
local reply, _, status = control.run(conf, nil, "unban", { decision_id = 5, scope = "Ip", value = "1.2.3.4", decision_type = "ban" })
show("STATUS", status)
show("REMOVED", reply.removed)
show("ABSENT", reply.already_absent)
show("CALLS", calls())
""")
    assert (out["STATUS"], out["REMOVED"], out["ABSENT"]) == ("200", "true", "false")
    assert "DELETE watchers" not in out["CALLS"] and "DELETE /v1/decisions/5" in out["CALLS"]


def test_a_delete_that_hits_nothing_is_already_absent():
    out = run("""
state.selected[1] = item(5, "Ip", "1.2.3.4")
state.delete_reply.nbDeleted = 0
local reply, _, status = control.run(conf, nil, "unban", { decision_id = 5, scope = "Ip", value = "1.2.3.4", decision_type = "ban" })
show("ABSENT", reply.already_absent)
""")
    assert out["ABSENT"] == "true"


def test_decisions_carry_the_remediation_the_bouncer_enforces():
    out = run("""
state.listing[1] = item(1, "Ip", "1.2.3.4", "ban")
state.listing[2] = item(2, "Ip", "1.2.3.4", "captcha")
state.listing[3] = item(3, "Ip", "1.2.3.4", "throttle")
state.listing[4] = item(4, "Country", "FR", "ban")
local reply, _, status = control.run(conf, nil, "decisions", { ip = "1.2.3.4" })
local by_id = {}
for _, decision in ipairs(reply.decisions) do by_id[decision.id] = tostring(decision.remediation) end
show("STATUS", status)
show("ID1", by_id[1]); show("ID2", by_id[2]); show("ID3", by_id[3]); show("ID4", by_id[4])
""")
    # throttle is not ban or captcha: it takes FALLBACK_REMEDIATION, exactly as bouncer.lua apply_decision does
    assert (out["ID1"], out["ID2"], out["ID3"], out["ID4"]) == ("ban", "captcha", "ban", "nil")


def test_a_decision_the_bouncer_ignores_has_no_remediation():
    out = run("""
conf.BOUNCING_ON_TYPE = "ban"
conf.FALLBACK_REMEDIATION = ""
state.listing[1] = item(1, "Ip", "1.2.3.4", "ban")
state.listing[2] = item(2, "Ip", "1.2.3.4", "captcha")
state.listing[3] = item(3, "Range", "1.2.3.0/24", "ban")
local reply = control.run(conf, nil, "decisions", { ip = "1.2.3.4" })
local by_id = {}
for _, decision in ipairs(reply.decisions) do by_id[decision.id] = tostring(decision.remediation) end
show("ID1", by_id[1]); show("ID2", by_id[2]); show("ID3", by_id[3])
""")
    # BOUNCING_ON_TYPE=ban ignores the captcha decision; a Range decision is enforced like an Ip one
    assert (out["ID1"], out["ID2"], out["ID3"]) == ("ban", "nil", "ban")


def test_an_empty_fallback_leaves_an_unknown_type_without_remediation():
    out = run("""
conf.FALLBACK_REMEDIATION = ""
state.listing[1] = item(1, "Ip", "1.2.3.4", "throttle")
local reply = control.run(conf, nil, "decisions", { ip = "1.2.3.4" })
show("R", reply.decisions[1].remediation)
""")
    assert out["R"] == "nil"
