"""Autoconf never writes a secret setting value to its logs, at any level."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from _autoconf_helpers import attach_log

from Config import REDACTED, Config, is_sensitive_key, redact_secrets
from controllers.KubernetesController import KubernetesController

SECRET = "s3cr3t-value-do-not-log"
HOST = "app.example.com"


@pytest.fixture
def cfg(fake_db):
    config = Config("docker")
    config.log = attach_log(SimpleNamespace(_logger=config._Config__logger))
    return config


def _logged(cfg):
    return " ".join(record.getMessage() for record in cfg.log.records)


def _instances(token):
    return [{"name": "bw", "hostname": "bw", "env": {"API_TOKEN": token, "SERVER_NAME": HOST}}]


def test_instance_service_and_config_debug_lines_hide_secret_values(cfg):
    service = {"SERVER_NAME": HOST, "CUSTOM_SSL_KEY_DATA": SECRET, "REVERSE_PROXY_SSL_KEY_DATA_1": SECRET, "USE_ANTIBOT": "captcha"}
    configs = {"http": {"site.conf": SECRET.encode()}}

    assert cfg.apply(_instances(SECRET), [service], configs=configs, first=True)
    # a second poll with other values reaches every "... changed:" debug line
    assert cfg.update_needed(_instances(SECRET + "2"), [{**service, "CUSTOM_SSL_KEY_DATA": SECRET + "2"}], configs={"http": {"site.conf": b"other"}})

    logged = _logged(cfg)
    assert "Updating instances in database" in logged and "Saving config in database" in logged
    assert "USE_ANTIBOT" in logged and "captcha" in logged
    assert SECRET not in logged


def test_a_rejected_label_is_logged_by_key_only(cfg):
    cfg.apply([{"name": "bw"}], [{"SERVER_NAME": HOST, "NOT_A_SETTING": SECRET}])

    assert cfg.log.has("Variable NOT_A_SETTING is not a valid autoconf setting", logging.WARNING)
    assert SECRET not in _logged(cfg)


def _password_setting_names():
    root = Path(__file__).resolve().parents[3] / "src" / "common"
    names = set()
    for path in [root / "settings.json", *sorted((root / "core").glob("*/plugin.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = data.get("settings", data)
        names.update(name for name, setting in settings.items() if isinstance(setting, dict) and setting.get("type") == "password")
    return names


def test_every_password_type_setting_is_redacted():
    names = _password_setting_names()
    assert "REDIS_PASSWORD" in names  # the walk found the plugin.json files

    unmatched = set()
    for name in sorted(names):
        for variant in (name, f"{HOST}_{name}", f"{name}_1", f"{HOST}_{name}_2"):
            redacted = redact_secrets({variant: SECRET})
            formatted = KubernetesController._format_conflict_value(None, variant, SECRET)
            if not (is_sensitive_key(variant) and redacted == {variant: REDACTED} and formatted == f"'{REDACTED}'"):
                unmatched.add(name)
    assert not unmatched
