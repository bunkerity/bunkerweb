"""The Reports/Bans reason renders as a sentence, not a JSON blob.

A CrowdSec row says ``crowdsec`` whether the request was blocked by a LAPI decision, challenged by
AppSec's bot detection, or handed a captcha — three verdicts that call for three different
reactions, told apart only by a ``reason_data`` blob nobody outside the team can read. An
``antibot`` row and a ``workflows`` row are the same problem: the token says a security action
happened and nothing about which one. ``components/security-reason.js`` turns that blob into one
sentence and returns ``null`` for everything it has nothing better to say about, so every other
reason keeps its current rendering.

Two things are worth pinning beyond the wording:

* the sentence is inserted as HTML by both tables, and the scenario name inside it is CrowdSec's
  string, not ours — it must be escaped exactly once. Escaping it twice would show ``&#39;`` to
  the user; not escaping it at all is an injection through the LAPI decision feed.
* the helper must return ``null``, never a half-built sentence, on any payload that is not a
  verdict — a ban whose ``reason_data`` is badbehavior's per-IP list, a JSON string that does not
  parse, a reason that is not crowdsec at all.

Runs the shipped file through node with a stub ``window``, the way ``test_export_formatters.py``
runs ``dataTableInit.js``.
"""

from json import dumps, loads
from pathlib import Path
from shutil import which
from subprocess import run

import pytest

ROOT = Path(__file__).resolve().parents[3]
COMPONENT = ROOT / "src/ui/app/static/js/components/security-reason.js"

# Loads the real component with a `window` that carries the real three-argument `t()` contract
# (i18n.js): {{placeholders}}, `defaultValue`, and `interpolation.escapeValue`. The catalog is
# empty on purpose for most cases, so what is asserted is the English source strings the file
# ships as fallbacks — the same thing an untranslated locale shows.
HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const CATALOG = JSON.parse(process.argv[3] || "{}");

function tr(key, defaultValue, options) {
  const settings =
    typeof defaultValue === "string"
      ? { defaultValue: defaultValue, ...(options || {}) }
      : defaultValue || {};
  const value = String(key).split(".").reduce((n, p) => (n == null ? undefined : n[p]), CATALOG);
  const message =
    typeof value === "string" ? value : settings.defaultValue !== undefined ? settings.defaultValue : key;
  const escape = !settings.interpolation || settings.interpolation.escapeValue !== false;
  return String(message).replace(/{{\s*([\w.]+)\s*}}/g, (ph, name) =>
    settings[name] === undefined
      ? ph
      : escape
        ? String(settings[name]).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])
        : String(settings[name]),
  );
}

const win = { t: CATALOG.__no_t__ ? undefined : tr };
const sandbox = { window: win, console, JSON };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox);

const cases = JSON.parse(process.argv[4]);
const out = cases.map((c) => win.formatSecurityReason(c.reason, c.data));
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def node():
    binary = which("node")
    if not binary:
        pytest.skip("node is not installed")
    return binary


def render(node, cases, catalog=None):
    harness = Path(__file__).resolve().parent / ".security_reason_harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    try:
        result = run(
            [node, str(harness), str(COMPONENT), dumps(catalog or {}), dumps(cases)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return loads(result.stdout)
    finally:
        harness.unlink(missing_ok=True)


class TestTheSentence:
    def test_an_appsec_challenge_reads_as_one(self, node):
        (sentence,) = render(node, [{"reason": "crowdsec", "data": {"source": "appsec", "action": "challenge", "http_status": 200}}])
        assert sentence == "CrowdSec AppSec: bot-detection challenge"

    def test_a_lapi_ban_names_its_scenario(self, node):
        (sentence,) = render(
            node,
            [{"reason": "crowdsec", "data": {"source": "lapi", "action": "ban", "scenario": "crowdsecurity/http-probing"}}],
        )
        assert sentence == "CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)"

    def test_a_captcha_reads_as_one(self, node):
        (sentence,) = render(node, [{"reason": "crowdsec", "data": {"source": "lapi", "action": "captcha"}}])
        assert sentence == "CrowdSec LAPI: captcha challenge"

    def test_a_json_string_payload_is_parsed(self, node):
        """The Reports table gets `data` as a dict; a ban row could carry it as stored JSON text."""
        (sentence,) = render(node, [{"reason": "crowdsec", "data": '{"source": "appsec", "action": "ban"}'}])
        assert sentence == "CrowdSec AppSec: request blocked"

    def test_an_unknown_action_falls_back_to_its_own_name(self, node):
        """A future CrowdSec remediation must degrade to something readable, not to nothing."""
        (sentence,) = render(node, [{"reason": "crowdsec", "data": {"source": "lapi", "action": "throttle"}}])
        assert sentence == "CrowdSec LAPI: throttle"

    def test_an_antibot_challenge_names_its_provider(self, node):
        """The reason antibot now records when it serves the challenge page
        (``antibot:set_challenge_reason``). The provider is the only thing that tells a captcha
        apart from a turnstile in the Reports table."""
        (sentence,) = render(
            node,
            [{"reason": "antibot", "data": {"source": "antibot", "provider": "captcha", "action": "challenge", "http_status": 200}}],
        )
        assert sentence == "Antibot challenge (captcha) served"

    def test_a_workflow_redirect_names_its_workflow(self, node):
        """``workflows:apply`` records ``{workflow, rule, action}``; the action type is config
        vocabulary out of the operator's own rule, interpolated raw like CrowdSec's scenario."""
        (sentence,) = render(
            node,
            [{"reason": "workflows", "data": {"workflow": "api-shield", "rule": "block-scanners", "action": "redirect"}}],
        )
        assert sentence == "Security workflow api-shield: redirect"

    def test_a_workflow_detection_reads_the_same_way(self, node):
        """The detect branch sets the same payload with the action it *would* have taken."""
        (sentence,) = render(node, [{"reason": "workflows", "data": {"workflow": "wp-guard", "rule": "r2", "action": "challenge"}}])
        assert sentence == "Security workflow wp-guard: challenge"

    def test_a_deferred_crowdsec_verdict_reads_like_the_immediate_one(self, node):
        """``CROWDSEC_DEFER_TO_WORKFLOWS``: ``workflows:enforce_deferred`` returns the deny, so the
        dispatcher stamps the row with ITS plugin id (``workflows``) while the payload is the
        bouncer's own verdict. Without the delegation the row would be a bare ``workflows`` token
        for an event the identical non-deferred row spells out."""
        (sentence,) = render(
            node,
            [{"reason": "workflows", "data": {"source": "appsec", "action": "ban", "scenario": "crowdsecurity/http-probing"}}],
        )
        assert sentence == "CrowdSec AppSec: request blocked (scenario: crowdsecurity/http-probing)"

    def test_the_reason_token_is_matched_case_insensitively(self, node):
        """Both halves of the report filter lowercase the reason; so does this."""
        (sentence,) = render(node, [{"reason": "AntiBot", "data": {"source": "antibot", "provider": "turnstile", "action": "challenge"}}])
        assert sentence == "Antibot challenge (turnstile) served"

    def test_the_catalog_wins_over_the_english_fallback(self, node):
        catalog = {
            "crowdsec": {"reason": {"source": {"appsec": "CrowdSec AppSec"}, "action": {"challenge": "défi anti-bot"}, "sentence": "{{source}} : {{action}}"}}
        }
        (sentence,) = render(node, [{"reason": "crowdsec", "data": {"source": "appsec", "action": "challenge"}}], catalog=catalog)
        assert sentence == "CrowdSec AppSec : défi anti-bot"


class TestItSaysNothingRatherThanSomethingWrong:
    def test_a_non_crowdsec_reason_is_left_alone(self, node):
        assert render(node, [{"reason": "modsecurity", "data": {"ids": ["942100"]}}]) == [None]

    def test_a_badbehavior_ban_payload_is_left_alone(self, node):
        """Bans carry badbehavior's per-IP counter list in reason_data; it is not a verdict."""
        assert render(node, [{"reason": "bad behavior", "data": [{"ip": "1.2.3.4", "count": 12}]}]) == [None]

    def test_a_crowdsec_row_with_no_verdict_is_left_alone(self, node):
        """Rows written before this shipped, and the pre-1.8 cache-hit path, carry an empty blob."""
        assert render(node, [{"reason": "crowdsec", "data": {}}, {"reason": "crowdsec", "data": None}]) == [None, None]

    def test_an_unparseable_payload_is_left_alone(self, node):
        assert render(node, [{"reason": "crowdsec", "data": "not json"}]) == [None]

    def test_an_antibot_row_without_a_provider_is_left_alone(self, node):
        """ "Antibot challenge () served" is worse than the raw token. ``reason_data`` is a
        free-text column a caller fills through the ban API, so the empty shape is reachable."""
        assert render(node, [{"reason": "antibot", "data": {"source": "antibot", "action": "challenge"}}]) == [None]

    def test_an_antibot_row_that_is_not_a_challenge_is_left_alone(self, node):
        """The sentence hard-codes the word "challenge"; a future antibot action must not be
        described as one."""
        assert render(node, [{"reason": "antibot", "data": {"source": "antibot", "provider": "captcha", "action": "ban"}}]) == [None]

    def test_a_workflows_row_without_a_name_is_left_alone(self, node):
        assert render(node, [{"reason": "workflows", "data": {"rule": "r1", "action": "redirect"}}]) == [None]

    def test_an_unknown_source_is_left_alone(self, node):
        """`source` is what makes the sentence's first half true; guessing it would be worse than
        showing the raw reason."""
        assert render(node, [{"reason": "crowdsec", "data": {"source": "elsewhere", "action": "ban"}}]) == [None]

    def test_an_inherited_property_name_is_not_a_known_source_or_action(self, node):
        """`reason_data` is a free-text column a caller fills through the ban API, so the lookup
        tables are indexed with attacker-chosen strings. Indexed by truthiness rather than by own
        property, `SOURCES["__proto__"]` is truthy and not callable — a throw inside the DataTables
        `render` callback, which aborts the whole table draw — and `SOURCES["constructor"]` renders
        the string "[object Object]" as a security verdict."""
        assert render(
            node,
            [
                {"reason": "crowdsec", "data": {"source": "__proto__", "action": "ban"}},
                {"reason": "crowdsec", "data": {"source": "constructor", "action": "ban"}},
                {"reason": "crowdsec", "data": {"source": "toString", "action": "ban"}},
            ],
        ) == [None, None, None]

    def test_a_value_that_cannot_become_a_string_does_not_abort_the_table(self, node):
        """The own-property guards run *after* `String(verdict.source)`, so they cannot see this
        one: `String({"toString": "not a function"})` raises `TypeError: Cannot convert object to
        primitive value`. From a DataTables `render` callback that aborts the whole draw, so the
        component swallows anything it cannot make a sentence out of."""
        assert render(
            node,
            [
                {"reason": "crowdsec", "data": {"source": "lapi", "action": {"toString": "x"}}},
                {"reason": "crowdsec", "data": {"source": {"toString": "x"}, "action": "ban"}},
                {"reason": "crowdsec", "data": {"source": "lapi", "action": "ban", "scenario": {"toString": "x"}}},
            ],
        ) == [None, None, None]

    def test_an_inherited_action_name_degrades_to_itself_rather_than_to_object_object(self, node):
        """An unknown action is shown as its own name (see the unknown-action case above); the
        point here is that an inherited one takes that same path instead of throwing or printing
        the prototype member it resolved to."""
        assert render(
            node,
            [
                {"reason": "crowdsec", "data": {"source": "appsec", "action": "__proto__"}},
                {"reason": "crowdsec", "data": {"source": "appsec", "action": "constructor"}},
            ],
        ) == ["CrowdSec AppSec: __proto__", "CrowdSec AppSec: constructor"]


class TestEscaping:
    def test_the_scenario_is_escaped_exactly_once(self, node):
        """It is CrowdSec's string, it is inserted as HTML, and a double escape is as visible a
        bug as no escape is a hole."""
        (sentence,) = render(
            node,
            [{"reason": "crowdsec", "data": {"source": "lapi", "action": "ban", "scenario": "<img src=x onerror=alert(1)>"}}],
        )
        assert "<img" not in sentence
        assert "&lt;img src=x onerror=alert(1)&gt;" in sentence
        assert "&amp;lt;" not in sentence

    def test_the_workflow_name_is_escaped_exactly_once(self, node):
        """The workflow name is the operator's own string and it is inserted as HTML."""
        (sentence,) = render(
            node,
            [{"reason": "workflows", "data": {"workflow": "<img src=x onerror=alert(1)>", "action": "redirect"}}],
        )
        assert "<img" not in sentence
        assert sentence == "Security workflow &lt;img src=x onerror=alert(1)&gt;: redirect"
        assert "&amp;lt;" not in sentence

    def test_the_antibot_provider_is_escaped_exactly_once(self, node):
        (sentence,) = render(
            node,
            [{"reason": "antibot", "data": {"source": "antibot", "provider": "<b>captcha</b>", "action": "challenge"}}],
        )
        assert sentence == "Antibot challenge (&lt;b&gt;captcha&lt;/b&gt;) served"
        assert "&amp;lt;" not in sentence

    def test_a_translated_label_is_not_double_escaped(self, node):
        catalog = {"crowdsec": {"reason": {"action": {"ban": "requête bloquée par l'IPS"}}}}
        (sentence,) = render(node, [{"reason": "crowdsec", "data": {"source": "lapi", "action": "ban"}}], catalog=catalog)
        assert sentence == "CrowdSec LAPI: requête bloquée par l&#39;IPS"
        assert "&amp;#39;" not in sentence


def test_the_route_ships_reason_data_for_exactly_the_reasons_this_file_renders():
    """`routes/bans.py` sends `reason_data` only for `_SENTENCE_REASONS`, to keep a payload no one
    reads off every draw of a 1000-row table. That gate and this component's own gate are one
    invariant in two files: widen the component and forget the route, and the Reports page picks
    the new reason up for free (`routes/reports.py` ships `data` unconditionally) while the Bans
    page silently keeps showing the bare token. Nothing else would go red.

    Deliberately NOT asserted against `_SELF_SERVED_REASONS` (`db_methods/metrics.py`): that one
    answers "which reasons are reports whatever their status", a different question that happens
    to have the same answer today."""
    import re

    route = (ROOT / "src" / "ui" / "app" / "routes" / "bans.py").read_text(encoding="utf-8")
    match = re.search(r"^_SENTENCE_REASONS = frozenset\(\{(.*?)\}\)$", route, re.S | re.M)
    assert match, "_SENTENCE_REASONS is gone from routes/bans.py"
    route_reasons = set(re.findall(r'"([^"]+)"', match.group(1)))
    assert route_reasons, "_SENTENCE_REASONS no longer spells its reasons as literals"

    component = COMPONENT.read_text(encoding="utf-8")
    table = re.search(r"^  const FORMATTERS = \{(.*?)^  \};$", component, re.S | re.M)
    assert table, "FORMATTERS is gone from security-reason.js"
    rendered = set(re.findall(r"^\s*(\w+):", table.group(1), re.M))
    assert rendered, "the component no longer dispatches on a literal reason"
    assert route_reasons == rendered


def test_it_still_renders_without_the_i18n_catalog(node):
    """The component is a `defer` script; if i18n.js ever stops defining window.t the page must
    still show the sentence rather than throw inside a DataTables render callback.

    All three branches, and the two new ones are the load-bearing cases. The CrowdSec branch
    composes its no-catalog fallback from labels that are themselves `t()` results, so it never
    reaches `fill()`. The antibot and workflows sentences are single templates carrying
    `{{placeholders}}`, and `t()` hands its fallback back **un-interpolated** when `window.t` is
    absent — `fill()` is the only thing standing between the user and a literal `{{provider}}`, and
    this is the only path on which it does anything at all."""
    sentences = render(
        node,
        [
            {"reason": "crowdsec", "data": {"source": "appsec", "action": "challenge"}},
            {"reason": "antibot", "data": {"source": "antibot", "provider": "captcha", "action": "challenge"}},
            {"reason": "workflows", "data": {"workflow": "api-shield", "action": "redirect"}},
        ],
        catalog={"__no_t__": True},
    )
    assert sentences == [
        "CrowdSec AppSec: bot-detection challenge",
        "Antibot challenge (captcha) served",
        "Security workflow api-shield: redirect",
    ]


class TestAValueIsNeverInterpolatedTwice:
    """`t()` has already substituted by the time `fill()` sees the string, so a second pass would
    re-scan the *values* it just injected. A workflow named `{{action}}` — an admin-supplied string
    — rendered as *Security workflow redirect: redirect*."""

    def test_a_placeholder_inside_a_value_is_left_alone(self, node):
        (with_catalog,) = render(node, [{"reason": "workflows", "data": {"workflow": "{{action}}", "action": "redirect"}}])
        (without_catalog,) = render(
            node,
            [{"reason": "workflows", "data": {"workflow": "{{action}}", "action": "redirect"}}],
            catalog={"__no_t__": True},
        )
        assert with_catalog == "Security workflow {{action}}: redirect"
        assert without_catalog == with_catalog

    def test_an_inherited_property_name_is_not_a_placeholder(self, node):
        """`fill()` indexes its values by name; a value carrying `{{constructor}}` must not print
        `function Object() { [native code] }` — the same own-property rule the lookup tables obey."""
        (sentence,) = render(
            node,
            [{"reason": "workflows", "data": {"workflow": "{{constructor}}", "action": "redirect"}}],
            catalog={"__no_t__": True},
        )
        assert sentence == "Security workflow {{constructor}}: redirect"
