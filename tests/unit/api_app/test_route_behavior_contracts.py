"""Caller-visible route results and writes, with DB/instance boundaries isolated."""

from datetime import datetime

import pytest

from _api_http_helpers import ADMIN_HEADERS
from test_configs_move_authz import _token
import test_route_permission_matrix

import app.routers.configs as configs
import app.routers.instances as instances
from ApiCaller import MIN_RELOAD_TIMEOUT

api_routes = test_route_permission_matrix.api_routes


def call(api_routes, method, path, **kwargs):
    return api_routes.client.request(method, path, headers=ADMIN_HEADERS, **kwargs)


@pytest.mark.parametrize("endpoint", ["/instances", "/instances/node"])
def test_instance_dates_are_iso_and_missing_last_seen_is_null(api_routes, endpoint):
    response = call(api_routes, "GET", endpoint)
    assert response.status_code == 200
    row = response.json().get("instance") or response.json()["instances"][0]
    assert datetime.fromisoformat(row["creation_date"]) == api_routes.instant
    assert row["last_seen"] is None


def test_instance_last_seen_is_serialized(api_routes):
    api_routes.database.get_instance.side_effect = None
    api_routes.database.get_instance.return_value = {"hostname": "node", "creation_date": api_routes.instant, "last_seen": api_routes.instant}
    response = call(api_routes, "GET", "/instances/node")
    assert datetime.fromisoformat(response.json()["instance"]["last_seen"]) == api_routes.instant


@pytest.mark.parametrize("action", ["ping", "reload", "stop"])
def test_broadcast_failures_return_bad_gateway(api_routes, action):
    api_routes.broadcast.send_to_apis.return_value = (False, None)
    response = call(api_routes, "GET" if action == "ping" else "POST", f"/instances/{action}")
    assert response.status_code == 502
    expected = {"status": "error", "msg": "internal error"} if action == "ping" else {"status": "error"}
    assert response.json() == expected


@pytest.mark.parametrize("single", [False, True])
@pytest.mark.parametrize("test_arg", [None, "true", "false"])
def test_reload_passes_test_flag_and_minimum_timeout(api_routes, single, test_arg):
    path = "/instances/node/reload" if single else "/instances/reload"
    response = call(api_routes, "POST", path, params={} if test_arg is None else {"test": test_arg})
    assert response.status_code == 200
    caller = api_routes.single if single else api_routes.broadcast
    caller.send_to_apis.assert_called_once_with("POST", f"/reload?test={'no' if test_arg == 'false' else 'yes'}", timeout=(5, MIN_RELOAD_TIMEOUT))


@pytest.mark.parametrize(
    "result,body",
    [
        ((False, "connection refused", None, None), {"status": "error", "msg": "connection refused"}),
        ((True, "", 503, {"msg": "busy"}), {"status": "error", "msg": "busy"}),
        ((False, "", None, None), {"status": "error", "msg": "internal error"}),
        ((True, "", 200, "pong"), {"status": "ok"}),
        ((True, "", 200, {"status": "ok", "uptime": 12}), {"status": "ok", "uptime": 12}),
    ],
)
def test_ping_one_preserves_response_or_reports_upstream_error(api_routes, result, body):
    api_routes.api.request.return_value = result
    response = call(api_routes, "GET", "/instances/node/ping")
    assert response.status_code == (200 if result[0] and result[2] == 200 else 502)
    assert response.json() == body
    api_routes.api.request.assert_called_once_with("GET", "/ping")


@pytest.mark.parametrize("action", ["reload", "stop"])
def test_single_action_upstream_failure(api_routes, action):
    api_routes.single.send_to_apis.return_value = (False, {})
    api_routes.api.request.return_value = (True, "", 503, {})
    response = call(api_routes, "POST", f"/instances/node/{action}")
    assert response.status_code == 502 and response.json() == {"status": "error"}


@pytest.mark.parametrize(
    "body,expected",
    [
        ({"hostname": "http://new-node:5050"}, {"hostname": "new-node", "port": 5050, "listen_https": False, "https_port": 5443}),
        ({"hostname": "https://new-node:5444"}, {"hostname": "new-node", "port": 5000, "listen_https": True, "https_port": 5444}),
        (
            {"hostname": "[2001:db8::1]", "port": 5051, "https_port": 5445, "listen_https": True, "name": "edge", "method": "api", "server_name": "custom"},
            {"hostname": "2001:db8::1", "port": 5051, "listen_https": True, "https_port": 5445, "name": "edge", "method": "api", "server_name": "custom"},
        ),
    ],
)
def test_create_instance_normalizes_endpoint_and_persists_returned_values(api_routes, body, expected):
    response = call(api_routes, "POST", "/instances", json=body)
    assert response.status_code == 201, response.text
    saved = api_routes.database.add_instance.call_args.kwargs
    assert (
        saved
        == {"hostname": "new-node", "port": 5000, "listen_https": False, "https_port": 5443, "name": "manual instance", "method": "ui", "server_name": "bwapi"}
        | expected
    )
    assert response.json() == {"status": "success", "instance": saved}


@pytest.mark.parametrize("field,value", [("port", 0), ("port", 65536), ("https_port", -1), ("https_port", 65536)])
def test_create_instance_rejects_invalid_ports_without_writing(api_routes, field, value):
    response = call(api_routes, "POST", "/instances", json={"hostname": "node", field: value})
    assert response.status_code == 422
    assert response.json() == {"status": "error", "message": f"Invalid {field}: Port must be between 1 and 65535"}
    api_routes.database.add_instance.assert_not_called()


def test_create_instance_rejects_bad_endpoint_before_database_write(api_routes):
    response = call(api_routes, "POST", "/instances", json={"hostname": "http://node:bad"})
    assert response.status_code == 422
    assert response.json()["status"] == "error" and response.json()["message"]
    api_routes.database.add_instance.assert_not_called()


def test_invalid_configured_http_port_fails_closed(api_routes, monkeypatch):
    monkeypatch.setattr(instances.api_config, "internal_api_port", "bad")
    response = call(api_routes, "POST", "/instances", json={"hostname": "node"})
    assert response.status_code == 500 and response.json() == {"status": "error", "message": "internal error"}
    api_routes.database.add_instance.assert_not_called()


def test_configured_https_port_failure_uses_default(api_routes):
    api_routes.database.get_config.side_effect = RuntimeError("DB unavailable")
    response = call(api_routes, "POST", "/instances", json={"hostname": "node"})
    assert response.status_code == 201
    assert api_routes.database.add_instance.call_args.kwargs["https_port"] == 5443


@pytest.mark.parametrize("error,code", [("already exists", 400), ("database read-only", 400), ("DB failed", 500)])
def test_instance_create_db_errors_are_visible(api_routes, error, code):
    api_routes.database.add_instance.return_value = error
    response = call(api_routes, "POST", "/instances", json={"hostname": "node"})
    assert response.status_code == code and response.json() == {"status": "error", "message": error}


@pytest.mark.parametrize("error,code", [("does not exist", 400), ("read-only", 400), ("DB failed", 500)])
def test_instance_update_errors_do_not_fetch_a_success_response(api_routes, error, code):
    api_routes.database.update_instance_fields.return_value = error
    response = call(api_routes, "PATCH", "/instances/node", json={"port": 5001, "listen_https": True, "https_port": 5444})
    assert response.status_code == code and response.json() == {"status": "error", "message": error}
    api_routes.database.get_instance.assert_not_called()


def test_instance_update_invalid_port_does_not_write(api_routes):
    response = call(api_routes, "PATCH", "/instances/node", json={"port": 0})
    assert response.status_code == 422 and "Port must be between" in response.json()["message"]
    api_routes.database.update_instance_fields.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_missing_instance_is_not_found(api_routes, method):
    api_routes.database.get_instance.side_effect = None
    api_routes.database.get_instance.return_value = {}
    response = call(api_routes, method, "/instances/missing")
    assert response.status_code == 404 and response.json() == {"status": "error", "message": "Instance missing not found"}
    api_routes.database.delete_instance.assert_not_called()


def test_external_instance_is_protected_from_delete(api_routes):
    api_routes.database.get_instance.side_effect = lambda *_: {"hostname": "node", "method": "autoconf"}
    response = call(api_routes, "DELETE", "/instances/node")
    assert response.status_code == 400 and response.json()["message"] == "Instance node is not a UI/API instance"
    api_routes.database.delete_instance.assert_not_called()


def test_delete_instance_db_error_is_not_success(api_routes):
    api_routes.database.delete_instance.return_value = "DB failed"
    response = call(api_routes, "DELETE", "/instances/node")
    assert response.status_code == 500 and response.json() == {"status": "error", "message": "DB failed"}


@pytest.mark.parametrize(
    "selection,error,code", [(["node", "external", "missing"], "", 200), (["external", "missing"], "", 404), (["node", "missing"], "DB failed", 500)]
)
def test_bulk_instance_delete_skips_unowned_and_missing_rows(api_routes, selection, error, code):
    api_routes.database.get_instances.side_effect = lambda: [{"hostname": "node", "method": "ui"}, {"hostname": "external", "method": "autoconf"}]
    api_routes.database.delete_instances.return_value = error
    response = call(api_routes, "DELETE", "/instances", json={"instances": selection})
    assert response.status_code == code
    assert response.json()["skipped"] == [name for name in selection if name != "node"]
    if "node" in selection:
        api_routes.database.delete_instances.assert_called_once_with(["node"])
        assert response.json().get("deleted") == (["node"] if not error else None)
    else:
        api_routes.database.delete_instances.assert_not_called()


@pytest.mark.parametrize("with_data", [True, False])
def test_config_list_filters_and_normalizes_global_and_utf8(api_routes, with_data):
    api_routes.database.get_custom_configs.side_effect = lambda **_: [
        {"service_id": None, "type": "http", "name": "global", "data": None},
        {"service_id": "example", "type": "server_http", "name": "kept", "data": b"bad\xff", "is_draft": 1},
        {"service_id": "other", "type": "server_http", "name": "other", "data": "hidden"},
        {"service_id": "example", "type": "http", "name": "wrong-type", "data": "hidden"},
    ]
    response = call(
        api_routes, "GET", "/configs", params={"service": "example", "type": "server-http", "with_data": str(with_data).lower(), "with_drafts": "false"}
    )
    assert response.status_code == 200
    expected = {"service": "example", "type": "server_http", "name": "kept", "is_draft": True}
    if with_data:
        expected["data"] = "bad\ufffd"
    assert response.json() == {"status": "success", "configs": [expected]}
    api_routes.database.get_custom_configs.assert_called_once_with(with_drafts=False, with_data=with_data)


@pytest.mark.parametrize("data,decoded", [(None, ""), (b"bad\xff", "bad\ufffd"), ("plain", "plain")])
def test_global_config_output_decodes_content(api_routes, data, decoded):
    api_routes.database.get_custom_config.side_effect = lambda *_, **__: {"service_id": None, "type": "http", "name": "snippet", "data": data}
    response = call(api_routes, "GET", "/configs/global/http/snippet")
    assert response.status_code == 200
    assert response.json()["config"] == {"service": "global", "type": "http", "name": "snippet", "data": decoded, "is_draft": False}
    api_routes.database.get_custom_config.assert_called_once_with("http", "snippet", service_id=None, with_data=True)


@pytest.mark.parametrize("path", ["/configs/example/http/snippet", "/configs/example/http/snippet/upload"])
@pytest.mark.parametrize("mode", ["missing", "external", "template-rename", "unchanged"])
def test_config_update_refusals_never_write(api_routes, path, mode):
    current = {"service_id": "example", "type": "http", "name": "snippet", "data": b"old", "method": "api", "is_draft": True}
    if mode == "external":
        current["method"] = "autoconf"
    if mode == "template-rename":
        current["template"] = "template"
    api_routes.database.get_custom_config.side_effect = lambda *_, **__: None if mode == "missing" else current
    upload = path.endswith("/upload")
    kwargs = (
        {"files": {"file": ("renamed.conf" if mode == "template-rename" else "snippet.conf", b"old")}}
        if upload
        else {"json": {"name": "renamed"} if mode == "template-rename" else {}}
    )
    response = call(api_routes, "PATCH", path, **kwargs)
    code = {"missing": 404, "external": 403, "template-rename": 403, "unchanged": 400}[mode]
    message = {
        "missing": "Config not found",
        "external": "Config is not UI/API-managed and cannot be edited",
        "template-rename": "Renaming a template-based custom config is not allowed",
        "unchanged": "No values were changed",
    }[mode]
    assert response.status_code == code and response.json() == {"status": "error", "message": message}
    api_routes.database.upsert_custom_config.assert_not_called()


@pytest.mark.parametrize("upload", [False, True])
@pytest.mark.parametrize("error,code", [("read-only", 400), ("already exists", 400), ("does not exist", 400), ("DB failed", 500)])
def test_config_update_reports_db_errors(api_routes, upload, error, code):
    api_routes.database.upsert_custom_config.return_value = error
    kwargs = {"files": {"file": ("snippet.conf", b"new")}} if upload else {"json": {"data": "new"}}
    response = call(api_routes, "PATCH", "/configs/example/http/snippet" + ("/upload" if upload else ""), **kwargs)
    assert response.status_code == code and response.json() == {"status": "error", "message": error}


@pytest.mark.parametrize("upload", [False, True])
@pytest.mark.parametrize("destination", ["other", "global"])
def test_config_move_http_requires_source_and_destination(api_routes, upload, destination):
    path = "/configs/example/http/snippet" + ("/upload" if upload else "")
    kwargs = {"files": {"file": ("snippet.conf", b"new")}, "data": {"new_service": destination}} if upload else {"json": {"service": destination}}
    source = ("configs", "example", "config_update")
    denied = api_routes.client.patch(path, headers={"Authorization": f"Bearer {_token(source)}"}, **kwargs)
    assert denied.status_code == 403 and denied.json() == {"status": "error", "message": "Forbidden"}
    api_routes.database.upsert_custom_config.assert_not_called()
    allowed = api_routes.client.patch(path, headers={"Authorization": f"Bearer {_token(source, ('configs', destination, 'config_update'))}"}, **kwargs)
    assert allowed.status_code == 200 and allowed.json() == {"status": "success"}
    assert api_routes.database.upsert_custom_config.call_args.args[2]["service_id"] == (None if destination == "global" else destination)


@pytest.mark.parametrize("draft", [None, "false", "true"])
def test_upload_preserves_omitted_draft_and_normalizes_type(api_routes, draft):
    fields = {"new_type": "server-http", "new_name": "new_name"}
    if draft is not None:
        fields["new_is_draft"] = draft
    response = call(api_routes, "PATCH", "/configs/example/http/snippet/upload", data=fields, files={"file": ("ignored.conf", b"new\xff")})
    assert response.status_code == 200
    saved = api_routes.database.upsert_custom_config.call_args.args[2]
    assert saved == {"service_id": "example", "type": "server_http", "name": "new_name", "data": "new\ufffd", "method": "api", "is_draft": draft != "false"}


@pytest.mark.parametrize("upload", [False, True])
def test_unknown_destination_service_prevents_config_write(api_routes, upload):
    kwargs = {"files": {"file": ("snippet.conf", b"new")}, "data": {"new_service": "missing"}} if upload else {"json": {"service": "missing"}}
    response = call(api_routes, "PATCH", "/configs/example/http/snippet" + ("/upload" if upload else ""), **kwargs)
    assert response.status_code == 404 and response.json() == {"status": "error", "message": "Service not found"}
    api_routes.database.upsert_custom_config.assert_not_called()


@pytest.mark.parametrize("error,code", [("already exists", 400), ("read-only", 400), ("DB failed", 500)])
def test_create_config_error_status(api_routes, error, code):
    api_routes.database.upsert_custom_config.return_value = error
    response = call(api_routes, "POST", "/configs", json={"type": "http", "name": "snippet", "data": "new"})
    assert response.status_code == code and response.json() == {"status": "error", "message": error}


@pytest.mark.parametrize("upload", [False, True])
def test_config_creation_with_unknown_service_does_not_write(api_routes, upload):
    kwargs = (
        {"data": {"type": "http", "service": "missing"}, "files": {"files": ("snippet.conf", b"new")}}
        if upload
        else {"json": {"type": "http", "name": "snippet", "data": "new", "service": "missing"}}
    )
    response = call(api_routes, "POST", "/configs/upload" if upload else "/configs", **kwargs)
    assert response.status_code == 404 and response.json() == {"status": "error", "message": "Service not found"}
    api_routes.database.upsert_custom_config.assert_not_called()


@pytest.mark.parametrize("error", ["DB refused", RuntimeError("DB unavailable")])
def test_upload_partial_results_keep_success_and_per_file_errors(api_routes, error):
    api_routes.database.upsert_custom_config.side_effect = ["", error]
    response = call(api_routes, "POST", "/configs/upload", data={"type": "http"}, files=[("files", ("good.conf", b"new")), ("files", ("bad.conf", b"bad"))])
    assert response.status_code == 207
    assert response.json() == {"status": "partial", "created": ["global/http/good"], "errors": [{"file": "bad.conf", "error": str(error)}]}


def test_upload_invalid_derived_name_does_not_write(api_routes):
    response = call(api_routes, "POST", "/configs/upload", data={"type": "http"}, files={"files": ("---.conf", b"new")})
    assert response.status_code == 400 and response.json()["status"] == "error"
    assert response.json()["errors"][0]["error"] == configs.validate_config_name("")
    api_routes.database.upsert_custom_config.assert_not_called()


def test_upload_long_filename_truncates_to_supported_length(api_routes):
    response = call(api_routes, "POST", "/configs/upload", data={"type": "http"}, files={"files": ("z" * 300 + ".conf", b"new")})
    assert response.status_code == 201
    assert response.json()["created"] == ["global/http/" + "z" * 255]


@pytest.mark.parametrize(
    "deleted,protected,error,code",
    [(set(), {(None, "http", "global")}, "", 404), ({("example", "http", "snippet")}, set(), "", 200), (set(), set(), "DB failed", 500)],
)
def test_bulk_config_delete_preserves_skipped_keys(api_routes, deleted, protected, error, code):
    api_routes.database.delete_custom_configs.return_value = (error, deleted, protected)
    keys = [{"service": "example", "type": "http", "name": "snippet"}, {"service": "global", "type": "http", "name": "global"}]
    response = call(api_routes, "DELETE", "/configs", json={"configs": keys})
    assert response.status_code == code
    expected_skipped = ["global/http/global", "example/http/snippet"] if not deleted else ["global/http/global"]
    assert response.json()["skipped"] == expected_skipped
    api_routes.database.delete_custom_configs.assert_called_once_with({("example", "http", "snippet"), (None, "http", "global")})


def test_service_dates_and_draft_filter(api_routes):
    response = call(api_routes, "GET", "/services?with_drafts=false")
    assert response.status_code == 200
    row = response.json()["services"][0]
    assert datetime.fromisoformat(row["creation_date"]) == api_routes.instant and row["last_update"] is None
    api_routes.database.get_services.assert_called_once_with(with_drafts=False)


@pytest.mark.parametrize("full,methods", [(True, True), (True, False), (False, True), (False, False)])
def test_service_read_includes_only_reportable_settings_unless_full(api_routes, full, methods):
    conf = {
        "DEFAULT": {"value": "default", "method": "default"},
        "OWN": {"value": "own", "method": "api"},
        "TEMPLATE": {"value": "template", "method": "default", "template": "custom"},
        "SERVER_NAME": "example",
    }
    api_routes.database.get_config.side_effect = lambda **_: conf
    response = call(api_routes, "GET", "/services/example", params={"full": str(full).lower(), "methods": str(methods).lower(), "with_drafts": "false"})
    expected = conf if full else {k: v if methods or not isinstance(v, dict) else v["value"] for k, v in conf.items() if k != "DEFAULT"}
    assert response.status_code == 200 and response.json() == {"status": "success", "service": "example", "config": expected}
    api_routes.database.get_config.assert_called_once_with(methods=methods if full else True, with_drafts=False, service="example")


@pytest.mark.parametrize(
    "method,path,kwargs,code",
    [
        ("GET", "/services/missing", {}, 404),
        ("PATCH", "/services/missing", {"json": {}}, 404),
        ("DELETE", "/services/missing", {}, 404),
        ("POST", "/services/missing/convert?convert_to=draft", {}, 400),
    ],
)
def test_unknown_service_does_not_persist(api_routes, method, path, kwargs, code):
    response = call(api_routes, method, path, **kwargs)
    assert response.status_code == code and response.json()["status"] == "error"
    api_routes.database.save_config.assert_not_called()


@pytest.mark.parametrize(
    "body,message",
    [
        ({"server_name": " "}, "server_name is required"),
        ({"server_name": "example"}, "Service example already exists"),
        ({"server_name": "new", "variables": {"SERVER_NAME": " "}}, "SERVER_NAME can't be empty"),
        ({"server_name": "new", "variables": {"SERVER_NAME": "alias"}}, "A server name of new is already used by service example"),
    ],
)
def test_create_service_refusals_never_persist(api_routes, body, message):
    response = call(api_routes, "POST", "/services", json=body)
    assert response.status_code in {400, 422} and response.json() == {"status": "error", "message": message}
    api_routes.database.save_config.assert_not_called()


def test_create_service_draft_and_variables_preserve_existing_config(api_routes):
    response = call(
        api_routes,
        "POST",
        "/services",
        json={"server_name": "new.example alias", "is_draft": True, "variables": {"USE_GZIP": "no", "SERVER_NAME": "new.example other.alias"}},
    )
    assert response.status_code == 200 and response.json() == {"status": "success", "changed_plugins": ["general", "gzip"]}
    assert api_routes.database.save_config.call_args.args == (
        api_routes.snapshot
        | {
            "SERVER_NAME": "example new.example other",
            "new.example_IS_DRAFT": "yes",
            "new.example_USE_GZIP": "no",
            "new.example_SERVER_NAME": "new.example other.alias",
        },
        "api",
    )
    assert api_routes.database.save_config.call_args.kwargs == {"changed": True}


@pytest.mark.parametrize("error,code", [("read-only", 400), ("already exists", 400), ("doesn't exist", 400), ("DB failed", 500)])
def test_service_persistence_errors_remain_errors(api_routes, error, code):
    api_routes.database.save_config.return_value = error
    response = call(api_routes, "POST", "/services", json={"server_name": "new"})
    assert response.status_code == code and response.json() == {"status": "error", "message": error}


@pytest.mark.parametrize("own", [{"value": "example alias", "method": "api", "global": False}, {"value": "example", "method": "default", "global": True}])
def test_service_rename_rewrites_prefixes_and_passes_transaction_pair(api_routes, own):
    api_routes.database.get_non_default_settings.side_effect = lambda **kw: {"SERVER_NAME": own} if kw.get("methods") else dict(api_routes.snapshot)
    response = call(
        api_routes, "PATCH", "/services/example", json={"server_name": "renamed", "is_draft": False, "variables": {"USE_GZIP": "no", "SERVER_NAME": "ignored"}}
    )
    assert response.status_code == 200, response.text
    saved = api_routes.database.save_config.call_args
    assert saved.args == (
        {
            "SERVER_NAME": "renamed other",
            "renamed_SERVER_NAME": "renamed alias" if own["global"] is False else "renamed",
            "renamed_USE_GZIP": "no",
            "other_USE_GZIP": "no",
            "renamed_IS_DRAFT": "no",
        },
        "api",
    )
    assert saved.kwargs == {"changed": True, "rename": ("example", "renamed")}


@pytest.mark.parametrize("mode,code", [("empty", 422), ("duplicate", 400), ("external", 403), ("invalid-name", 422), ("invalid-variable", 422)])
def test_service_update_validation_prevents_save(api_routes, mode, code):
    body = {"server_name": "renamed"}
    if mode in {"empty", "duplicate"}:
        body["server_name"] = " " if mode == "empty" else "other"
    if mode == "external":
        api_routes.database.get_services.side_effect = lambda **_: [{"id": "example", "method": "autoconf"}]
    if mode in {"invalid-name", "invalid-variable"}:
        api_routes.database.is_valid_setting.return_value = (False, "invalid")
    if mode == "invalid-variable":
        body = {"variables": {"BAD_SETTING": "bad"}}
    response = call(api_routes, "PATCH", "/services/example", json=body)
    assert response.status_code == code and response.json()["status"] == "error"
    api_routes.database.save_config.assert_not_called()


def test_service_delete_preserves_other_service_keys(api_routes):
    response = call(api_routes, "DELETE", "/services/example")
    assert response.status_code == 200
    api_routes.database.save_config.assert_called_once_with({"SERVER_NAME": "other", "other_USE_GZIP": "no"}, "api", changed=True)


def test_wizard_service_cannot_be_deleted(api_routes):
    api_routes.database.get_services.side_effect = lambda **_: [{"id": "example", "method": "wizard"}]
    response = call(api_routes, "DELETE", "/services/example")
    assert response.status_code == 403 and response.json() == {"status": "error", "message": "Service example is managed by wizard and cannot be deleted"}
    api_routes.database.save_config.assert_not_called()


@pytest.mark.parametrize("target,expected", [("online", "no"), ("draft", "yes")])
def test_service_convert_only_changes_requested_service_draft(api_routes, target, expected):
    response = call(api_routes, "POST", f"/services/example/convert?convert_to={target}")
    assert response.status_code == 200
    api_routes.database.save_config.assert_called_once_with(api_routes.snapshot | {"example_IS_DRAFT": expected}, "api", changed=True)
