"""The Web UI support export and `bwcli support` leak no secret from one fixture holding every secret kind (dev 4a91e1e13).

Secret kinds: password settings, a DB URI whose password holds ``@``, credentials inside header list settings
(``REVERSE_PROXY_HEADERS``, ``CUSTOM_HEADER``), PEM private-key text (a ``_KEY_DATA`` setting and log text), API tokens,
bearer tokens in logs and credentials in the generated NGINX configuration. Three producers write it out: the UI
configuration export, the UI diagnostics bundle (logs) and ``bwcli support``. On the tree before the port the UI
exports leaked the header credentials and the key data, and ``bwcli support`` did not exist.
"""

import importlib.util
import json
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from zipfile import ZipFile

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[3]
for _path in ("cli", "api", "utils", "db"):
    if str(ROOT / "src" / "common" / _path) not in sys.path:
        sys.path.insert(0, str(ROOT / "src" / "common" / _path))

ROUTE_PATH = ROOT / "src" / "ui" / "app" / "routes" / "support.py"

PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7pemkeyBODY"
PEM = f"-----BEGIN PRIVATE KEY-----\n{PEM_BODY}\nQUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=\n-----END PRIVATE KEY-----\n"
SECRETS = {
    "password setting": "sessSECRETvalue9f3a",
    "api token": "apitokenVALUE7c1d",
    "database uri password": "pw@ss:w@rd-4b2e",
    "header credential": "hdrBEARERvalue5e8a",
    "custom header credential": "hdrAPIKEYvalue2d6f",
    "pem in a setting": PEM_BODY,
    "pem in a log": "LOGKEYbody0123456789abcdefghijklmnop",
    "bearer in a log": "logBEARER8821xyz",
    "token in a log": "logTOKENvalue77",
    "nginx header": "nginxBEARER4411",
    "nginx variable": "nginxSETvar99",
}

SETTINGS = {
    "SERVER_NAME": {"type": "text"},
    "SESSIONS_SECRET": {"type": "password"},
    "API_TOKEN": {"type": "password"},
    "DATABASE_URI": {"type": "text"},
    "REVERSE_PROXY_HEADERS": {"type": "multivalue"},
    "CUSTOM_HEADER": {"type": "text"},
    "GRPC_SSL_CLIENT_KEY_DATA": {"type": "file"},
    "LOG_LEVEL": {"type": "select"},
}
CONFIG = {
    "SERVER_NAME": {"value": "www.example.com", "default": "www.example.com", "method": "scheduler"},
    "SESSIONS_SECRET": {"value": SECRETS["password setting"], "default": "", "method": "scheduler"},
    "API_TOKEN": {"value": SECRETS["api token"], "default": "", "method": "scheduler"},
    "DATABASE_URI": {"value": f"mysql+pymysql://bunkerweb:{SECRETS['database uri password']}@db.example.com:3306/bw", "default": "", "method": "scheduler"},
    "REVERSE_PROXY_HEADERS_1": {"value": f"Authorization Bearer {SECRETS['header credential']};X-Real-IP $remote_addr", "default": "", "method": "ui"},
    "www.example.com_CUSTOM_HEADER": {"value": f"X-Api-Key: {SECRETS['custom header credential']}", "default": "", "method": "ui"},
    "GRPC_SSL_CLIENT_KEY_DATA": {"value": PEM.replace(PEM_BODY, SECRETS["pem in a setting"]), "default": "", "method": "ui"},
    "LOG_LEVEL": {"value": "info", "default": "notice", "method": "scheduler"},
}
LOG_TEXT = (
    "[2026-10-15 10:00:00 +0000] [UI] [7] [ℹ️ ] - loading key\n"
    + PEM.replace(PEM_BODY, SECRETS["pem in a log"])
    + f"[2026-10-15 10:00:01 +0000] [UI] [7] [❌] - Authorization: Bearer {SECRETS['bearer in a log']}\n"
    + f"[2026-10-15 10:00:02 +0000] [UI] [7] [ℹ️ ] - api_token={SECRETS['token in a log']} loaded\n"
)
NGINX_CONF = (
    f"server {{\n  proxy_set_header Authorization 'Bearer {SECRETS['nginx header']}';\n  proxy_set_header X-Real-IP $remote_addr;\n"
    f'  set $upstream_token "{SECRETS["nginx variable"]}";\n}}\n'
)
KEPT = ("X-Real-IP $remote_addr", "[REDACTED]@db.example.com")


def _all_text(archive: bytes) -> str:
    with ZipFile(BytesIO(archive)) as bundle:
        return "\n".join(bundle.read(name).decode("utf-8", errors="replace") for name in bundle.namelist())


def _leaks(text: str):
    return sorted(kind for kind, secret in SECRETS.items() if secret in text)


@pytest.fixture
def support_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    module_name = "app.routes._support_redaction_parity_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        yield module


def ui_config_export(tmp_path, support_route, monkeypatch, anonymize):
    support_route.BW_CONFIG.get_plugins_settings.return_value = SETTINGS
    support_route.BW_CONFIG.get_config.return_value = json.loads(json.dumps(CONFIG))
    with Flask(__name__).test_request_context("/support/config"), patch.object(support_route, "current_user", SimpleNamespace(list_permissions=["write"])):
        response = support_route.support_config.__wrapped__()
        response.direct_passthrough = False
        return response.get_data(as_text=True)


def ui_diagnostics_bundle(tmp_path, support_route, monkeypatch, anonymize):
    support_bundle = pytest.importorskip("app.support_bundle")
    log_file = tmp_path / "ui.log"
    log_file.write_text(LOG_TEXT, encoding="utf-8")
    return _all_text(
        support_bundle.build_support_bundle(
            domains={"www.example.com"},
            environ={"LOG_TYPES": "file", "LOG_FILE_PATH": str(log_file)},
            integration="Docker",
            ring={"pid": 7, "started": "2026-10-15T10:00:00+00:00", "records": [LOG_TEXT], "bytes": len(LOG_TEXT)},
            plugins={"plugins": []},
            environment={"bunkerweb_version": "1.7.0"},
        )
    )


def cli_support_bundle(tmp_path, support_route, monkeypatch, anonymize):
    cli_module = pytest.importorskip("CLI")
    logs, nginx = tmp_path / "logs", tmp_path / "nginx"
    logs.mkdir()
    nginx.mkdir()
    (logs / "scheduler.log").write_text(LOG_TEXT, encoding="utf-8")
    (nginx / "server.conf").write_text(NGINX_CONF, encoding="utf-8")
    monkeypatch.setattr(cli_module, "LOG_DIR", str(logs))
    monkeypatch.setattr(cli_module, "NGINX_PATH", nginx)

    db = MagicMock()
    db.get_config.side_effect = lambda **kwargs: {"SERVER_NAME": "www.example.com"} if kwargs.get("filtered_settings") else json.loads(json.dumps(CONFIG))
    db.get_plugins.return_value = [{"id": "core", "type": "core", "version": "1.7.0", "page": False, "settings": SETTINGS}]
    db.get_metadata.return_value = {"version": "1.7.0", "database_version": "test"}
    db.get_instances.return_value = []
    db.get_services.return_value = []
    db.get_jobs.return_value = {}
    db.get_jobs_cache_files.return_value = []
    db.get_custom_configs.return_value = []
    db.sql_engine.dialect.name = "sqlite"
    db._db_session.side_effect = RuntimeError("no alembic table in the fixture")

    cli = cli_module.CLI.__new__(cli_module.CLI)
    cli._CLI__db, cli._CLI__db_error, cli._CLI__logger, cli._CLI__api_token, cli.apis = db, None, Mock(), None, []
    target = tmp_path / "bundle.zip"
    ok, message = cli.support(str(target), anonymize)
    assert ok, message
    return _all_text(target.read_bytes())


PRODUCERS = {"ui configuration export": ui_config_export, "ui diagnostics bundle": ui_diagnostics_bundle, "bwcli support": cli_support_bundle}


@pytest.mark.parametrize("anonymize", (True, False), ids=("anonymized", "kept ips and domains"))
@pytest.mark.parametrize("producer", PRODUCERS)
def test_no_producer_leaks_a_secret(producer, anonymize, tmp_path, support_route, monkeypatch):
    text = PRODUCERS[producer](tmp_path, support_route, monkeypatch, anonymize)
    assert text.strip()
    assert _leaks(text) == [], f"{producer} leaked"


@pytest.mark.parametrize("producer", ("ui configuration export", "bwcli support"))
def test_the_config_masking_keeps_what_is_not_secret(producer, tmp_path, support_route, monkeypatch):
    text = PRODUCERS[producer](tmp_path, support_route, monkeypatch, False)
    for kept in KEPT:
        assert kept in text, kept
