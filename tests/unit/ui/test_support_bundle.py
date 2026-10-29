"""Web UI diagnostics bundle contracts shared with dev."""

import json
from io import BytesIO
from logging import ERROR, LogRecord
from pathlib import Path
from zipfile import ZipFile

import pytest

pytest.importorskip("flask")
support_bundle = pytest.importorskip("app.support_bundle")

Anonymizer = support_bundle.Anonymizer
RingBufferHandler = support_bundle.RingBufferHandler
build_plugins_report = support_bundle.build_plugins_report
build_support_bundle = support_bundle.build_support_bundle

UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"

SECRETS = {
    "ipv4": ("client 203.0.113.77 connected", "203.0.113.77"),
    "ipv6 full": ("from 2001:0db8:85a3:0000:0000:8a2e:0370:7334 ok", "8a2e:0370:7334"),
    "ipv6 compressed": ("peer 2001:db8::1 gone", "2001:db8::1"),
    "ipv6 loopback": ("bind ::1 failed", "::1 failed"),
    "ipv6 zone": ("link fe80::1%eth0 up", "fe80::1"),
    "ipv4 mapped": ("addr ::ffff:192.0.2.128 seen", "192.0.2.128"),
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


def test_bundle_reports_a_missing_log_file_instead_of_failing(tmp_path):
    with ZipFile(BytesIO(_bundle(tmp_path / "absent.log"))) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
    assert manifest["log_sources"][0]["status"] == "not found"


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


def test_module_exports_stay_in_step():
    assert support_bundle.RING_HANDLER is not None


def test_main_records_the_loaded_plugin_version_on_each_blueprint():
    """The `disk/loaded` check of plugins.json needs the version recorded when the blueprint is registered."""
    main = (UI_ROOT / "main.py").read_text(encoding="utf-8")
    assert "from app.support_bundle import read_plugin_version" in main
    assert "bp.plugin_version = read_plugin_version(plugin_root)" in main


@pytest.mark.parametrize("password", ("sec?ret", "se#cret"))
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


def test_quoted_percent_encoded_keys_that_are_not_secret_stay():
    for text in ('{"host%20name":"web-1"}', "{'host%20name':['web-1']}", '{"us%65r":"bob"}'):
        assert Anonymizer().redact(text) == text
