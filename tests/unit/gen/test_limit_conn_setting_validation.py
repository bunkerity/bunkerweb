"""Connection quotas must pass NGINX's ASCII integer parser and 1..65535 check."""

import json
from pathlib import Path

import pytest

from _t5_helpers import configured
from fixtures.seed import make_general_settings

MANIFEST = Path(__file__).resolve().parents[3] / "src/common/core/limit/plugin.json"
DEFAULTS = {"LIMIT_CONN_MAX_HTTP1": "10", "LIMIT_CONN_MAX_HTTP2": "100", "LIMIT_CONN_MAX_HTTP3": "100", "LIMIT_CONN_MAX_STREAM": "10"}
CASES = [
    (value, True)
    for value in (
        "1",
        "10",
        "100",
        "9999",
        "10000",
        "59999",
        "60000",
        "64999",
        "65000",
        "65499",
        "65500",
        "65529",
        "65530",
        "65535",
        "0001",
        "00065535",
        "0" * 100 + "1",
    )
]
CASES += [
    (value, False)
    for value in ("0", "00", "65536", "99999", "100000", "9" * 100, "١", "١٠", "１", "１００", "1١", "", "-1", "+1", "1.0", " 1", "1 ", "1;", "1x")
]


@pytest.mark.parametrize("value,valid", CASES)
def test_configurator_keeps_only_nginx_compatible_connection_quotas(value, valid, monkeypatch):
    monkeypatch.delenv("IGNORE_REGEX_CHECK", raising=False)
    config = configured(**dict.fromkeys(DEFAULTS, value))
    assert {name: config[name] for name in DEFAULTS} == {name: value if valid else default for name, default in DEFAULTS.items()}


@pytest.mark.parametrize("value,valid", CASES)
def test_database_validates_shipped_connection_quotas(db, value, valid):
    assert db.init_tables([make_general_settings(), json.loads(MANIFEST.read_text())])[0]
    for name in DEFAULTS:
        accepted, error = db.is_valid_setting(name, value=value, multisite=True)
        assert accepted is valid, (name, value, error)


def test_connection_quota_defaults_stay_unchanged():
    settings = json.loads(MANIFEST.read_text())["settings"]
    assert {name: settings[name]["default"] for name in DEFAULTS} == DEFAULTS
    config = configured()
    assert {name: config[name] for name in DEFAULTS} == DEFAULTS
