"""Request-body parser denials (ModSecurity rules 200002 / 200005) keep their own reason (port of dev 2c950f757).

The two rules deny a request whose body the parser rejected. They set no ``tx.bunkerweb_reason`` of
their own, so ``utils.get_reason`` fell through to the generic "unknown" denial and Reports could not
tell a malformed body from any other BunkerWeb refusal. The conf now stamps
``modsecurity-body-<id>`` and ``get_reason`` turns it into the reason ``modsecurity-body`` with the
rule id as data. Two properties matter:

* only 200002 and 200005 map; any other ``modsecurity_reason`` value keeps today's behaviour, so a
  client cannot pick its own reason through a crafted value;
* the BunkerNet plugin must not push such a denial to the shared database (a parser error is not
  evidence of an attack).

Runs the real ``get_reason`` / ``bunkernet:log`` blocks through the ``lua`` binary with OpenResty
stubbed, the way ``test_header_rules_lua.py`` does.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
BUNKERNET_LUA = ROOT / "src" / "common" / "core" / "bunkernet" / "bunkernet.lua"
MODSEC_CONFS = [
    ROOT / "src" / "common" / "core" / "modsecurity" / "confs" / "server-http" / "modsecurity-rules.conf.modsec",
    ROOT / "src" / "common" / "core" / "modsecurity" / "confs" / "server-http" / "modsecurity-rules-global-crs.conf.modsec",
]

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def get_reason_source() -> str:
    text = UTILS_LUA.read_text(encoding="utf-8")
    chunk = re.search(r"^utils\.get_reason = function\(ctx\)$.*?^end$", text, re.S | re.M)
    assert chunk, "utils.get_reason was not found in utils.lua -- renamed or restructured?"
    return chunk.group(0)


def bunkernet_log_source() -> str:
    """``bunkernet:log`` up to the first check after the skip filters, with a marker return."""
    text = BUNKERNET_LUA.read_text(encoding="utf-8")
    chunk = re.search(r"^function bunkernet:log\(bypass_checks\)$.*?(?=\n\t-- Check if IP is global)", text, re.S | re.M)
    assert chunk, "bunkernet:log was not found in bunkernet.lua -- renamed or restructured?"
    return chunk.group(0) + '\n\treturn self:ret(true, "reached the report path")\nend'


PREAMBLE = r"""
VAR = {}
ngx = { var = VAR, status = 200 }
local var = VAR
local utils = {}
utils.get_security_mode = function() return "block" end
utils.get_deny_status = function() return 403 end
local decode = function(s) return {} end
local datastore = { get = function() return nil, "not found" end }
"""

BUNKERNET_PREAMBLE = r"""
local WARN = "WARN"
local ERR = "ERR"
local get_reason
"""


def run_get_reason(body: str) -> str:
    script = "\n".join([PREAMBLE, get_reason_source(), body])
    result = subprocess.run([str(LUA), "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def run_bunkernet_log(reason: str) -> str:
    script = "\n".join(
        [
            BUNKERNET_PREAMBLE,
            f'get_reason = function() return {reason!r}, {{}}, "block" end',
            "local bunkernet = {}",
            bunkernet_log_source(),
            "local self = { ctx = { bw = {} }, ret = function(_, ok, msg) return msg end }",
            "print(bunkernet.log(self, true))",
        ]
    )
    result = subprocess.run([str(LUA), "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


@needs_lua
class TestGetReason:
    @pytest.mark.parametrize("rule_id", ["200002", "200005"])
    def test_body_parser_denial_is_named_with_its_rule_id(self, rule_id):
        out = run_get_reason(f"""
VAR.modsecurity_reason = "modsecurity-body-{rule_id}"
local reason, data, mode = utils.get_reason({{ bw = {{ security_mode = "block", remote_addr = "203.0.113.7" }} }})
print(reason, #data.ids, data.ids[1], mode)
""")
        assert out == f"modsecurity-body\t1\t{rule_id}\tblock"

    @pytest.mark.parametrize("value", ["modsecurity-body-200003", "modsecurity-body-2000020", "modsecurity-body-", "xmodsecurity-body-200002"])
    def test_any_other_value_keeps_the_unmapped_behaviour(self, value):
        # not a mapped id: falls through to the unknown-denial arm (status == deny status)
        out = run_get_reason(f"""
VAR.modsecurity_reason = "{value}"
ngx.status = 403
local reason = utils.get_reason({{ bw = {{ security_mode = "block", remote_addr = "203.0.113.7" }} }})
print(reason)
""")
        assert out == "unknown"

    def test_crs_summary_reason_is_untouched(self):
        out = run_get_reason("""
VAR.modsecurity_reason = "modsecurity"
VAR.modsecurity_rules = " 942100 941100"
local reason, data = utils.get_reason({ bw = { security_mode = "block", remote_addr = "203.0.113.7" } })
print(reason, #data.ids, data.ids[1], data.ids[2])
""")
        assert out == "modsecurity\t2\t942100\t941100"


@needs_lua
class TestBunkerNetSkip:
    def test_body_parser_denial_is_not_reported(self):
        assert run_bunkernet_log("modsecurity-body") == "skipping report because the reason is modsecurity-body"

    def test_other_reasons_still_reach_the_report_path(self):
        assert run_bunkernet_log("modsecurity") == "reached the report path"

    def test_bunkernet_reason_still_skipped(self):
        assert run_bunkernet_log("bunkernet") == "skipping report because the reason is bunkernet"


class TestConfStampsTheReason:
    """The nginx variable comes from ``tx.bunkerweb_reason``; a rule that never sets it reports nothing."""

    @pytest.mark.parametrize("conf", MODSEC_CONFS, ids=lambda p: p.name)
    @pytest.mark.parametrize("rule_id", ["200002", "200005"])
    def test_each_parser_rule_has_an_update_action_with_status_and_reason(self, conf, rule_id):
        text = conf.read_text(encoding="utf-8")
        match = re.search(rf'^SecRuleUpdateActionById {rule_id} "([^"]*)"$', text, re.M)
        assert match, f"{conf.name}: no SecRuleUpdateActionById for {rule_id}"
        actions = match.group(1)
        assert "deny" in actions and "status:400" in actions
        assert f"setvar:'tx.bunkerweb_reason=modsecurity-body-{rule_id}'" in actions


METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"


def method_block_source() -> str:
    text = METRICS_LUA.read_text(encoding="utf-8")
    chunk = re.search(r'^\t\t\tif reason == "modsecurity-body" and ngx\.var\.request then$.*?^\t\t\tend$', text, re.S | re.M)
    assert chunk, "the modsecurity-body method fallback was not found in metrics:log -- not ported?"
    return chunk.group(0)


def run_stored_method(reason: str, request: str | None, fallback: str | None) -> str:
    req = "nil" if request is None else f'"{request}"'
    fb = "nil" if fallback is None else f'"{fallback}"'
    script = "\n".join(
        [
            f"ngx = {{ var = {{ request = {req} }} }}",
            f'local reason = "{reason}"',
            f"local request = {{ method = {fb} }}",
            method_block_source(),
            "print(tostring(request.method))",
        ]
    )
    result = subprocess.run([str(LUA), "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


@needs_lua
class TestMetricsMethod:
    """An early parser denial can redirect to the error page before ``ctx.bw.request_method`` is saved."""

    def test_body_denial_reads_the_method_from_the_request_line(self):
        assert run_stored_method("modsecurity-body", "POST /x HTTP/1.1", None) == "POST"

    def test_body_denial_prefers_the_request_line_over_a_stale_method(self):
        # after an error-page redirect nginx rewrites the method to GET in ctx
        assert run_stored_method("modsecurity-body", "PUT /x HTTP/1.1", "GET") == "PUT"

    def test_body_denial_without_a_request_line_keeps_the_context_method(self):
        assert run_stored_method("modsecurity-body", None, "POST") == "POST"

    @pytest.mark.parametrize("reason", ["modsecurity", "blacklist", "unknown"])
    def test_any_other_reason_keeps_the_context_method(self, reason):
        assert run_stored_method(reason, "POST /x HTTP/1.1", "GET") == "GET"
        assert run_stored_method(reason, "POST /x HTTP/1.1", None) == "nil"
