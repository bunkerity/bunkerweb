"""The Web UI diagnostics bundle (dev d363779b2, ported to the API-only 1.7 UI).

``/support/ui_bundle`` is owner-only (``current_user.admin``, the flag the other admin gates read), builds a zip from
allow-listed data and anonymizes every log line: IPv4, IPv6, credentials, URIs whose password holds ``@``. The ring log
handler that feeds it is bounded in bytes at ingestion.
"""

import importlib.util
import json
import sys
from io import BytesIO
from logging import ERROR, LogRecord
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest

# Skip, never fail collection, when the UI dependencies are not installed (src/ui on path via the ui conftest)
pytest.importorskip("flask")
support_bundle = pytest.importorskip("app.support_bundle")

from flask import Flask  # noqa: E402

Anonymizer = support_bundle.Anonymizer
RingBufferHandler = support_bundle.RingBufferHandler
build_environment = support_bundle.build_environment
build_plugins_report = support_bundle.build_plugins_report
build_support_bundle = support_bundle.build_support_bundle

UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"
ROUTE_PATH = UI_ROOT / "app" / "routes" / "support.py"
LOCALES = UI_ROOT / "app" / "static" / "locales"

SECRETS = {
    "ipv4": ("client 203.0.113.77 connected", "203.0.113.77"),
    "ipv6 full": ("from 2001:0db8:85a3:0000:0000:8a2e:0370:7334 ok", "8a2e:0370:7334"),
    "ipv6 compressed": ("peer 2001:db8::1 gone", "2001:db8::1"),
    "ipv6 loopback": ("bind ::1 failed", "::1 failed"),
    "ipv6 zone": ("link fe80::1%eth0 up", "fe80::1"),
    "ipv4 mapped": ("addr ::ffff:192.0.2.128 seen", "192.0.2.128"),
    "mysql uri with @ in the password": ("db mysql+pymysql://bunkerweb:p@ss:w@rd@db.example.com:3306/db?charset=utf8mb4", "ss:w@rd"),
    "postgres uri": ("postgresql://bunkerweb:s3@cr@t@pg.internal/bw failed", "cr@t"),
    "token in the userinfo": ("clone https://ghp_AbCdEf123456@github.com/org/repo", "ghp_AbCdEf123456"),
    "bearer": ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", "eyJhbGciOiJIUzI1NiJ9"),
    "basic": ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA"),
    "env style": ("API_TOKEN=s3cr3t-value-123 loaded", "s3cr3t-value-123"),
    "json password": ('{"user": "bob", "password": "hunter2hunter2"}', "hunter2hunter2"),
    "cookie": ("Cookie: session=abcdef0123456789; csrf=zzz999", "abcdef0123456789"),
    "domain": ("proxying www.customer-site.org upstream", "customer-site.org"),
}


@pytest.mark.parametrize("name", SECRETS)
def test_anonymizer_removes_every_secret(name):
    line, secret = SECRETS[name]
    redacted = Anonymizer({"www.customer-site.org"}).redact(line)
    assert secret not in redacted, redacted


def test_anonymizer_keeps_ordinary_text():
    line = "[2026-10-15 10:00:00 +0000] [UI] [7] [ℹ️ ] - Loaded 12 plugins in 0.4s (version 1.7.0)"
    assert Anonymizer({"www.customer-site.org"}).redact(line) == line


def _ring_record(message: str) -> LogRecord:
    return LogRecord("UI", ERROR, __file__, 1, message, None, None)


def test_ring_handler_is_bounded():
    handler = RingBufferHandler(record_cap=200, total_cap=1000)
    for index in range(500):
        handler.emit(_ring_record(f"record {index} " + "x" * 80))
    snapshot = handler.snapshot()
    assert snapshot["bytes"] <= 1000
    assert snapshot["records_evicted"] > 400
    assert snapshot["records"][-1].startswith("record 499 ")


def test_ring_handler_cuts_then_redacts_oversized_records():
    """A secret that straddles the record cap must not survive as a truncated, unrecognisable stub."""
    handler = RingBufferHandler(record_cap=120, total_cap=10_000)
    handler.emit(_ring_record("a" * 90 + " mysql://bunkerweb:topsecret@db.example.com/db " + "b" * 400))
    snapshot = handler.snapshot()
    assert snapshot["records_cut"] == 1
    assert "topsecret" not in snapshot["records"][0]
    assert len(snapshot["records"][0].encode()) <= 120 + len(" [truncated]")


@pytest.fixture
def log_file(tmp_path):
    path = tmp_path / "ui.log"
    path.write_text(
        "[2026-10-15 10:00:00 +0000] [UI] [7] [ℹ️ ] - client 203.0.113.77 for www.customer-site.org\n"
        "[2026-10-15 10:00:01 +0000] [UI] [7] [❌] - boom mysql+pymysql://bunkerweb:p@ss:w@rd@db.example.com/db\n"
        "Traceback (most recent call last):\n"
        '  File "app.py", line 1, in <module>\n'
        "ValueError: peer 2001:db8::1\n",
        encoding="utf-8",
    )
    return path


def _bundle(log_file, ring=None, plugins=None, environment=None):
    return build_support_bundle(
        domains={"www.customer-site.org"},
        environ={"LOG_TYPES": "file", "LOG_FILE_PATH": str(log_file), "DATABASE_URI": "mysql://u:envsecret@h/db", "PRO_LICENSE_KEY": "lic-envsecret"},
        integration="Docker",
        ring=ring or {"pid": 7, "started": "2026-10-15T10:00:00+00:00", "records": ["ring 198.51.100.9 api_token=ringsecret"], "bytes": 40},
        plugins=plugins or {"plugins": []},
        environment=environment or {"bunkerweb_version": "1.7.0"},
    )


def test_bundle_holds_the_expected_parts(log_file):
    with ZipFile(BytesIO(_bundle(log_file))) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
    assert {"manifest.json", "errors.txt", "plugins.json", "environment.json", "logs/ui-recent.log", "logs/ui.log"} <= names
    assert {entry["name"] for entry in manifest["files"]} >= {"errors.txt", "plugins.json", "logs/ui.log"}
    assert manifest["error_blocks"]["found"] >= 1


def test_bundle_carries_no_secret_ip_or_domain(log_file):
    with ZipFile(BytesIO(_bundle(log_file))) as bundle:
        everything = "\n".join(bundle.read(name).decode("utf-8") for name in bundle.namelist())
    for leaked in ("203.0.113.77", "198.51.100.9", "2001:db8::1", "ss:w@rd", "customer-site.org", "ringsecret", "envsecret", "lic-envsecret"):
        assert leaked not in everything, leaked
    assert "[ANONYMIZED_IPv4]" in everything and "[ANONYMIZED_IPv6]" in everything and "[ANONYMIZED_DOMAIN]" in everything


def test_bundle_reports_a_missing_log_file_instead_of_failing(tmp_path):
    with ZipFile(BytesIO(_bundle(tmp_path / "absent.log"))) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
    assert manifest["log_sources"][0]["status"] == "not found"


def test_environment_is_allow_listed_and_hashes_hostnames():
    environment = build_environment(
        metadata={
            "version": "1.7.0",
            "is_pro": True,
            "pro_status": "valid",
            "pro_expire": "2027-01-01T00:00:00+00:00",
            "pro_services": 5,
            "database_version": "16.1",
        },
        integration="Docker",
        instances=[{"name": "bw1", "hostname": "bunkerweb.internal", "type": "static", "method": "ui", "status": "up", "credential_set": True}],
        service_count=3,
        worker={"pid": 7, "started": "x"},
    )
    text = json.dumps(environment)
    assert "bunkerweb.internal" not in text and "PRO_LICENSE_KEY" not in text
    assert environment["instances"][0]["hostname"].startswith("host-")
    assert environment["pro"]["services_configured"] == 3
    assert environment["database"]["server_version"] == "16.1"


def test_plugins_report_flags_a_version_mismatch(tmp_path):
    root = tmp_path / "myplugin"
    (root / "ui" / "blueprints").mkdir(parents=True)
    (root / "plugin.json").write_text(json.dumps({"version": "1.1"}), encoding="utf-8")
    report = build_plugins_report(
        [{"id": "myplugin", "type": "external", "version": "1.0", "page": True}],
        {"external": tmp_path},
        [{"name": "myplugin", "plugin_priority": 1, "root_path": str(root), "import_path": str(root / "ui" / "blueprints"), "plugin_version": "1.0"}],
        {"pid": 7},
    )
    plugin = report["plugins"][0]
    assert plugin["status"] == "mismatch"
    assert {item["pair"] for item in plugin["mismatches"]} == {"database/disk", "disk/loaded"}


def test_plugins_report_is_unknown_without_a_recorded_load_version(tmp_path):
    root = tmp_path / "myplugin"
    (root / "ui" / "blueprints").mkdir(parents=True)
    (root / "plugin.json").write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    report = build_plugins_report(
        [{"id": "myplugin", "type": "external", "version": "1.0"}],
        {"external": tmp_path},
        [{"name": "myplugin", "import_path": str(root / "ui" / "blueprints")}],
        {"pid": 7},
    )
    assert report["plugins"][0]["status"] == "unknown"


# --------------------------------------------------------------------------------------
# The route
# --------------------------------------------------------------------------------------


@pytest.fixture
def client():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.API_CLIENT.get_metadata.return_value = {"version": "1.7.0", "is_pro": False}
    dependencies.API_CLIENT.get_instances.return_value = [{"name": "bw1", "hostname": "bunkerweb.internal", "type": "static", "method": "ui", "status": "up"}]
    dependencies.API_CLIENT.get_services.return_value = [{"id": "www.customer-site.org"}]
    dependencies.API_CLIENT.get_plugins.return_value = [{"id": "limit", "type": "core", "version": "1.0", "page": True}]
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_CONFIG.get_config.return_value = {"SERVER_NAME": "www.customer-site.org"}
    dependencies.BW_CONFIG.get_plugins_settings.return_value = {}
    for name in ("CORE_PLUGINS_PATH", "EXTERNAL_PLUGINS_PATH", "PRO_PLUGINS_PATH"):
        setattr(dependencies, name, Path("/nonexistent") / name)

    module_name = "app.routes._support_bundle_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    # Stays patched for the whole test: the route imports the plugin paths from dependencies when it runs
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        module.render_error_page = lambda code, message=None: (message or "", code)

        app = Flask(__name__)
        app.secret_key = "test"  # nosec B105 - unit test
        app.add_url_rule("/support/ui_bundle", view_func=module.support_ui_bundle.__wrapped__)
        app.module = module
        yield app.test_client()


def _as(client, *, admin, permissions=("read", "write")):
    return patch.object(client.application.module, "current_user", SimpleNamespace(admin=admin, list_permissions=set(permissions)), create=True)


def test_non_admin_is_refused_even_with_the_write_permission(client):
    with _as(client, admin=False):
        response = client.get("/support/ui_bundle")
    assert response.status_code == 403
    assert not response.get_data().startswith(b"PK")


def test_admin_downloads_the_bundle(client, log_file, monkeypatch):
    monkeypatch.setenv("LOG_TYPES", "file")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file))
    with _as(client, admin=True):
        response = client.get("/support/ui_bundle")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert "bunkerweb-ui-support-" in response.headers["Content-Disposition"]
    with ZipFile(BytesIO(response.get_data())) as bundle:
        names = set(bundle.namelist())
        everything = "\n".join(bundle.read(name).decode("utf-8") for name in names)
    assert {"manifest.json", "plugins.json", "environment.json", "errors.txt"} <= names
    assert "bunkerweb.internal" not in everything and "203.0.113.77" not in everything


def test_every_data_read_goes_through_the_api_client(client, monkeypatch):
    monkeypatch.setenv("LOG_TYPES", "stderr")
    with _as(client, admin=True):
        assert client.get("/support/ui_bundle").status_code == 200
    api_client = client.application.module.API_CLIENT
    api_client.get_metadata.assert_called_once()
    api_client.get_instances.assert_called_once()
    api_client.get_plugins.assert_called_once()


def test_logs_download_uses_the_stronger_anonymizer(client, tmp_path):
    """`/support/logs` shares the anonymizer: IPv6 in any form and credentials are gone, not only the full 8-group form."""
    module = client.application.module
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "ui.log").write_text("peer 2001:db8::1 token=abcdef123456 www.customer-site.org\n", encoding="utf-8")
    app = Flask(__name__)
    app.add_url_rule("/support/logs", view_func=module.support_logs.__wrapped__)
    real_path = module.Path
    with patch.object(module, "Path", lambda *parts: logs if parts[:1] == ("/",) else real_path(*parts)), _as(client, admin=False):
        response = app.test_client().get("/support/logs")
    with ZipFile(BytesIO(response.get_data())) as bundle:
        body = bundle.read("ui.log").decode()
    assert "2001:db8::1" not in body and "abcdef123456" not in body and "customer-site.org" not in body


# --------------------------------------------------------------------------------------
# i18n and template
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(LOCALES.glob("*.json")), ids=lambda path: path.stem)
def test_the_card_keys_exist_in_every_locale(path):
    card = json.loads(path.read_text(encoding="utf-8"))["support"]["card"]["ui_bundle"]
    assert set(card) == {"admin_only", "button", "help", "title"}
    assert all(isinstance(value, str) and value for value in card.values())


def test_the_template_shows_the_card_to_the_owner_only():
    template = (UI_ROOT / "app" / "templates" / "support.html").read_text(encoding="utf-8")
    block = template[template.index("ui_bundle") - 400 :]
    assert "{% if user_admin %}" in block.split("ui_bundle")[0][-400:]
    assert "support.card.ui_bundle.title" in template


def test_module_exports_stay_in_step():
    assert support_bundle.RING_HANDLER is not None


def test_main_records_the_loaded_plugin_version_on_each_blueprint():
    """The `disk/loaded` check of plugins.json needs the version recorded when the blueprint is registered."""
    main = (UI_ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.support_bundle import read_plugin_version" in main
    assert "bp.plugin_version = read_plugin_version(plugin_root)" in main


# `_redact_structured` / `_structure_end`: a list, mapping or tuple after a secret key goes as one value, whatever the order of the suite.
STRUCTURED = {
    "list": ("password: [a, b] tail", "password: [REDACTED] tail"),
    "mapping": ("token={'a': 1} tail", "token=[REDACTED] tail"),
    "tuple": ("user=bob token=(1,2) name=z", "user=bob token=[REDACTED] name=z"),
    "nested brackets": ("x password: [1, [2, 3], {'k': (4)}] after", "x password: [REDACTED] after"),
    "closer inside a quoted string": ('"secret": {"a": "]"} ok', '"secret": "[REDACTED]" ok'),
    "escaped quote hides a closer": (r'token=["a\"]b"] ok', "token=[REDACTED] ok"),
    "percent-encoded secret key": ("pass%77ord=[1, 2] ok", "pass%77ord=[REDACTED] ok"),
    "never closed": ("api_key=[1, 2 and nothing closes", "api_key=[REDACTED]"),
    "non-secret key beside a secret one": ("password: [1, 2] user: bob host: x", "password: [REDACTED] user: bob host: x"),
}


@pytest.mark.parametrize("name", STRUCTURED)
def test_redact_structured_replaces_the_value_after_a_secret_key(name):
    text, expected = STRUCTURED[name]
    assert support_bundle._redact_structured(text) == expected


def test_redact_structured_keeps_a_structure_after_a_non_secret_key():
    text = "hosts: [a, b] user={'name': 'bob'} port=(80, 443) host%20name=[1, 2]"
    assert support_bundle._redact_structured(text) == text


def test_structure_end_returns_the_index_after_the_closing_bracket():
    assert support_bundle._structure_end("x=[1, [2]] rest", 2) == 10
    assert support_bundle._structure_end('x=["]"] rest', 2) == 7
    assert support_bundle._structure_end("x=[1, 2", 2) == 7


# W25-FIXRED: three leaks the final review reproduced. SQLAlchemy is the oracle for what a database URI password is.
@pytest.mark.parametrize("password", ("secret/word", "sec?ret", "se#cret", "a/b?c#d", "/lead", "trail/"))
@pytest.mark.parametrize("scheme", ("postgresql", "mysql+pymysql"))
def test_uri_password_with_a_delimiter_is_redacted(scheme, password):
    from sqlalchemy.engine.url import make_url

    uri = f"{scheme}://bunkerweb:{password}@pg.internal:5432/bw?sslmode=require"
    parsed = make_url(uri)
    assert parsed.password and parsed.host == "pg.internal", "the oracle must read the whole password"
    redacted = Anonymizer().redact(f"connecting to {uri} now")
    assert parsed.password not in redacted, redacted
    assert "pg.internal:5432/bw?sslmode=require now" in redacted, redacted


def test_uri_with_an_at_sign_in_the_query_keeps_its_host():
    line = "GET https://shop.example.com/cart?email=a@b.example.org&x=1 200"
    assert Anonymizer().redact(line) == line


QUOTED_ENCODED_KEYS = {
    "json scalar": '{"pass%77ord":"sentinel-secret"}',
    "single quoted scalar": "{'pass%77ord':'sentinel-secret'}",
    "json list": '{"pass%77ord":["sentinel-secret"]}',
    "single quoted list": "{'pass%77ord':['sentinel-secret']}",
    "json mapping": '{"pass%77ord":{"a":"sentinel-secret"}}',
    "spaced separator": '{"pass%77ord" : "sentinel-secret"}',
    "equals sign": "'pass%77ord'='sentinel-secret'",
    "bare value": '{"pass%77ord":sentinel-secret}',
    "escaped quote in the value": r'{"pass%77ord":"sentinel\"-secret"}',
    "encoded key keyword": '{"my%5Fto%6Ben":"sentinel-secret"}',
}


@pytest.mark.parametrize("name", QUOTED_ENCODED_KEYS)
def test_quoted_percent_encoded_secret_keys_are_redacted(name):
    text = QUOTED_ENCODED_KEYS[name]
    redacted = Anonymizer().redact(f"payload {text} end")
    assert "sentinel" not in redacted and "-secret" not in redacted, redacted
    assert "[REDACTED]" in redacted and redacted.endswith(" end"), redacted


def test_quoted_percent_encoded_keys_that_are_not_secret_stay():
    for text in ('{"host%20name":"web-1"}', "{'host%20name':['web-1']}", '{"us%65r":"bob"}'):
        assert Anonymizer().redact(text) == text


MULTILINE_SECRETS = {
    "literal": "password: |\n  sentinel-secret\n  more-sentinel\n",
    "folded": "password: >\n  sentinel-secret\n  more-sentinel\n",
    "literal strip": "password: |-\n  sentinel-secret\n  more-sentinel\n",
    "folded keep": "password: >+\n  sentinel-secret\n  more-sentinel\n",
    "indent indicator": "password: |2\n  sentinel-secret\n  more-sentinel\n",
    "indicator order": "password: |+2\n  sentinel-secret\n  more-sentinel\n",
    "trailing comment": "password: | # keep out\n  sentinel-secret\n  more-sentinel\n",
    "nested": "db:\n  api_key: |\n    sentinel-secret\n    more-sentinel\n  other: x\n",
    "crlf": "password: |\r\n  sentinel-secret\r\n  more-sentinel\r\n",
    "blank line inside": "password: |\n  sentinel-secret\n\n  more-sentinel\n",
}


@pytest.mark.parametrize("name", MULTILINE_SECRETS)
def test_logs_download_redacts_a_block_scalar_secret(client, tmp_path, name):
    """`/support/logs` used to redact line by line, so the indented lines under `password: |` went out as they were."""
    module = client.application.module
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "ui.log").write_bytes(f"[2026-10-15 10:00:00 +0000] [UI] loading\n{MULTILINE_SECRETS[name]}after: kept\n".encode())
    (logs / "other.log").write_bytes(f"first line\n{MULTILINE_SECRETS[name]}after: kept\n".encode())
    app = Flask(__name__)
    app.add_url_rule("/support/logs", view_func=module.support_logs.__wrapped__)
    real_path = module.Path
    with patch.object(module, "Path", lambda *parts: logs if parts[:1] == ("/",) else real_path(*parts)), _as(client, admin=False):
        response = app.test_client().get("/support/logs")
    assert response.status_code == 200
    with ZipFile(BytesIO(response.get_data())) as bundle:
        members = {member: bundle.read(member).decode() for member in bundle.namelist()}
    assert set(members) == {"ui.log", "other.log"}
    for member, body in members.items():
        assert "sentinel" not in body and "-secret" not in body, (member, body)
        assert "after: kept" in body and "[REDACTED]" in body, (member, body)
