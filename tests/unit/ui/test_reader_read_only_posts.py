"""QA-UI-6 Q6-H3: a reader's pages make POSTs that only read, and Biscuit refused them.

A POST is a `write` for the Biscuit check unless `app/models/biscuit.py` lists it as read-only. Only
the bans table and the reports page were listed, so a reader saw an empty `/services` table
(serverSide `POST /services/fetch`), an empty home chart (`/home/dashboard`), empty bans KPIs, an
empty reports chart, and a workflow editor whose live checks all failed.

Runs the shipped middleware with a real reader token against routes registered under their real
endpoint names and rules, both directions: every read-only POST passes, every write sibling is
still refused, and a write route whose path merely ends like a read-only one stays a write.
"""

import ast
from pathlib import Path

import pytest
from flask import Flask

from test_mfa_pending_access import _as, biscuit_module, keypair  # noqa: F401 (fixtures)

ROUTES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes"

READ_ONLY = (
    ("services.services_fetch", "/services/fetch", "/services/fetch"),
    ("bans.bans_fetch", "/bans/fetch", "/bans/fetch"),
    ("bans.bans_stats", "/bans/stats", "/bans/stats"),
    ("bans.bans_timeseries", "/bans/timeseries", "/bans/timeseries"),
    ("home.home_dashboard", "/home/dashboard", "/home/dashboard"),
    ("reports.reports_dashboard", "/reports/dashboard", "/reports/dashboard"),
    ("reports.reports_fetch", "/reports/fetch", "/reports/fetch"),
    ("workflows.workflows_test", "/workflows/<string:workflow_id>/test", "/workflows/wf1/test"),
    ("workflows.workflows_validate", "/workflows/<string:workflow_id>/validate", "/workflows/wf1/validate"),
)

WRITES = (
    ("services.services_delete", "/services/delete", "/services/delete"),
    ("services.services_convert", "/services/convert", "/services/convert"),
    ("bans.bans_ban", "/bans/ban", "/bans/ban"),
    ("workflows.workflows_save", "/workflows/<string:workflow_id>/save", "/workflows/wf1/save"),
    # A write route whose PATH ends like a read-only one: the old suffix match read it as `read`.
    ("configs.configs_edit", "/configs/<string:service>/<string:config_type>/<string:name>", "/configs/x/services/fetch"),
    ("configs.configs_edit", "/configs/<string:service>/<string:config_type>/<string:name>", "/configs/x/bans/fetch"),
)


@pytest.fixture
def app(biscuit_module, keypair, tmp_path):  # noqa: F811
    public_key = tmp_path / "biscuit.pub"
    public_key.write_text(str(keypair.public_key))

    application = Flask("bw_ui_reader_posts_test")
    application.secret_key = "test"
    application.config.update(BISCUIT_PUBLIC_KEY_PATH=str(public_key), CHECK_PRIVATE_IP=False)
    biscuit_module.BiscuitMiddleware(application)

    for endpoint, rule, _ in dict.fromkeys(READ_ONLY + WRITES):
        if rule not in {r.rule for r in application.url_map.iter_rules()}:
            application.add_url_rule(rule, endpoint=endpoint, view_func=lambda **_: "reached", methods=["POST"])
    return application


@pytest.mark.parametrize("endpoint,rule,path", READ_ONLY)
def test_a_reader_reaches_every_read_only_post(app, biscuit_module, keypair, endpoint, rule, path):  # noqa: F811
    response = _as(app, biscuit_module, keypair, "reader").post(path)

    assert response.status_code == 200, f"POST {path} ({endpoint}) refused to a reader: {response.get_data(as_text=True)!r}"


@pytest.mark.parametrize("endpoint,rule,path", WRITES)
def test_a_reader_is_still_refused_every_write(app, biscuit_module, keypair, endpoint, rule, path):  # noqa: F811
    response = _as(app, biscuit_module, keypair, "reader").post(path)

    assert response.status_code == 403, f"POST {path} ({endpoint}) let a reader write"


def test_a_writer_still_writes(app, biscuit_module, keypair):  # noqa: F811
    assert _as(app, biscuit_module, keypair, "writer").post("/services/delete").status_code == 200


def _post_views():
    """`{endpoint: rule}` for every POST view the UI routes register."""
    views = {}
    for path in ROUTES.glob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and ast.unparse(decorator.func).endswith(".route") and "POST" in ast.unparse(decorator):
                    blueprint = ast.unparse(decorator.func).rsplit(".", 1)[0]
                    views.setdefault(f"{blueprint}.{node.name}", set()).add(decorator.args[0].value)
    return views


def test_the_allowlist_names_real_post_views_only(biscuit_module):  # noqa: F811
    """A renamed view would silently fall out of the allowlist; a new entry must be a real route."""
    views = _post_views()

    assert biscuit_module.READ_ONLY_POST_ENDPOINTS <= set(views), biscuit_module.READ_ONLY_POST_ENDPOINTS - set(views)
    rules = {rule for endpoint in biscuit_module.READ_ONLY_POST_ENDPOINTS for rule in views[endpoint]}
    assert biscuit_module.READ_ONLY_POST_RULES == rules


def test_the_test_matches_the_shipped_views():
    views = _post_views()
    for endpoint, rule, _ in READ_ONLY + WRITES:
        if endpoint != "configs.configs_edit":
            assert rule in views.get(endpoint, set()), (endpoint, rule)
