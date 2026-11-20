"""Real Flask routing and signed-reader authorization across OSS and core plugins."""

import ast
from functools import wraps
from importlib import import_module
from inspect import unwrap
from os import environ
from pathlib import Path
from shutil import copytree
from unittest.mock import patch

import pytest
from werkzeug.routing import IntegerConverter, PathConverter, UnicodeConverter

from _ui_core_main import LoadedMain
from reader_route_manifest import ROUTE_CLASSES

ROOT = Path(__file__).resolve().parents[4]
# Prefixes present on Database/UIDatabase; the catalog test prevents stale entries.
MUTATOR_PREFIXES = ("add_", "create_", "delete_", "update_", "upsert_", "set_", "save_", "checked_changes")
INSTANCE_MUTATORS = frozenset({"reload_instances", "ban", "unban"})
INSTANCE_READS = frozenset(
    {
        "get_instances",
        "get_bans",
        "get_reports",
        "get_report_data",
        "get_reports_pane_counts",
        "get_reports_query",
        "get_home_aggregates",
        "get_metrics",
        "get_ping",
        "get_data",
    }
)


def loaded_app_with_core_plugins(tmp_path):
    # Include the optional public probe so every shipped route is inventoried.
    with patch.dict(environ, {"ENABLE_HEALTHCHECK": "yes"}):
        loaded = LoadedMain(tmp_path)
    loaded.reset()
    for ui in (ROOT / "src/common/core").glob("*/ui"):
        target = tmp_path / "core" / ui.parent.name
        copytree(ui, target / "ui")
        (target / "plugin.json").write_bytes((ui.parent / "plugin.json").read_bytes())
    loaded.main.refresh_app_context()
    return loaded


@pytest.fixture
def matrix_app(tmp_path, monkeypatch):
    loaded = loaded_app_with_core_plugins(tmp_path)
    # Patch imported path aliases too; no business/scratch root may touch the checkout or host.
    modules = {import_module("app.routes." + name) for name in ("plugins", "utils", "cache")}
    modules.add(loaded.main)
    le = unwrap(loaded.app.view_functions["letsencrypt.letsencrypt_fetch"]).__globals__
    monkeypatch.setitem(le, "SCRATCH_ROOT", str(tmp_path / "ui/letsencrypt"))
    monkeypatch.setitem(le, "WORK_DIR_ROOT", str(tmp_path / "ui/letsencrypt/work"))
    monkeypatch.setitem(le, "LE_CACHE_DIR", str(tmp_path / "cache/letsencrypt"))
    monkeypatch.setitem(le, "LOGS_DIR", str(tmp_path / "ui/letsencrypt/log"))
    consistency = import_module("letsencrypt_consistency")
    monkeypatch.setattr(consistency, "LE_CACHE_LOCK_PATH", tmp_path / "cache/letsencrypt.lock")
    for module in modules:
        if hasattr(module, "TMP_DIR"):
            monkeypatch.setattr(module, "TMP_DIR", tmp_path / "ui")
    loaded.deps.BW_INSTANCES_UTILS.get_bans.return_value = []
    loaded.deps.BW_INSTANCES_UTILS.get_reports_query.return_value = {"data": [], "total": 0, "filtered": 0, "pane_counts": {}}
    loaded.deps.BW_INSTANCES_UTILS.get_report_data.return_value = {"message": "fixture"}
    loaded.db.get_jobs_cache_files.return_value = []
    monkeypatch.setattr(import_module("app.routes.bans"), "get_redis_client", lambda: None)
    try:
        yield loaded
    finally:
        loaded.close()


def recorder_for(view):
    calls = []

    @wraps(view)
    def recorder(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok", 200

    recorder.calls = calls
    return recorder


def record_views(loaded, monkeypatch):
    recorders = {endpoint: recorder_for(view) for endpoint, view in loaded.app.view_functions.items()}
    for endpoint, recorder in recorders.items():
        monkeypatch.setitem(loaded.app.view_functions, endpoint, recorder)
    return recorders


def route_url(loaded, triple, values=None):
    endpoint, path, method = triple
    rule = next(r for r in loaded.app.url_map.iter_rules() if r.endpoint == endpoint and r.rule == path and method in r.methods)
    args = {}
    for name, converter in rule._converters.items():
        if isinstance(converter, IntegerConverter):
            args[name] = 1
        elif isinstance(converter, PathConverter):
            args[name] = "a/b"
        elif isinstance(converter, UnicodeConverter):
            args[name] = "x"
        else:
            raise AssertionError(f"Classify converter {type(converter).__name__} for {triple}")
    args.update(values or {})
    return rule.build(args)[1]


def signed_client(loaded, *, reader=True):
    from biscuit_auth import PrivateKey
    from app.models.biscuit import BiscuitTokenFactory

    client = loaded.client(admin=not reader, roles=("reader",) if reader else ("admin",), permissions=("read",) if reader else ("read", "write"))
    with loaded.app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        token = BiscuitTokenFactory(PrivateKey((loaded.lib / ".biscuit_private_key").read_text())).create_token_for_role(
            "reader" if reader else "admin", "alice"
        )
    with client.session_transaction() as sess:
        sess["biscuit_token"] = token.to_base64()
    return client


def mutation_attempts(loaded):
    return (
        [str(c) for c in loaded.db.mock_calls if c[0].startswith(MUTATOR_PREFIXES)]
        + [str(c) for c in loaded.deps.BW_INSTANCES_UTILS.mock_calls if c[0].split(".")[0] in INSTANCE_MUTATORS]
        + [f"config task: {fn}" for fn in loaded.deps.CONFIG_TASKS_EXECUTOR.submitted]
    )


def triples(*classes):
    return [key for key, (cls, _) in ROUTE_CLASSES.items() if cls in classes]


def test_manifest_matches_url_map(matrix_app):
    actual = {
        (r.endpoint, r.rule, method)
        for r in matrix_app.app.url_map.iter_rules()
        if r.endpoint not in {"static", "probe"} and not r.endpoint.endswith(".static")
        for method in r.methods - {"HEAD", "OPTIONS"}
    }
    assert actual == set(ROUTE_CLASSES), f"Missing classifications: {actual - set(ROUTE_CLASSES)}; stale: {set(ROUTE_CLASSES) - actual}"
    for cls, reason in ROUTE_CLASSES.values():
        assert cls in {"public", "read", "self_service", "read_post", "write", "delegated"}
        assert reason or cls in {"read", "write"}
    tree = ast.parse(Path(__file__).with_name("reader_route_manifest.py").read_text())
    manifest = next(n.value for n in tree.body if isinstance(n, ast.Assign))
    assert len(manifest.keys) == len(ROUTE_CLASSES), "Duplicate manifest triple"


def test_recorder_preserves_view_attributes(matrix_app):
    assert recorder_for(matrix_app.app.view_functions["letsencrypt.letsencrypt_fetch"]).bw_read_only_post is True


@pytest.mark.parametrize("triple", triples("write", "delegated"))
def test_reader_write_routes_denied_before_view(matrix_app, monkeypatch, triple):
    recorders = record_views(matrix_app, monkeypatch)
    response = signed_client(matrix_app).open(route_url(matrix_app, triple), method=triple[2])
    assert response.status_code == 403, triple
    assert recorders[triple[0]].calls == [], triple


@pytest.mark.parametrize("triple", triples("read", "self_service", "read_post"))
def test_reader_non_write_routes_reach_view(matrix_app, monkeypatch, triple):
    recorders = record_views(matrix_app, monkeypatch)
    response = signed_client(matrix_app).open(route_url(matrix_app, triple), method=triple[2])
    assert response.status_code != 403, triple
    assert len(recorders[triple[0]].calls) == 1, (triple, response.status_code)


def test_reader_without_token_still_denied_write(matrix_app, monkeypatch):
    recorders = record_views(matrix_app, monkeypatch)
    seen = set()
    for triple in triples("write"):
        blueprint = triple[0].split(".")[0]
        if blueprint in seen:
            continue
        seen.add(blueprint)
        client = signed_client(matrix_app)
        with client.session_transaction() as sess:
            sess.pop("biscuit_token")
        response = client.post(route_url(matrix_app, triple))
        assert response.status_code == 403, triple
        assert recorders[triple[0]].calls == [], triple


def test_reader_options_head_on_write_rules_never_run_view(matrix_app, monkeypatch):
    recorders = record_views(matrix_app, monkeypatch)
    client = signed_client(matrix_app)
    for triple in triples("write", "delegated"):
        for recorder in recorders.values():
            recorder.calls.clear()
        response = client.options(route_url(matrix_app, triple))
        assert response.status_code < 400, triple
        assert recorders[triple[0]].calls == [], triple
        # POST-only rules must reject HEAD before dispatch (mixed rules legitimately run GET).
        if (triple[0], triple[1], "GET") not in ROUTE_CLASSES:
            client.head(route_url(matrix_app, triple))
            assert recorders[triple[0]].calls == [], triple


def test_mutator_catalog_matches_real_methods():
    from Database import Database
    from app.models.ui_database import UIDatabase
    from app.models.instance import InstancesUtils

    db_methods = {name for cls in (Database, UIDatabase) for name in dir(cls) if callable(getattr(cls, name)) and not name.startswith("_")}
    for prefix in MUTATOR_PREFIXES:
        assert any(name.startswith(prefix) for name in db_methods), prefix
    candidates = ("add_", "create_", "delete_", "update_", "upsert_", "remove_", "set_", "save_", "insert_", "edit_", "checked_changes")
    assert {p for p in candidates if any(n.startswith(p) for n in db_methods)} == set(MUTATOR_PREFIXES)
    actual = {name for name in dir(InstancesUtils) if not name.startswith("_") and callable(getattr(InstancesUtils, name))}
    assert actual == INSTANCE_MUTATORS | INSTANCE_READS
    assert not INSTANCE_MUTATORS & INSTANCE_READS


@pytest.mark.parametrize("triple", triples("read_post"))
def test_read_post_views_make_no_business_mutation(matrix_app, triple):
    client = signed_client(matrix_app)
    response = client.post(route_url(matrix_app, triple), data={"draw": "1", "report_id": "fixture", "force": "true"}, headers={"Sec-Fetch-Mode": "cors"})
    assert response.status_code == 200, (triple, response.data)
    assert mutation_attempts(matrix_app) == []
