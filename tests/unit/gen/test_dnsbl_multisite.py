"""DNSBL service overrides and preservation of pre-upgrade global lists (#4018)."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from Configurator import Configurator
from fixtures.seed import add_global_value, add_service, add_service_setting, make_general_settings, session
from model import Global_values, Settings

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src/common/core"
PLUGIN = CORE / "dnsbl/plugin.json"


@pytest.mark.parametrize("from_file", [False, True], ids=["env", "variables.env"])
def test_service_override_and_global_inheritance(tmp_path, quiet_logger, from_file):
    variables = {
        "MULTISITE": "yes",
        "SERVER_NAME": "api.example.com www.example.com",
        "DNSBL_LIST": "global.bl",
        "api.example.com_DNSBL_LIST": "partner.bl",
    }
    if from_file:
        path = tmp_path / "variables.env"
        path.write_text("".join(f"{key}={value}\n" for key, value in variables.items()))
        variables = str(path)
    config = Configurator(str(ROOT / "src/common/settings.json"), str(CORE), [], [], variables, quiet_logger).get_config(None)
    assert config["DNSBL_LIST"] == "global.bl"
    assert config["api.example.com_DNSBL_LIST"] == "partner.bl"
    assert config["www.example.com_DNSBL_LIST"] == "global.bl"


def test_plugin_upgrade_keeps_global_value_and_accepts_service_writes(db):
    shipped = json.loads(PLUGIN.read_text())
    old = deepcopy(shipped)
    old["settings"]["DNSBL_LIST"]["context"] = "global"
    _, err = db.init_tables([make_general_settings(), old])
    assert not err
    add_service(db, "api.example.com")
    add_service(db, "www.example.com")
    add_global_value(db, setting_id="MULTISITE", value="yes")
    add_global_value(db, setting_id="DNSBL_LIST", value="global.bl", method="ui")

    _, err = db.init_tables([make_general_settings(), shipped])
    assert not err
    with session(db) as s:
        assert s.query(Settings).filter_by(id="DNSBL_LIST").one().context == "multisite"
        row = s.query(Global_values).filter_by(setting_id="DNSBL_LIST").one()
        assert (row.value, row.method) == ("global.bl", "ui")
    # Shared validator used by the API, UI and autoconf service write paths.
    assert db.is_valid_setting("DNSBL_LIST", value="global.bl") == (True, "")
    assert db.is_valid_setting("api.example.com_DNSBL_LIST", value="partner.bl", multisite=True) == (True, "")
    add_service_setting(db, service_id="api.example.com", setting_id="DNSBL_LIST", value="partner.bl")
    config = db.get_config()
    assert config["DNSBL_LIST"] == "global.bl"
    assert config["api.example.com_DNSBL_LIST"] == "partner.bl"
    assert config["www.example.com_DNSBL_LIST"] == "global.bl"
