"""CrowdSec UI page contracts."""

import importlib.util
import json
from pathlib import Path
from shutil import which
from subprocess import run
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
ROUTE = ROOT / "src" / "ui" / "app" / "routes" / "crowdsec.py"
CROWDSEC_SCRIPT = ROOT / "src" / "ui" / "app" / "static" / "js" / "pages" / "crowdsec.js"
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"
UNBAN_FORM = {
    "connection": "instance-a",
    "decision_id": "7",
    "scope": "Ip",
    "value": "192.0.2.10",
    "decision_type": "ban",
    "confirmed": "yes",
}


def test_crowdsec_report_snapshot_uses_action_when_remediation_is_missing():
    node = which("node")
    if not node:
        pytest.skip("node is not installed")

    harness = r"""
const fs = require("fs");
const vm = require("vm");
const sandbox = {
  document: { addEventListener() {} },
  window: { addEventListener() {} },
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
const report = JSON.parse(process.argv[2]);
console.log(JSON.stringify(sandbox.getCrowdSecReportSnapshot(report)));
"""
    report = {
        "data": {
            "crowdsec": {
                "captured_at": "2026-09-23T10:00:00Z",
                "source": "failure_policy",
                "action": "ban",
            }
        }
    }
    result = run(
        [node, "-e", harness, str(CROWDSEC_SCRIPT), json.dumps(report)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    snapshot = json.loads(result.stdout)
    assert snapshot.get("remediation") == "ban"


def test_crowdsec_fetch_rejects_redirected_and_non_json_responses():
    node = which("node")
    if not node:
        pytest.skip("node is not installed")

    harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const match = source.match(/  const fetchJson = async \(url, options\) => \{[\s\S]*?\n  \};/);
if (!match) throw new Error("fetchJson not found");
const responses = [
  { ok: true, redirected: true, json: async () => ({ page: "login" }) },
  { ok: true, redirected: false, json: async () => { throw new Error("HTML response"); } },
];
const sandbox = {
  fetch: async () => responses.shift(),
  t: (_key, fallback) => fallback,
};
vm.createContext(sandbox);
vm.runInContext(`${match[0]}\nglobalThis.invoke = fetchJson;`, sandbox);
Promise.allSettled([
  sandbox.invoke("/crowdsec/unban", { method: "POST" }),
  sandbox.invoke("/crowdsec/unban", { method: "POST" }),
]).then((results) => {
  const errors = results.filter((result) => result.status === "rejected");
  if (errors.length !== 2 || errors.some((result) => result.reason.message !== "The CrowdSec request failed.")) {
    process.exitCode = 1;
  }
  console.log(JSON.stringify(errors.map((result) => result.reason.message)));
});
"""
    result = run(
        [node, "-e", harness, str(CROWDSEC_SCRIPT)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        "The CrowdSec request failed.",
        "The CrowdSec request failed.",
    ]


def test_crowdsec_removal_requires_api_confirmation():
    node = which("node")
    if not node:
        pytest.skip("node is not installed")

    harness = r"""
const fs = require("fs");
const vm = require("vm");
const sandbox = {
  document: { addEventListener() {} },
  window: { addEventListener() {} },
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
console.log(JSON.stringify([undefined, {}, { removed: false }, { removed: 1 }, { removed: true }]
  .map(sandbox.isCrowdSecRemovalConfirmed)));
"""
    result = run(
        [node, "-e", harness, str(CROWDSEC_SCRIPT)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [False, False, False, False, True]


def _load_route(api_client):
    assert ROUTE.is_file(), "CrowdSec UI route has not been added"
    spec = importlib.util.spec_from_file_location("app.routes._crowdsec_page_test", ROUTE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = api_client
    app_utils = ModuleType("app.utils")
    app_utils.LOGGER = Mock()
    app_utils.is_readonly_request = lambda readonly: readonly or "write" not in module.current_user.list_permissions
    with patch.dict(
        "sys.modules",
        {
            "app.dependencies": dependencies,
            "app.utils": app_utils,
            "app.routes._crowdsec_page_test": module,
        },
    ):
        spec.loader.exec_module(module)
    return module


def _post_unban(module, client, *, form=None, admin=True, permissions=("read", "write")):
    client.readonly = False
    module.current_user = Mock(
        admin=admin,
        get_id=Mock(return_value="admin"),
        list_permissions=set(permissions),
    )
    with Flask(__name__).test_request_context("/crowdsec/unban", method="POST", data=form if form is not None else UNBAN_FORM):
        return module.crowdsec_unban.__wrapped__()


def test_crowdsec_page_uses_the_1_7_page_endpoint_name():
    module = _load_route(Mock())

    app = Flask(__name__)
    app.register_blueprint(module.crowdsec)

    assert "crowdsec.crowdsec_page" in app.view_functions
    assert any(rule.rule == "/crowdsec" and rule.endpoint == "crowdsec.crowdsec_page" for rule in app.url_map.iter_rules())


@pytest.mark.parametrize(
    ("template_name", "expected"),
    [
        ("crowdsec.html", "/crowdsec/connections"),
        ("bans.html", 'id="crowdsec-url" value="/crowdsec"'),
        ("reports.html", 'id="crowdsec-url" value="/crowdsec"'),
    ],
)
def test_crowdsec_templates_render_urls_from_the_registered_page_endpoint(template_name, expected):
    module = _load_route(Mock())
    app = Flask(__name__)
    app.register_blueprint(module.crowdsec)
    app.add_url_rule("/bans", endpoint="bans", view_func=lambda: "")
    app.add_url_rule("/reports", endpoint="reports", view_func=lambda: "")
    url_adapter = app.url_map.bind("example.test")
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        undefined=ChainableUndefined,
        autoescape=True,
    )
    env.globals.update(
        url_for=lambda endpoint, **values: url_adapter.build(endpoint, values),
        _=lambda key, *_args, **_kwargs: key,
        csrf_token=lambda: "csrf-token",
    )
    rendered = env.get_template(template_name).render(
        current_user=Mock(admin=True),
        is_readonly=False,
        user_readonly=False,
        columns_preferences_defaults={"bans": [], "reports": []},
        columns_preferences={},
        style_nonce="",
        script_nonce="",
        theme="light",
    )

    assert expected in rendered


def test_decisions_normalize_ip_and_pass_bounded_filters_to_api_client():
    client = Mock()
    client.get_crowdsec_decisions.return_value = {"decisions": []}
    module = _load_route(client)

    with Flask(__name__).test_request_context("/crowdsec/decisions?connection=instance-a&ip=2001%3A0db8%3A%3A1&origin=lists&scenario=scan&offset=10&limit=20"):
        response = module.crowdsec_decisions.__wrapped__()

    assert response.get_json() == {"decisions": []}
    client.get_crowdsec_decisions.assert_called_once_with("instance-a", ip="2001:db8::1", origin="lists", scenario="scan", offset=10, limit=20)


def test_crowdsec_reads_pass_through_api_502_details():
    client = Mock()
    module = _load_route(client)
    client.get_crowdsec_connections.side_effect = module.ApiUnavailableError("API returned 502: LAPI timeout")

    with Flask(__name__).test_request_context("/crowdsec/connections"):
        response, status = module.crowdsec_connections.__wrapped__()

    assert status == 502
    assert response.get_json() == {"error": "LAPI timeout"}


def test_decision_removal_is_denied_in_readonly_mode():
    client = Mock(readonly=True)
    module = _load_route(client)
    module.current_user = Mock(admin=True)

    with Flask(__name__).test_request_context(
        "/crowdsec/unban",
        method="POST",
        data={"connection": "instance-a", "decision_id": "7", "scope": "Ip", "value": "192.0.2.10", "decision_type": "ban", "confirmed": "yes"},
    ):
        response, status = module.crowdsec_unban.__wrapped__()

    assert status == 403
    assert response.get_json()["error"] == "Database is in read-only mode"
    client.remove_crowdsec_decision.assert_not_called()


def test_decision_removal_is_denied_for_non_admins():
    client = Mock()
    module = _load_route(client)

    response, status = _post_unban(module, client, admin=False)

    assert status == 403
    assert response.get_json()["error"] == "CrowdSec decision removal is restricted to administrators"
    client.remove_crowdsec_decision.assert_not_called()


def test_decision_removal_is_denied_without_user_write_permission():
    client = Mock()
    module = _load_route(client)

    response, status = _post_unban(module, client, permissions=("read",))

    assert status == 403
    assert response.get_json()["error"] == "You do not have the write permission"
    client.remove_crowdsec_decision.assert_not_called()


def test_decision_removal_requires_explicit_confirmation():
    client = Mock()
    module = _load_route(client)
    form = {key: value for key, value in UNBAN_FORM.items() if key != "confirmed"}

    response, status = _post_unban(module, client, form=form)

    assert status == 400
    assert response.get_json()["error"] == "Explicit confirmation is required"
    client.remove_crowdsec_decision.assert_not_called()


def test_decision_removal_rejects_a_scope_target_mismatch():
    client = Mock()
    module = _load_route(client)
    form = {**UNBAN_FORM, "scope": "Range"}

    response, status = _post_unban(module, client, form=form)

    assert status == 400
    assert response.get_json()["error"] == "CrowdSec decision scope does not match its target"
    client.remove_crowdsec_decision.assert_not_called()


@pytest.mark.parametrize("status_code", [403, 404])
def test_decision_removal_passes_through_api_client_errors(status_code):
    client = Mock()
    module = _load_route(client)
    client.remove_crowdsec_decision.side_effect = module.ApiClientError("CrowdSec removal denied", status_code=status_code)

    response, status = _post_unban(module, client)

    assert status == status_code
    assert response.get_json() == {"error": "CrowdSec removal denied"}


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_message"),
    [
        ("API returned 502: LAPI timeout", 502, "LAPI timeout"),
        ("Cannot reach API at http://api.test", 503, "CrowdSec service unavailable"),
    ],
)
def test_decision_removal_reports_api_unavailable_errors(error, expected_status, expected_message):
    client = Mock()
    module = _load_route(client)
    client.remove_crowdsec_decision.side_effect = module.ApiUnavailableError(error)

    response, status = _post_unban(module, client)

    assert status == expected_status
    assert response.get_json() == {"error": expected_message}
