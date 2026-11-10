"""Admin write controls and DB.readonly immutability over the route inventory."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from importlib import import_module
from inspect import unwrap
from io import BytesIO
from json import dumps
from pathlib import Path
import subprocess
from tarfile import TarInfo, open as tar_open
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from reader_route_manifest import ROUTE_CLASSES
from test_reader_route_matrix import MUTATOR_PREFIXES, matrix_app as _matrix_app, mutation_attempts, route_url, signed_client, triples

matrix_app = _matrix_app

CONFIG_SELECTION = dumps([{"service": "global", "type": "http", "name": "fixture"}])
CONFIG_FORM = {"service": "global", "type": "HTTP", "name": "fixture", "value": "# updated"}
CONFIG_EXPORT = dumps({"version": 1, "configs": [{"service_id": None, "type": "http", "name": "imported", "data": "# imported"}]}).encode()
TEMPLATE_FORM = {"template": dumps({"id": "fixture", "name": "Updated", "settings": {}, "steps": [], "configs": []})}

VALID_WRITE_PAYLOADS = {
    ("services.services_convert", "/services/convert", "POST"): {"data": {"services": "fixture.test", "convert_to": "draft"}},
    ("services.services_delete", "/services/delete", "POST"): {"data": {"services": "fixture.test"}},
    ("services.services_validate_certificate", "/services/validate-certificate", "POST"): {"data": {"cert": "fixture", "key": "fixture"}},
    ("services.services_service_page", "/services/<string:service>", "POST"): {
        "values": {"service": "new"},
        "data": {"csrf_token": "fixture", "SERVER_NAME": "new.test"},
    },
    ("services.services_service_import", "/services/import", "POST"): {"data": {"services_file": (b"new.test_SERVER_NAME=new.test\n", "services.env")}},
    ("jobs.jobs_run", "/jobs/run", "POST"): {"data": {"jobs": dumps([{"plugin": "letsencrypt", "name": "certbot-renew"}])}},
    ("crowdsec.crowdsec_unban", "/crowdsec/unban", "POST"): {
        "data": {"confirmed": "yes", "connection": "fixture", "decision_id": "1", "value": "192.0.2.1", "scope": "ip", "decision_type": "ban"}
    },
    ("instances.instances_new", "/instances/new", "POST"): {"data": {"hostname": "new.test", "name": "Fixture"}},
    ("instances.instances_action", "/instances/<string:action>", "POST"): {"values": {"action": "reload"}, "data": {"instances": "fixture.test"}},
    ("plugins.delete_plugin", "/plugins/delete", "POST"): {"data": {"plugins": "fixture"}},
    ("plugins.plugins_refresh", "/plugins/refresh", "POST"): {"data": {"csrf_token": "fixture"}},
    ("plugins.upload_plugin", "/plugins/upload", "POST"): {"data": {"file": (b"", "uploaded.zip")}},
    ("global_settings.global_settings_page", "/global-settings", "POST"): {"data": {"csrf_token": "fixture", "LOG_LEVEL": "debug"}},
    ("global_settings.global_settings_page", "/global-config", "POST"): {"data": {"csrf_token": "fixture", "LOG_LEVEL": "debug"}},
    ("pro.pro_key", "/pro/key", "POST"): {"data": {"PRO_LICENSE_KEY": "fixture"}},
    ("pro.force_check", "/pro/force-check", "POST"): {},
    ("pro.force_update", "/pro/force-update", "POST"): {},
    ("pro.refresh_ui", "/pro/refresh-ui", "POST"): {},
    ("cache.cache_delete_bulk", "/cache/delete", "POST"): {
        "data": {"cache_files": dumps([{"fileName": "fixture", "jobName": "fixture", "service": "global", "plugin": "fixture"}])}
    },
    ("configs.configs_convert", "/configs/convert", "POST"): {"data": {"configs": CONFIG_SELECTION, "convert_to": "draft"}},
    ("configs.configs_delete", "/configs/delete", "POST"): {"data": {"configs": CONFIG_SELECTION}},
    ("configs.configs_new", "/configs/new", "POST"): {"data": CONFIG_FORM},
    ("configs.configs_edit", "/configs/<string:service>/<string:config_type>/<string:name>", "POST"): {
        "values": {"service": "global", "config_type": "http", "name": "fixture"},
        "data": CONFIG_FORM,
    },
    ("configs.configs_import", "/configs/import", "POST"): {"data": {"configs_file": (CONFIG_EXPORT, "configs.json")}},
    ("templates.templates_create", "/templates/create", "POST"): {"data": TEMPLATE_FORM},
    ("templates.templates_update", "/templates/<template_id>/update", "POST"): {"values": {"template_id": "fixture"}, "data": TEMPLATE_FORM},
    ("templates.templates_delete_multiple", "/templates/delete", "POST"): {"data": {"templates": "fixture"}},
    ("templates.templates_delete", "/templates/<template_id>/delete", "POST"): {"values": {"template_id": "fixture"}},
    ("bans.bans_ban", "/bans/ban", "POST"): {"data": {"bans": dumps([{"ip": "192.0.2.1", "exp": 3600}])}},
    ("bans.bans_crowdsec_preview", "/bans/crowdsec_preview", "POST"): {"json": {"ip": "192.0.2.1", "ban_scope": "global"}},
    ("bans.bans_unban", "/bans/unban", "POST"): {"data": {"ips": dumps([{"ip": "192.0.2.1", "ban_scope": "global"}])}},
    ("bans.bans_update_duration", "/bans/update_duration", "POST"): {"data": {"updates": dumps([{"ip": "192.0.2.1", "duration": "1h"}])}},
    ("letsencrypt.letsencrypt_delete", "/letsencrypt/delete", "POST"): {"json": {"cert_name": "example.test"}},
    ("letsencrypt.letsencrypt_heal", "/letsencrypt/heal", "POST"): {"json": {"cert_name": "example.test"}},
}
QUERY_ONLY_WRITES = {
    ("services.services_validate_certificate", "/services/validate-certificate", "POST"): (
        "Validates input certificate/key without storage; no database guard",
        200,
    ),
    ("bans.bans_crowdsec_preview", "/bans/crowdsec_preview", "POST"): ("Queries CrowdSec decisions; existing database guard returns 423", 423),
}
WRITES = [triple for triple in triples("write") if triple not in QUERY_ONLY_WRITES]


def tar_bytes(files):
    data = BytesIO()
    with tar_open(fileobj=data, mode="w:gz") as archive:
        for name, value in files.items():
            payload = value.encode()
            info = TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, BytesIO(payload))
    return data.getvalue()


def plugin_zip():
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("plugin.json", (Path(__file__).resolve().parents[4] / "src/common/core/letsencrypt/plugin.json").read_bytes())
    return data.getvalue()


def tree_hashes(loaded):
    roots = ("core", "external", "pro", "cache", "ui")
    return {str(p.relative_to(loaded.tmp)): sha256(p.read_bytes()).hexdigest() for root in roots for p in (loaded.tmp / root).rglob("*") if p.is_file()}


@pytest.fixture
def write_app(matrix_app, monkeypatch):
    loaded = matrix_app
    db = loaded.db
    from app.models.ui_database import UIDatabase

    for name in dir(UIDatabase):
        if name.startswith(MUTATOR_PREFIXES):
            getattr(db, name).return_value = ""
    config = {"SERVER_NAME": "fixture.test", "LOG_LEVEL": "info"}
    db.get_config.side_effect = lambda **kw: (
        {key: {"value": val, "method": "ui", "global": True} for key, val in config.items()} if kw.get("methods") else config.copy()
    )
    loaded.deps.BW_CONFIG.get_config.return_value = config.copy()
    loaded.deps.BW_CONFIG.check_variables.side_effect = lambda variables, *args, **kwargs: variables.copy()
    loaded.deps.BW_CONFIG.get_plugins.return_value = {}
    db.get_services.return_value = [{"id": "fixture.test", "method": "ui", "is_draft": False}]
    db.get_custom_config.return_value = {
        "type": "http",
        "name": "fixture",
        "data": b"# old",
        "method": "ui",
        "template": None,
        "is_draft": False,
        "service_id": None,
    }
    db.get_custom_configs.return_value = [db.get_custom_config.return_value]
    db.get_template_details.return_value = {"name": "Fixture", "settings": {}, "steps": [], "configs": []}
    db.delete_custom_configs.return_value = ("", {(None, "http", "fixture")}, set())
    loaded.deps.BW_INSTANCES_UTILS.get_instances.return_value = []
    db.get_instances.return_value = [{"hostname": "fixture.test", "method": "ui"}]
    loaded.deps.BW_INSTANCES_UTILS.get_bans.return_value = [{"ip": "192.0.2.1", "ban_scope": "global", "reason": "ui"}]
    # Deferred work is observed at submit, without threads or real instance/API calls.
    from _ui_core_main import DeferredExecutor

    executor = DeferredExecutor()
    for name in ("instances", "plugins", "utils"):
        monkeypatch.setattr(import_module("app.routes." + name), "CONFIG_TASKS_EXECUTOR", executor)
    loaded.deps.CONFIG_TASKS_EXECUTOR = executor
    cache = loaded.tmp / "cache"
    cache.mkdir(exist_ok=True)
    (cache / "fixture").write_bytes(b"unchanged job cache")
    ui = loaded.tmp / "ui/ui"
    ui.mkdir(parents=True)
    (ui / "fixture.zip").write_bytes(plugin_zip())
    db.get_jobs_cache_files.return_value = [
        {
            "file_name": "folder:cache.tgz",
            "data": tar_bytes(
                {
                    "renewal/example.test.conf": "account = missing\nserver = https://acme.example/directory\n",
                    "live/example.test/fullchain.pem": "pem",
                    "archive/example.test/cert1.pem": "pem",
                }
            ),
        }
    ]
    le = unwrap(loaded.app.view_functions["letsencrypt.letsencrypt_delete"]).__globals__
    loaded.process_calls = []

    def run(*args, **kwargs):
        loaded.process_calls.append((args, kwargs))
        if db.readonly:
            raise AssertionError("subprocess attempted under DB.readonly")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(subprocess, "Popen", run)
    monkeypatch.setitem(le, "run", run)
    # CrowdSec unban persists remotely, so observe its outbound mutation too.
    loaded.crowdsec = Mock()
    loaded.crowdsec.connections.return_value = {
        "connections": [{"id": "fixture", "management_configured": True, "node": "node", "local_id": "local", "status": "success", "services": ["global"]}]
    }
    loaded.crowdsec._instances.return_value = [{"hostname": "fixture.test", "status": "up"}]
    loaded.crowdsec.instance_request.return_value = {"found": True, "row": {"reason_data": {"instance": "node", "connection": "local"}}}
    loaded.crowdsec.query.return_value = {"status": "ok", "decisions": [], "total": 0}
    monkeypatch.setattr(import_module("app.routes.crowdsec"), "CrowdSecClient", lambda db: loaded.crowdsec)
    monkeypatch.setattr(import_module("app.routes.bans"), "CrowdSecClient", lambda db: loaded.crowdsec)
    return loaded


def attempts(loaded):
    return (
        mutation_attempts(loaded)
        + [str(c) for c in loaded.crowdsec.query.call_args_list if c.args[1] != "decisions"]
        + [str(c) for c in loaded.crowdsec.instance_request.call_args_list if c.args[2] != "/lease_lookup"]
        + [str(c) for c in loaded.process_calls]
    )


def request_write(loaded, triple):
    payload = deepcopy(VALID_WRITE_PAYLOADS[triple])
    values = payload.pop("values", {})
    if triple[0] == "services.services_validate_certificate":
        key = ec.generate_private_key(ec.SECP256R1())
        now = datetime.now(timezone.utc)
        name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "example.test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(1)
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256())
        )
        payload["data"] = {
            "cert": cert.public_bytes(serialization.Encoding.PEM).decode(),
            "key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
        }

    for key, value in payload.get("data", {}).items():
        if isinstance(value, tuple):
            data, name = value
            payload["data"][key] = (BytesIO(plugin_zip() if name.endswith(".zip") else data), name)
    loaded.last_client = signed_client(loaded, reader=False)
    return loaded.last_client.open(route_url(loaded, triple, values), method=triple[2], headers={"Sec-Fetch-Mode": "cors"}, **payload)


def test_valid_write_payloads_cover_manifest():
    assert set(VALID_WRITE_PAYLOADS) == {key for key, (cls, _) in ROUTE_CLASSES.items() if cls == "write"}
    assert set(QUERY_ONLY_WRITES) < set(VALID_WRITE_PAYLOADS)
    assert all(reason and status in {200, 403, 409, 423} for reason, status in QUERY_ONLY_WRITES.values())


@pytest.mark.parametrize("triple", WRITES)
def test_writable_admin_positive_control(write_app, triple):
    before = tree_hashes(write_app)
    response = request_write(write_app, triple)
    assert response.status_code < 400, (triple, response.status_code, response.data)
    assert attempts(write_app) or tree_hashes(write_app) != before, (triple, response.status_code, response.data)


@pytest.mark.parametrize("triple", QUERY_ONLY_WRITES)
@pytest.mark.parametrize("readonly", [False, True])
def test_query_only_writes_execute_without_mutation(write_app, triple, readonly):
    write_app.db.readonly = readonly
    before = tree_hashes(write_app)
    response = request_write(write_app, triple)
    assert response.status_code == (QUERY_ONLY_WRITES[triple][1] if readonly else 200), (triple, response.data)
    assert attempts(write_app) == []
    assert tree_hashes(write_app) == before


@pytest.mark.parametrize("triple", WRITES)
def test_db_readonly_write_routes_change_nothing(write_app, triple):
    write_app.db.readonly = True
    before = tree_hashes(write_app)
    response = request_write(write_app, triple)
    assert attempts(write_app) == [], triple
    assert tree_hashes(write_app) == before, triple
    assert response.status_code in {302, 403, 409, 423}, (triple, response.status_code, response.data)
    if response.status_code == 302:
        with write_app.last_client.session_transaction() as sess:
            assert any("read-only" in str(item).lower() for item in sess.get("_flashes", [])), (triple, dict(sess))
