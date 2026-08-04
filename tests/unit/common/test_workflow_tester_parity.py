"""The rule tester's evaluator against the real runtime, case for case.

``workflow_eval.py`` is a second implementation of what ``workflows.lua`` does on the request
path. A second implementation drifts — that is not a risk to be argued away, it is a
certainty to be detected. So the same corpus is executed by both engines and the two answer
lines are compared: Python in-process, Lua in a subprocess running the actual plugin source.

The corpus is data (``workflow_cases.json``). Adding a case is appending one object; when the
two disagree the failure names the case and prints both answers.

What this does NOT prove: that either engine is *correct*, only that they agree on the cases
present. It is a regression net. Every fidelity gap gets a case the day it is written down.
"""

import json
import shutil
import subprocess
from re import sub
from pathlib import Path

import pytest

from workflow_eval import Outcome, evaluate, prepare_ladder  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "workflows"
CORPUS = Path(__file__).parent / "workflow_cases.json"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SERVER = "app.example.com"


def _lua_literal(value, null="NULL"):
    """Emit a JSON value as a Lua table literal.

    ``nil`` cannot live in a table constructor, so a JSON null becomes the same truthy
    sentinel cjson hands the runtime — which is the shape the artefact really arrives in.
    """
    if value is None:
        return null
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, list):
        return "{ " + ", ".join(_lua_literal(item, null) for item in value) + " }"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"[{_lua_literal(key, null)}] = {_lua_literal(item, null)}" for key, item in value.items()) + " }"
    raise TypeError(f"cannot emit {type(value)!r} as Lua")


HARNESS = """
local PLUGIN = %s
local NULL = setmetatable({}, { __tostring = function() return "null" end })
local ARTEFACT = %s
local CASES = %s

local COUNT = 1

ngx = {
    ERR = "ERR",
    INFO = "INFO",
    re = {
        -- Lua patterns stand in for PCRE. The corpus guard keeps every pattern in the
        -- intersection of both dialects, so this substitution cannot change a verdict.
        find = function(subject, pattern)
            local ok, s = pcall(string.find, subject, pattern)
            if not ok then return nil, nil, "bad pattern" end
            return s, nil, nil
        end,
    },
}

package.loaded["cjson"] = { decode = function() return ARTEFACT end, null = NULL }
package.loaded["middleclass"] = function(_, parent)
    local klass = {}
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.ipmatcher"] = {
    new = function(values)
        local set = {}
        for _, value in ipairs(values) do
            -- Mirrors the corpus contract: exact addresses only, so CIDR arithmetic (which
            -- neither engine implements itself) stays out of the differential.
            if type(value) ~= "string" or value:find("/") then return nil, "unsupported" end
            set[value] = true
        end
        return { match = function(_, ip) return set[ip] == true end }
    end,
}
package.loaded["bunkerweb.plugin"] = {
    initialize = function(self)
        self.logger = { log = function() end }
    end,
    ret = function(_, ok, msg, status, redirect, data)
        return { ret = ok, msg = msg, status = status, redirect = redirect, data = data }
    end,
    set_metric = function() end,
    log_throttled = function() end,
}
package.loaded["bunkerweb.ratelimit"] = {
    -- incr() returns the count INCLUDING the current request, which is exactly what the
    -- tester's request_number field means. So the gate is a pure comparison on both sides.
    incr = function() return COUNT end,
}
package.loaded["bunkerweb.utils"] = {
    get_variable = function() return "512" end,
    get_deny_status = function() return 403 end,
    get_security_mode = function() return "block" end,
    is_whitelisted = function(ctx) return ctx and ctx.bw and ctx.bw.whitelisted == true end,
    set_reason = function() end,
}
package.loaded["workflows.eval"] = dofile(PLUGIN .. "/eval.lua")

local real_open = io.open
io.open = function(path, mode)
    if path:find("workflows/config.json", 1, true) then
        return { read = function() return "{}" end, close = function() end }
    end
    return real_open(path, mode)
end

-- rule id -> workflow id, built from the artefact itself. Deriving this from case.expect
-- would let the Lua side copy the answer it is supposed to be checked against.
local OWNER = {}
for workflow_id, workflow in pairs(ARTEFACT.workflows) do
    for _, rule in ipairs(workflow.rules) do OWNER[rule.id] = workflow_id end
end

local workflows = dofile(PLUGIN .. "/workflows.lua")
local instance = setmetatable({}, workflows)
instance:initialize({})
local loaded = instance:init()
assert(loaded.ret, "init failed: " .. tostring(loaded.msg))

local out = {}
for _, case in ipairs(CASES) do
    COUNT = case.request_number
    local bw = {
        server_name = "%s",
        remote_addr = "203.0.113.7",
        uri = "/",
        request_method = "GET",
        country = "FR",
        country_ok = true,
        asn_number = 64496,
        asn_ok = true,
    }
    for key, value in pairs(case.bw) do
        if value == NULL then bw[key] = nil else bw[key] = value end
    end
    -- country_ok / asn_ok default to true, but an explicit false in the case must win.
    if case.bw.country_ok == false then bw.country_ok = false end
    if case.bw.asn_ok == false then bw.asn_ok = false end

    instance.ctx = { bw = bw }
    local result = instance:access()

    local line
    if bw.whitelisted then
        line = "whitelisted"
    elseif result.msg:find("no rule matched", 1, true) then
        line = "no match"
    else
        -- "workflow rule <id> ..." — recover the id, then read the action from the shape.
        local rule = result.msg:match("workflow rule ([%%w%%-]+)")
        local action
        if result.redirect then action = "redirect"
        elseif result.msg:find("challenge", 1, true) then action = "challenge"
        else action = "block" end
        line = "match " .. tostring(OWNER[rule] or "?") .. " " .. tostring(rule) .. " " .. action
    end
    out[#out + 1] = line
end
print(table.concat(out, "\\n"))
"""


def _corpus():
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _python_lines(data):
    """Run every case through the Python evaluator, in the artefact's own order."""
    group_index = data["groups"]
    order = data["services"][SERVER]
    workflows = [
        {"id": workflow_id, "name": data["workflows"][workflow_id]["name"], "definition": {"rules": _as_definition(data["workflows"][workflow_id]["rules"])}}
        for workflow_id in order
    ]
    ladder = prepare_ladder(workflows, group_index)

    lines = []
    for case in data["cases"]:
        request = _request(case)
        outcome, _ = evaluate(ladder, request)
        if outcome["type"] == Outcome.WHITELISTED:
            lines.append("whitelisted")
        elif outcome["type"] == Outcome.NO_MATCH:
            lines.append("no match")
        else:
            lines.append(f"match {outcome['workflow_id']} {outcome['rule_id']} {outcome['action']['type']}")
    return lines


def _as_definition(rules):
    """The artefact drops `enabled`; the evaluator's ladder builder expects a definition."""
    return [dict(rule, enabled=True) for rule in rules]


def _request(case):
    bw = {
        "remote_addr": "203.0.113.7",
        "uri": "/",
        "request_method": "GET",
        "country": "FR",
        "country_ok": True,
        "asn_number": 64496,
        "asn_ok": True,
        "whitelisted": False,
    }
    bw.update(case["bw"])
    bw["request_number"] = case["request_number"]
    return bw


def _lua_lines(data):
    artefact = {"groups": data["groups"], "services": data["services"], "workflows": data["workflows"]}
    script = HARNESS % (
        _lua_literal(str(PLUGIN)),
        _lua_literal(artefact),
        _lua_literal(data["cases"]),
        SERVER,
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().split("\n")


def test_the_python_evaluator_agrees_with_the_lua_runtime():
    data = _corpus()
    expected = [case["expect"] for case in data["cases"]]
    python = _python_lines(data)
    lua = _lua_lines(data)

    assert len(python) == len(lua) == len(expected)

    for index, case in enumerate(data["cases"]):
        assert python[index] == expected[index], f"case {index} ({case['name']}): python said {python[index]!r}, corpus expects {expected[index]!r}"
        assert lua[index] == python[index], f"case {index} ({case['name']}): lua said {lua[index]!r}, python said {python[index]!r}"


def test_corpus_regexes_are_dialect_safe():
    """The Lua side stubs ngx.re.find with string.find, so a PCRE-only construct would be
    compared against a Lua pattern that means something else. Keep every corpus regex inside
    the intersection: anchors, literals, [0-9]-style classes, * and +. No alternation, no
    backslash class, no {n,m}. A '-' is fine inside [...] (a range in both dialects) but not
    outside it, where Lua reads it as a lazy quantifier and PCRE as a literal."""
    data = _corpus()
    safe = set("^$/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_[]-+*.()")
    offenders = []

    def walk(node):
        op = node.get("op")
        if op in ("all", "any"):
            for child in node.get("nodes") or []:
                walk(child)
        elif op == "not":
            walk(node["node"])
        elif op == "uri" and node.get("match") == "regex":
            value = node["value"]
            outside = sub(r"\[[^\]]*\]", "", value)
            if set(value) - safe or "\\" in value or "{" in value or "|" in value or "-" in outside:
                offenders.append(value)

    for workflow in data["workflows"].values():
        for rule in workflow["rules"]:
            walk(rule["condition"])

    assert not offenders, f"corpus regexes outside the Lua/PCRE intersection: {offenders}"


def test_every_corpus_case_is_reachable_and_named():
    data = _corpus()
    names = [case["name"] for case in data["cases"]]
    assert len(names) == len(set(names)), "corpus case names must be unique — they are the failure message"
    for case in data["cases"]:
        assert case["expect"] == "no match" or case["expect"] == "whitelisted" or case["expect"].startswith("match "), case["name"]
