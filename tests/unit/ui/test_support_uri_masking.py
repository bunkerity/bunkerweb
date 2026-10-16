"""The support configuration export masks the password inside a database URI (dev cf41cd57c).

``DATABASE_URI`` and ``DATABASE_URI_READONLY`` are ``type: text``, so ``redact_secrets`` (``type: password`` only)
let ``mysql+pymysql://user:secret@host/db`` through to the bundle. 1.7 keeps its own rule: no clear export.

The password may hold ``@`` (SQLAlchemy ends it at the last ``@`` of the authority), so the masker must too.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.models import secret_settings  # type: ignore  (src/ui on path via the ui conftest)

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "support.py"

PYMYSQL = "mysql+pymysql://bunkerweb:p@ss:w@rd@db.example.com:3306/db?charset=utf8mb4"
POSTGRES = "postgresql://bunkerweb:s3@cr@t@pg.example.com/bw"
SQLITE = "sqlite:////var/lib/bunkerweb/db.sqlite3"


@pytest.mark.parametrize(
    "uri, expected",
    (
        (PYMYSQL, "mysql+pymysql://bunkerweb:[REDACTED]@db.example.com:3306/db?charset=utf8mb4"),
        (POSTGRES, "postgresql://bunkerweb:[REDACTED]@pg.example.com/bw"),
        ("postgresql://bunkerweb@pg.example.com/bw", "postgresql://bunkerweb@pg.example.com/bw"),
        (SQLITE, SQLITE),
        ("", ""),
    ),
)
def test_mask_uri(uri, expected):
    assert secret_settings.mask_uri(uri) == expected


@pytest.fixture
def support_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    module_name = "app.routes._support_uri_masking_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        yield module


def _export(module, **query):
    module.BW_CONFIG.get_plugins_settings.return_value = {
        "DATABASE_URI": {"type": "text"},
        "DATABASE_URI_READONLY": {"type": "text"},
        "API_TOKEN": {"type": "password"},
        "LOG_LEVEL": {"type": "text"},
    }
    module.BW_CONFIG.get_config.return_value = {
        "DATABASE_URI": {"value": PYMYSQL, "default": SQLITE, "method": "scheduler"},
        "DATABASE_URI_READONLY": {"value": POSTGRES, "default": "", "method": "scheduler"},
        "API_TOKEN": {"value": "tok", "default": "", "method": "scheduler"},
        "LOG_LEVEL": {"value": "info", "default": "notice", "method": "scheduler"},
    }
    app = Flask(__name__)
    with app.test_request_context("/support/config", query_string=query), patch.object(module, "current_user", SimpleNamespace(list_permissions=["write"])):
        response = module.support_config.__wrapped__()
        response.direct_passthrough = False
        return response.get_data(as_text=True)


def test_export_masks_database_uri_passwords(support_route):
    body = _export(support_route)
    for secret in ("p@ss:w@rd", "s3@cr@t", "tok"):
        assert secret not in body
    exported = json.loads(body)
    assert exported["DATABASE_URI"]["value"] == "mysql+pymysql://bunkerweb:[REDACTED]@db.example.com:3306/db?charset=utf8mb4"
    assert exported["DATABASE_URI_READONLY"]["value"] == "postgresql://bunkerweb:[REDACTED]@pg.example.com/bw"
    assert exported["LOG_LEVEL"]["value"] == "info"


def test_export_has_no_clear_variant(support_route):
    """Asking for clear values changes nothing: 1.7 has no clear export."""
    assert "p@ss:w@rd" not in _export(support_route, mask_passwords="no")


# W25-FIXRED task 2: a password holding "/", "?" or "#" is still masked whole. SQLAlchemy is the oracle for the password.
@pytest.mark.parametrize("password", ("secret/word", "sec?ret", "se#cret", "a/b?c#d", "/lead", "trail/", "#", "x//y"))
@pytest.mark.parametrize("scheme", ("postgresql", "mysql+pymysql"))
def test_mask_uri_hides_a_password_with_url_delimiters(scheme, password):
    from sqlalchemy.engine.url import make_url

    uri = f"{scheme}://bunkerweb:{password}@pg.example.com:5432/bw?sslmode=require&note=a@b"
    parsed = make_url(uri)
    assert parsed.password == password and parsed.host == "pg.example.com", "the oracle must read the whole password"
    assert secret_settings.mask_uri(uri) == f"{scheme}://bunkerweb:[REDACTED]@pg.example.com:5432/bw?sslmode=require&note=a@b"
