"""The /plugins blueprint: administrator gating, upload and refresh, and running a plugin's actions and page."""

import json
import sys
import tarfile
import zipfile
from io import BytesIO

import pytest

PLUGIN_JSON = {"id": "myplugin", "name": "My Plugin", "description": "d", "version": "1.0", "stream": "no", "settings": {}}
ACTIONS = """
def pre_render(**kwargs):
    return {"greeting": "hello"}


def myplugin(app, db, bw_instances_utils, args, data):
    return {"echo": data, "args": args}


def boom(**kwargs):
    raise RuntimeError("secret detail")
"""


@pytest.fixture
def plug(h, tmp_path, monkeypatch):
    module = h.routes.plugins
    paths = {
        "TMP_DIR": tmp_path / "tmp",
        "EXTERNAL_PLUGINS_PATH": tmp_path / "ext",
        "PRO_PLUGINS_PATH": tmp_path / "pro",
        "CORE_PLUGINS_PATH": tmp_path / "core",
    }
    for name, path in paths.items():
        path.mkdir()
        monkeypatch.setattr(module, name, path)
    (paths["TMP_DIR"] / "ui").mkdir()
    # every plugin's actions file is loaded under the module name "actions": start each test without a leftover
    monkeypatch.delitem(sys.modules, "actions", raising=False)
    h.paths = paths
    h.db.delete_plugin.return_value = ""
    h.config.get_plugins.return_value = {"myplugin": {"name": "My Plugin", "type": "external"}}
    h.db.get_config.return_value = {"USE_METRICS": "yes", "USE_MYPLUGIN": "yes", "SERVER_NAME": "a.example.com"}
    return module


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


def _install(h, root_name="ext", actions=ACTIONS, template="<p>{{ pre_render.data.greeting }}</p>", name="myplugin"):
    ui = h.paths[{"ext": "EXTERNAL_PLUGINS_PATH", "pro": "PRO_PLUGINS_PATH", "core": "CORE_PLUGINS_PATH"}[root_name]] / name / "ui"
    ui.mkdir(parents=True)
    if actions is not None:
        (ui / "actions.py").write_text(actions)
    if template is not None:
        (ui / "template.html").write_text(template)
    return ui


def _zip(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _tar_gz(files):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))
    return buffer.getvalue()


# --------------------------------------------------------------------------------------
# page, delete and the administrator gate
# --------------------------------------------------------------------------------------
def test_the_plugins_page_empties_the_upload_staging_folder(h, plug):
    stale = h.paths["TMP_DIR"] / "ui" / "old.zip"
    stale.write_text("x")

    h.client().get("/plugins")

    assert not stale.exists() and (h.paths["TMP_DIR"] / "ui").is_dir()
    assert h.renders[-1][0] == "plugins.html"


@pytest.mark.parametrize(
    "method, path, extra",
    [
        ("post", "/plugins/delete", {"plugins": "a"}),
        ("post", "/plugins/refresh", {"csrf_token": "t"}),
        ("post", "/plugins/upload", None),
        ("post", "/plugins/myplugin", {}),
    ],
)
def test_a_non_administrator_cannot_manage_plugins(h, plug, method, path, extra):
    client = h.client("viewer", admin=False)
    kwargs = {"data": extra} if extra is not None else {"data": {"file": (BytesIO(b"x"), "a.zip")}, "content_type": "multipart/form-data"}

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code in (302, 403)
    h.db.delete_plugin.assert_not_called()
    h.db.update_external_plugins.assert_not_called()
    assert list((h.paths["TMP_DIR"] / "ui").iterdir()) == []
    if response.status_code == 302:
        assert "Plugin management is restricted to administrators" in _flashed(h, client)
    else:
        assert "restricted to administrators" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/plugins/delete", "/plugins/refresh", "/plugins/upload"])
def test_plugin_writes_are_refused_in_read_only_mode(h, plug, path):
    h.db.readonly = True

    response = h.client().post(path, data={"plugins": "a", "csrf_token": "t"})

    assert response.status_code in (302, 403)
    h.db.delete_plugin.assert_not_called()


def test_delete_removes_each_plugin_and_flags_the_change_on_the_last_one(h, plug):
    h.db.delete_plugin.side_effect = ["", "Plugin with id x does not exist", "locked"]

    response = h.client().post("/plugins/delete", data={"plugins": "one,two,three"})

    assert [(call.args, call.kwargs) for call in h.db.delete_plugin.call_args_list] == [
        (("one", "ui"), {"changes": False}),
        (("two", "ui"), {"changes": False}),
        (("three", "ui"), {"changes": True}),
    ]
    queued = [(item["content"], item["type"]) for item in h.data["TO_FLASH"]]
    assert queued == [
        ("Deleted plugin one successfully", "success"),
        ("Plugin with id x does not exist", "error"),
        ("Couldn't delete plugin three in database: locked", "error"),
    ]
    assert "Deleting+plugins:+one,+two,+three" in response.headers["Location"] and h.data["RELOADING"] is False


# --------------------------------------------------------------------------------------
# upload
# --------------------------------------------------------------------------------------
def _upload(h, name, content):
    return h.client().post("/plugins/upload", data={"file": (BytesIO(content), name)}, content_type="multipart/form-data")


def test_upload_without_a_file_is_a_400(h, plug):
    assert h.client().post("/plugins/upload", data={}).status_code == 400


@pytest.mark.parametrize("name", ["plugin.txt", "plugin.rar", "plugin.tar"])
def test_upload_rejects_unknown_extensions(h, plug, name):
    assert _upload(h, name, b"x").status_code == 422
    assert list((h.paths["TMP_DIR"] / "ui").iterdir()) == []


def test_upload_stores_a_single_plugin_archive_for_the_refresh(h, plug):
    archive = _zip({"plugin.json": json.dumps(PLUGIN_JSON)})

    response = _upload(h, "myplugin.zip", archive)

    assert response.status_code == 201
    assert (h.paths["TMP_DIR"] / "ui" / "myplugin.zip").read_bytes() == archive


def test_upload_splits_a_bundle_of_several_plugins(h, plug):
    bundle = _zip({"bundle/one/plugin.json": "{}", "bundle/one/a.txt": "1", "bundle/two/plugin.json": "{}"})

    response = _upload(h, "bundle.zip", bundle)

    assert response.status_code == 201
    staged = sorted(path.name for path in (h.paths["TMP_DIR"] / "ui").iterdir())
    assert "one.tar.gz" in staged and "two.tar.gz" in staged and "bundle" not in staged


def test_upload_splits_a_tar_bundle_too(h, plug):
    bundle = _tar_gz({"bundle/one/plugin.json": "{}", "bundle/two/plugin.json": "{}"})

    assert _upload(h, "bundle.tar.gz", bundle).status_code == 201
    assert {"one.tar.gz", "two.tar.gz"} <= {path.name for path in (h.paths["TMP_DIR"] / "ui").iterdir()}


def test_upload_rejects_a_bundle_with_path_traversal(h, plug):
    bundle = _zip({"x/one/plugin.json": "{}", "x/two/plugin.json": "{}", "../evil.txt": "pwn"})

    assert _upload(h, "bundle.zip", bundle).status_code == 422
    assert not (h.paths["TMP_DIR"].parent / "evil.txt").exists()


# --------------------------------------------------------------------------------------
# refresh
# --------------------------------------------------------------------------------------
def _stage(h, name, content):
    (h.paths["TMP_DIR"] / "ui" / name).write_bytes(content)


def _refresh(h):
    client = h.client()
    return client, client.post("/plugins/refresh", data={"csrf_token": "t"})


def test_refresh_without_an_uploaded_file_asks_for_one(h, plug):
    client, _ = _refresh(h)

    assert "Please upload new plugins to reload plugins" in _flashed(h, client)
    h.db.update_external_plugins.assert_not_called()


def test_refresh_stores_a_valid_zip_plugin(h, plug):
    _stage(h, "myplugin.zip", _zip({"plugin.json": json.dumps(PLUGIN_JSON), "ui/template.html": "<p/>"}))
    h.config.get_plugins.return_value = {}
    h.db.update_external_plugins.return_value = ""

    _, response = _refresh(h)

    plugins = h.db.update_external_plugins.call_args.args[0]
    assert len(plugins) == 1 and plugins[0]["id"] == "myplugin" and plugins[0]["type"] == "ui" and plugins[0]["page"] is True
    assert len(plugins[0]["checksum"]) == 64 and plugins[0]["data"][:2] == b"\x1f\x8b"
    assert h.db.update_external_plugins.call_args.kwargs == {"_type": "ui", "delete_missing": False}
    assert {"content": "Plugins uploaded successfully", "type": "success"} in h.data["TO_FLASH"]
    assert "message=Reloading+plugins" in response.headers["Location"]


def test_refresh_accepts_a_tar_archive_whose_files_sit_in_a_folder(h, plug):
    _stage(h, "myplugin.tar.gz", _tar_gz({"myplugin/plugin.json": json.dumps(PLUGIN_JSON)}))
    h.config.get_plugins.return_value = {}
    h.db.update_external_plugins.return_value = ""

    _refresh(h)

    assert h.db.update_external_plugins.call_args.args[0][0]["page"] is False


def test_refresh_does_not_overwrite_an_existing_ui_plugin(h, plug):
    _stage(h, "myplugin.zip", _zip({"plugin.json": json.dumps(PLUGIN_JSON)}))
    h.config.get_plugins.return_value = {"myplugin": {}}

    _refresh(h)

    h.db.update_external_plugins.assert_not_called()
    assert {"content": "Plugin myplugin already exists", "type": "error"} in h.data["TO_FLASH"]
    assert h.data["RELOADING"] is False


def test_refresh_reports_a_database_error(h, plug):
    _stage(h, "myplugin.zip", _zip({"plugin.json": json.dumps(PLUGIN_JSON)}))
    h.config.get_plugins.return_value = {}
    h.db.update_external_plugins.return_value = "locked"

    _refresh(h)

    assert {"content": "Couldn't update ui plugins to database: locked", "type": "error"} in h.data["TO_FLASH"]


@pytest.mark.parametrize(
    "name, content, fragment",
    [
        ("bad.zip", b"not a zip", "is not a valid zip file"),
        ("bad.tar.gz", b"not a tar", "Couldn't read file bad.tar.gz"),
        ("nojson.zip", _zip({"readme.txt": "x"}), "plugin.json file is missing"),
        ("badjson.zip", _zip({"plugin.json": "{nope"}), "The file plugin.json in badjson.zip is not valid"),
        ("keys.zip", _zip({"plugin.json": json.dumps({"id": "abcd"})}), "missing one or more of the following keys"),
        ("name.zip", _zip({"plugin.json": json.dumps(PLUGIN_JSON | {"id": "x"})}), "Invalid plugin name"),
        ("two.zip", _zip({"a/plugin.json": "{}", "b/plugin.json": "{}"}), "plugin.json file is missing"),
    ],
)
def test_refresh_reports_each_kind_of_bad_archive_and_stores_nothing(h, plug, name, content, fragment):
    _stage(h, name, content)

    _refresh(h)

    h.db.update_external_plugins.assert_not_called()
    assert any(fragment in item["content"] for item in h.data["TO_FLASH"] if item["type"] == "error"), h.data["TO_FLASH"]


def test_refresh_needs_the_csrf_form_field(h, plug):
    _stage(h, "myplugin.zip", _zip({"plugin.json": json.dumps(PLUGIN_JSON)}))

    h.client().post("/plugins/refresh", data={"other": "1"})

    h.db.update_external_plugins.assert_not_called()


# --------------------------------------------------------------------------------------
# plugin path precedence
# --------------------------------------------------------------------------------------
def test_get_plugin_path_prefers_pro_then_external_then_core(h, plug):
    for root in ("core", "ext", "pro"):
        _install(h, root)
        expected = h.paths[{"ext": "EXTERNAL_PLUGINS_PATH", "pro": "PRO_PLUGINS_PATH", "core": "CORE_PLUGINS_PATH"}[root]] / "myplugin"
        assert plug.get_plugin_path("myplugin") in (h.paths["PRO_PLUGINS_PATH"] / "myplugin", h.paths["EXTERNAL_PLUGINS_PATH"] / "myplugin", expected)

    assert plug.get_plugin_path("myplugin") == h.paths["PRO_PLUGINS_PATH"] / "myplugin"
    assert plug.get_plugin_path("ghost") is None


def test_get_plugin_path_falls_back_in_order(h, plug):
    _install(h, "core")
    assert plug.get_plugin_path("myplugin") == h.paths["CORE_PLUGINS_PATH"] / "myplugin"
    _install(h, "ext")
    assert plug.get_plugin_path("myplugin") == h.paths["EXTERNAL_PLUGINS_PATH"] / "myplugin"


# --------------------------------------------------------------------------------------
# actions (POST /plugins/<plugin>)
# --------------------------------------------------------------------------------------
def test_an_action_receives_the_request_data_and_its_result_is_returned(h, plug):
    _install(h)

    response = h.client().post("/plugins/myplugin?x=1", json={"k": "v"})

    assert response.status_code == 200
    assert response.get_json() == {"message": "ok", "data": {"echo": {"k": "v"}, "args": {"x": "1"}}}


def test_a_form_post_is_redirected_back_to_the_page(h, plug):
    _install(h)

    response = h.client().post("/plugins/myplugin", data={"a": "b"})

    assert response.status_code == 303 and response.headers["Location"].endswith("/plugins/myplugin")


def test_a_failing_action_does_not_leak_its_exception(h, plug):
    _install(h)
    ui = h.paths["EXTERNAL_PLUGINS_PATH"] / "myplugin" / "ui"
    (ui / "actions.py").write_text(ACTIONS.replace("def myplugin(", "def other(") + "\ndef myplugin(**kw):\n    raise RuntimeError('secret detail')\n")

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 500
    assert "secret detail" not in response.get_data(as_text=True)
    assert response.get_json()["message"].startswith("An error occurred while executing the plugin")


def test_an_action_returning_nothing_is_an_error(h, plug):
    _install(h, actions="def myplugin(**kw):\n    return None\n")

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 500 and "did not return a valid response" in response.get_json()["message"]


def test_a_plugin_without_the_named_method_is_reported(h, plug):
    _install(h, actions="def pre_render(**kw):\n    return {}\n")

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 500 and "does not have a method" in response.get_json()["message"]


def test_a_syntax_error_in_the_actions_file_is_reported_without_details(h, plug):
    _install(h, actions="def broken(:\n")

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 500 and "importing the plugin" in response.get_json()["message"]
    assert "SyntaxError" not in response.get_data(as_text=True)


def test_a_plugin_without_actions_or_page_is_a_404(h, plug):
    h.db.get_plugin_page.return_value = None

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 404 and "does not have a page" in response.get_json()["message"]


def test_actions_are_loaded_from_the_database_blob_when_not_on_disk(h, plug):
    h.db.get_plugin_page.return_value = _tar_gz({"ui/actions.py": ACTIONS})

    response = h.client().post("/plugins/myplugin", json={"k": 1})

    assert response.get_json()["data"]["echo"] == {"k": 1}
    assert [path for path in (h.paths["TMP_DIR"] / "ui" / "action").rglob("*") if path.is_file()] == [], "the extracted files must be cleaned up"


def test_a_blob_with_a_traversal_member_is_refused(h, plug):
    h.db.get_plugin_page.return_value = _tar_gz({"../evil.py": "x"})

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 400 and response.get_json()["message"] == "Invalid file path"


def test_a_corrupt_blob_is_a_generic_500(h, plug):
    h.db.get_plugin_page.return_value = b"not a tarball"

    response = h.client().post("/plugins/myplugin", json={})

    assert response.status_code == 500 and "extracting the plugin" in response.get_json()["message"]


def test_a_plugin_id_that_is_not_valid_is_refused_before_anything_runs(h, plug):
    client = h.client()

    response = client.get("/plugins/a%20b")

    assert response.status_code == 302
    assert any("Invalid plugin id" in message for message in _flashed(h, client))


# --------------------------------------------------------------------------------------
# plugin page (GET /plugins/<plugin>)
# --------------------------------------------------------------------------------------
def test_an_unknown_plugin_is_a_404(h, plug):
    h.config.get_plugins.return_value = {}

    assert h.client().get("/plugins/myplugin").status_code == 404


def test_a_used_plugin_page_is_rendered_from_its_template_and_pre_render(h, plug):
    _install(h)

    h.client().get("/plugins/myplugin")

    template, context = h.renders[-1]
    assert template == "plugin_page.html"
    assert context["plugin_page"] == "<p>hello</p>" and context["is_used"] and context["is_metrics"]
    assert context["pre_render"]["data"] == {"greeting": "hello"}


def test_the_page_escapes_what_the_pre_render_returns(h, plug):
    _install(h, actions='def pre_render(**kw):\n    return {"greeting": "<script>x</script>"}\n')

    h.client().get("/plugins/myplugin")

    assert "<script>" not in h.renders[-1][1]["plugin_page"]


def test_a_plugin_that_is_switched_off_has_no_embedded_page(h, plug):
    _install(h)
    h.db.get_config.return_value = {"USE_METRICS": "yes", "USE_MYPLUGIN": "no", "SERVER_NAME": "a.example.com"}

    h.client().get("/plugins/myplugin")

    context = h.renders[-1][1]
    assert context["plugin_page"] == "" and context["is_used"] is False


def test_a_service_level_setting_counts_as_use(h, plug):
    _install(h)
    h.db.get_config.return_value = {"USE_METRICS": "yes", "USE_MYPLUGIN": "no", "SERVER_NAME": "a.example.com", "a.example.com_USE_MYPLUGIN": "yes"}

    h.client().get("/plugins/myplugin")

    assert h.renders[-1][1]["plugin_page"] == "<p>hello</p>"


def test_a_failing_template_renders_a_generic_alert(h, plug):
    _install(h, template="{{ pre_render.nope.deeper.still }}")

    h.client().get("/plugins/myplugin")

    assert "An error occurred while rendering the plugin page" in h.renders[-1][1]["plugin_page"]


def test_the_old_template_format_gets_an_upgrade_notice(h, plug):
    _install(h, template='{% extends "base.html" %}{% block content %}x{% endblock %}')

    h.client().get("/plugins/myplugin")

    assert "uses old template" in h.renders[-1][1]["plugin_page"]


def test_a_blueprint_only_plugin_without_a_page_says_so(h, plug):
    _install(h, actions=None, template=None)

    h.client().get("/plugins/myplugin")

    context = h.renders[-1][1]
    assert context["no_page"] is True and context["blueprint_loaded"] is False


def test_a_plugin_page_missing_from_disk_and_database_is_a_404(h, plug):
    h.db.get_plugin_page.return_value = None

    response = h.client().get("/plugins/myplugin")

    assert response.status_code == 404 and response.get_json()["message"] == "The plugin does not have a page"


def test_the_page_is_extracted_from_the_database_blob_when_not_on_disk(h, plug):
    h.db.get_plugin_page.return_value = _tar_gz({"ui/template.html": "<b>blob</b>"})

    h.client().get("/plugins/myplugin")

    assert h.renders[-1][1]["plugin_page"] == "<b>blob</b>"
    assert [path for path in (h.paths["TMP_DIR"] / "ui" / "page").rglob("*") if path.is_file()] == []


def test_a_plugin_without_pre_render_does_not_run_another_plugins_pre_render(h, plug):
    _install(h)
    _install(h, name="otherplug", actions="def unrelated(**kw):\n    return {}\n", template="<p>{{ pre_render.message }}</p>")
    h.config.get_plugins.return_value = {"myplugin": {"name": "My Plugin", "type": "external"}, "otherplug": {"name": "Other Plug", "type": "external"}}
    h.db.get_config.return_value = {"USE_METRICS": "yes", "USE_MYPLUGIN": "yes", "USE_OTHERPLUG": "yes", "SERVER_NAME": "a.example.com"}
    client = h.client()

    client.get("/plugins/myplugin")
    client.get("/plugins/otherplug")

    assert h.renders[-1][1]["pre_render"] == {"status": "ok", "code": 200, "message": "The plugin does not have a pre_render method"}
