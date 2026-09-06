"""Antibot names its served challenge in the report reason.

A challenge page is a security action that answers the request *instead of* the origin:
``antibot:access()`` ends on ``ngx.OK`` and the content phase renders the page with a 200. The
dispatcher (``src/common/confs/server-http/access-lua.conf``) only calls ``set_reason()`` for a
status in its ``reason_statuses`` set — the deny status, 400, 405, 429 — and ``ngx.OK`` is not one
of them, so before this the plugin recorded nothing at all: ``metrics:log()`` buffers a record only
when ``utils.get_reason()`` returns one, so no filter widening on any side could ever have surfaced
a challenge. Two things have to hold:

* ``antibot:set_challenge_reason()`` must build the payload the Reports page renders its sentence
  from — ``source``/``provider``/``action``/``http_status``, with the reason token being the plugin
  id so it matches the report allowlist (``is_report()``, ``_SELF_SERVED_REASONS``).
* both branches that serve a challenge page must call it. There are two (GET, and the POST that
  re-renders after a failed answer) and they are eight lines apart; instrumenting one and not the
  other loses half the rows and nothing else goes red.

The first is executed: the method is spliced out and run through the ``lua`` binary against a stub
``set_reason``, so the payload is proven rather than pattern-matched. The second is asserted on the
shipped source — ``antibot:access()`` closes over the plugin base class, the session store, the
datastore and six settings, and re-implementing those would test the mock.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ANTIBOT_LUA = ROOT / "src" / "common" / "core" / "antibot" / "antibot.lua"
SOURCE = ANTIBOT_LUA.read_text(encoding="utf-8")

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _method(name: str) -> str:
    match = re.search(rf"^function antibot:{name}\(.*?^end$", SOURCE, re.S | re.M)
    assert match, f"antibot:{name}() not found — did it get renamed?"
    return match.group(0)


def _run_set_challenge_reason(provider, recorded_action=None, recorded_reason=None, method_source=None):
    """Execute the shipped set_challenge_reason() against a stub set_reason and dump what it built.

    ``recorded_action`` / ``recorded_reason`` seed ``ctx.bw`` the way another plugin that already
    recorded a reason for this request would have left it (CrowdSec delegating a ``captcha``
    decision, `crowdsec.lua`).
    """
    assert LUA is not None
    provider_literal = "nil" if provider is None else f"[==[{provider}]==]"
    if recorded_reason is None and recorded_action is None:
        ctx_literal = "{ bw = {} }"
    else:
        data_literal = "nil" if recorded_action is None else f"{{ action = [==[{recorded_action}]==] }}"
        ctx_literal = "{ bw = { reason = [==[" + (recorded_reason or "crowdsec") + "]==], reason_data = " + data_literal + " } }"
    script = "\n".join(
        [
            # The two module upvalues the method closes over, spelled the way antibot.lua spells
            # them. HTTP_OK is `ngx.HTTP_OK or 200` there; standalone lua has no ngx, so 200.
            "local HTTP_OK = 200",
            "local CAPTURED",
            "local function set_reason(reason, data, ctx) CAPTURED = { reason = reason, data = data, ctx = ctx } end",
            "local antibot = {}",
            method_source if method_source is not None else _method("set_challenge_reason"),
            f"local self = {{ id = 'antibot', provider = {provider_literal}, ctx = {ctx_literal} }}",
            "antibot.set_challenge_reason(self)",
            "if CAPTURED == nil then print('REASON=<kept>') os.exit(0) end",
            "print('REASON=' .. tostring(CAPTURED.reason))",
            "print('SOURCE=' .. tostring(CAPTURED.data.source))",
            "print('PROVIDER=' .. tostring(CAPTURED.data.provider))",
            "print('ACTION=' .. tostring(CAPTURED.data.action))",
            "print('STATUS=' .. tostring(CAPTURED.data.http_status))",
            "print('CTX=' .. tostring(CAPTURED.ctx == self.ctx))",
        ]
    )
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return dict(line.split("=", 1) for line in result.stdout.strip().splitlines())


@needs_lua
class TestThePayload:
    def test_it_records_the_plugin_id_as_the_reason(self):
        """``antibot`` is the token both halves of the report filter allowlist; anything else and
        the row is written and never displayed."""
        assert _run_set_challenge_reason("captcha")["REASON"] == "antibot"

    def test_it_records_the_provider_that_was_served(self):
        """The only thing that tells a captcha apart from a turnstile in the Reports table, and
        the value ``security-reason.js`` interpolates into its sentence."""
        captured = _run_set_challenge_reason("turnstile")
        assert captured["SOURCE"] == "antibot"
        assert captured["PROVIDER"] == "turnstile"
        assert captured["ACTION"] == "challenge"

    def test_it_records_the_status_the_challenge_page_is_served_with(self):
        """Not ``ngx.status`` read during the access phase: nothing has been sent yet there, so it
        is still the default and recording it would be noise."""
        assert _run_set_challenge_reason("captcha")["STATUS"] == "200"

    def test_it_writes_into_the_request_context(self):
        """``set_reason`` mirrors into ``ctx.bw``; ``metrics:log()`` reads it back from there at
        log time through ``utils.get_reason()``."""
        assert _run_set_challenge_reason("captcha")["CTX"] == "true"


class TestBothServedBranchesCallIt:
    def test_every_challenge_page_records_a_reason(self):
        """access() serves the challenge page from two places — the GET branch and the POST branch
        that re-renders after a failed answer. Both set ``antibot_display_content`` and return
        ``ngx.OK``; the reason has to be set on both or half the challenges are invisible."""
        lines = _method("access").splitlines()
        # Every line that hands the challenge page back, found independently of what precedes it:
        # counting the *returns* and then looking behind each one is what makes deleting the call
        # go red, rather than merely reshaping the window a single regex was matching.
        served = [i for i, line in enumerate(lines) if 'return self:ret(true, "displaying challenge to client"' in line]
        assert len(served) == 2, f"expected 2 challenge-serving branches in antibot:access(), found {len(served)}"
        for index in served:
            preceding = lines[max(0, index - 3) : index]  # noqa: E203 (black's slice spacing)
            assert any(
                "self:set_challenge_reason()" in line for line in preceding
            ), f"the challenge served at offset {index} of antibot:access() records no reason:\n" + "\n".join(preceding)

    def test_the_helper_is_wired_to_the_shared_set_reason(self):
        """``utils.set_reason`` and not a local re-implementation: it is what mirrors the reason
        into both ``ctx.bw`` and the ``$reason`` nginx variable, and the log phase reads either."""
        assert "local set_reason = utils.set_reason" in SOURCE
        assert "set_reason(self.id, {" in _method("set_challenge_reason")


@needs_lua
class TestItNeverOverwritesAnotherPluginsChallengeReason:
    """CrowdSec delegates a ``captcha`` remediation to this plugin and records *why* before handing
    over -- the LAPI scenario, or the AppSec verdict (``crowdsec.lua``). ``utils.set_reason``
    overwrites unconditionally, so without the guard the Reports row loses the decision entirely and
    reads as a bare "antibot" challenge nobody asked for."""

    def test_a_recorded_captcha_remediation_is_kept(self):
        assert _run_set_challenge_reason("captcha", recorded_action="captcha")["REASON"] == "<kept>"

    def test_a_recorded_challenge_remediation_is_kept(self):
        assert _run_set_challenge_reason("captcha", recorded_action="challenge")["REASON"] == "<kept>"

    @pytest.mark.parametrize("recorded_action", ["redirect", "block"])
    def test_a_reason_recorded_for_a_DIFFERENT_remediation_is_still_replaced(self, recorded_action):
        """Under ``SECURITY_MODE=detect`` a workflow rule records ``action = action.type`` and lets
        the chain continue (``workflows.lua:289``/``:298``), so a `redirect` or a `block` rule can
        leave a reason behind on a request the antibot then challenges. That reason is not about
        this challenge: the action actually taken is what the row should name.

        ``block`` and ``redirect`` are the two non-challenge members of
        ``ACTION_TYPES = ("block", "redirect", "challenge")``
        (``src/common/utils/workflow_schema.py:50``) -- with the ``challenge`` case in the test
        below, the three shapes ``workflows.lua`` can actually write are all covered."""
        captured = _run_set_challenge_reason("captcha", recorded_reason="workflows", recorded_action=recorded_action)
        assert captured["REASON"] == "antibot"
        assert captured["ACTION"] == "challenge"

    def test_a_workflow_challenge_rule_observed_in_detect_keeps_its_own_row(self):
        """The one workflow shape the guard *does* keep, and deliberately: a challenge rule records
        ``action = "challenge"`` in the same detect branch. The rule is the cause of the page the
        antibot is about to serve, exactly as a CrowdSec captcha decision is, so it owns the row.
        The cost is the ``provider`` field, which only ``set_challenge_reason()`` records."""
        captured = _run_set_challenge_reason("captcha", recorded_reason="workflows", recorded_action="challenge")
        assert captured["REASON"] == "<kept>"

    def test_a_reason_with_no_remediation_data_is_still_replaced(self):
        captured = _run_set_challenge_reason("captcha", recorded_reason="workflows")
        assert captured["REASON"] == "antibot"

    def test_nothing_recorded_yet_records_the_antibot_reason(self):
        """The ordinary path: no CrowdSec, no workflow, just USE_ANTIBOT."""
        assert _run_set_challenge_reason("captcha")["REASON"] == "antibot"

    def test_the_guard_is_what_keeps_it(self):
        """Mutation: drop the guard and CrowdSec's reason is overwritten by a bare antibot row.

        Mutates the spliced copy, never the file on disk -- nothing else in the tree can observe it.
        """
        method = _method("set_challenge_reason")
        mutated = re.sub(
            r'\n\tif recorded_action == "captcha" or recorded_action == "challenge" then\n\t\treturn\n\tend\n',
            "\n",
            method,
        )
        assert mutated != method, "the guard no longer reads as expected -- update this mutation"
        captured = _run_set_challenge_reason("captcha", recorded_action="captcha", method_source=mutated)
        assert captured["REASON"] == "antibot"


class TestASolvedChallengeIsNotServedAgain:
    """This early return is the resolution state of a CrowdSec-delegated captcha.

    ``crowdsec.lua`` flags *every* request for the whole life of a `captcha` decision -- there is no
    per-source store on the CrowdSec side (design gate ruling 3, ``report-CS-B.md`` §6). What turns
    that into a no-op instead of a challenge loop the visitor can never leave is ``access()``
    returning on ``session_data.resolved`` **before** it prepares or serves anything. Asserted on the
    shipped source: ``antibot:access()`` closes over the plugin base class, the session store, the
    datastore and six settings, and re-implementing those would test the mock.
    """

    def test_access_returns_on_a_resolved_session_before_it_prepares_a_challenge(self):
        lines = _method("access").splitlines()
        resolved = [i for i, line in enumerate(lines) if "if self.session_data.resolved then" in line]
        assert resolved, "antibot:access() no longer short-circuits on a resolved session"
        prepared = [i for i, line in enumerate(lines) if "self:prepare_challenge()" in line]
        assert prepared, "antibot:access() no longer prepares a challenge -- update this test"
        assert resolved[0] < prepared[0], "the resolved check must come first, or a solved client is re-challenged"
        window = "\n".join(lines[resolved[0] : prepared[0]])  # noqa: E203 (black's slice spacing)
        assert "return self:ret(" in window, f"the resolved branch falls through instead of returning:\n{window}"
