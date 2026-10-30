"""The `api` and `ui` templates carry the whitelist settings dev added to them.

The `api` template ships the whole whitelist family as a step of its own, switched on; the `ui`
template pre-declares the two reverse-DNS and ASN lists empty so a fresh web UI service does not
whitelist crawlers it never serves. Each setting named in `settings` must also appear in a step,
or the wizard never shows it.
"""

from json import loads
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "src" / "common" / "core" / "templates" / "templates"


def _template(name):
    return loads((TEMPLATES / f"{name}.json").read_text(encoding="utf-8"))


def _step_settings(template):
    return {setting for step in template["steps"] for setting in step["settings"]}


def test_the_api_template_whitelist_step():
    template = _template("api")
    settings = template["settings"]
    whitelist = {
        "WHITELIST_IP",
        "WHITELIST_RDNS",
        "WHITELIST_ASN",
        "WHITELIST_USER_AGENT",
        "WHITELIST_URI",
        "WHITELIST_HEADER_VALUE",
        "WHITELIST_IP_URLS",
        "WHITELIST_RDNS_URLS",
        "WHITELIST_ASN_URLS",
        "WHITELIST_USER_AGENT_URLS",
        "WHITELIST_URI_URLS",
    }

    assert settings["USE_WHITELIST"] == "yes"
    assert {k: settings.get(k) for k in whitelist} == {k: "" for k in whitelist}
    assert whitelist | {"USE_WHITELIST"} <= _step_settings(template)


def test_the_ui_template_empties_the_rdns_and_asn_whitelists():
    template = _template("ui")

    assert template["settings"]["WHITELIST_RDNS"] == ""
    assert template["settings"]["WHITELIST_ASN"] == ""
    assert {"WHITELIST_RDNS", "WHITELIST_ASN"} <= _step_settings(template)


@pytest.mark.parametrize("name", ["api", "ui"])
def test_every_template_setting_is_shown_in_a_step(name):
    template = _template(name)

    assert set(template["settings"]) <= _step_settings(template)
