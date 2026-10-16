"""`BANS_TLS_DROP_REASONS`: the core setting that arms the TLS ClientHello drop (CrowdSec port, lane C).

Off by default (secure defaults: nothing changes for a deployment that does not list a reason), five
reasons only, one entry per place a setting has to be described: `settings.json`, the five core
READMEs and the 19 UI catalogs (`general.settings.*`, where core settings have no plugin directory).
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = json.loads((ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8"))["BANS_TLS_DROP_REASONS"]
REASONS = ("crowdsec", "bad_behavior", "manual", "ui", "api")
LOCALES = sorted((ROOT / "src" / "ui" / "app" / "static" / "locales").glob("*.json"))


def test_the_setting_is_a_multisite_multiselect_that_defaults_to_off():
    assert SETTINGS["context"] == "multisite"
    assert SETTINGS["default"] == ""
    assert SETTINGS["type"] == "multiselect"
    assert [option["value"] for option in SETTINGS["multiselect"]] == list(REASONS)
    assert all(option["id"] == option["value"] and option["label"] for option in SETTINGS["multiselect"])


@pytest.mark.parametrize("value", ["", "crowdsec", "crowdsec manual", " ".join(REASONS)])
def test_the_regex_accepts_empty_and_any_space_separated_reasons(value):
    assert re.fullmatch(SETTINGS["regex"], value)


@pytest.mark.parametrize("value", ["antibot", "crowdsec,manual", "crowdsec  manual", "Crowdsec", "crowdsec antibot", " crowdsec", "crowdsec "])
def test_the_regex_refuses_everything_else(value):
    assert not re.fullmatch(SETTINGS["regex"], value)


def test_the_help_fits_the_catalogue_limit_and_states_the_proxy_protocol_rule():
    assert len(SETTINGS["help"]) <= 512
    assert "proxy_protocol" in SETTINGS["help"]


@pytest.mark.parametrize("readme", sorted((ROOT / "src" / "common").glob("README*.md")), ids=lambda p: p.name)
def test_every_core_readme_has_exactly_one_row(readme):
    rows = [line for line in readme.read_text(encoding="utf-8").splitlines() if line.lstrip().startswith("| `BANS_TLS_DROP_REASONS`")]
    assert len(rows) == 1
    assert "multisite" in rows[0]
    assert all(f"`{reason}`" in rows[0] for reason in REASONS)


@pytest.mark.parametrize("catalog", LOCALES, ids=lambda p: p.stem)
def test_every_ui_catalog_describes_the_setting(catalog):
    entry = json.loads(catalog.read_text(encoding="utf-8"))["general"]["settings"]["BANS_TLS_DROP_REASONS"]
    assert entry["label"].strip() and entry["help"].strip()
    assert "proxy_protocol" in entry["help"]


def test_the_english_catalog_matches_settings_json():
    en = json.loads((ROOT / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
    entry = en["general"]["settings"]["BANS_TLS_DROP_REASONS"]
    assert entry == {"label": SETTINGS["label"], "help": SETTINGS["help"]}
