"""Three small UI ports from 1.6.16 (dev 6b4915994, 890d8777c, 726ff8ad2 templates part).

Source-text assertions: this suite has no JS or browser runtime, and each defect is which string the shipped
file holds.
"""

import re
from pathlib import Path

UI = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"


def test_bans_investigate_link_is_gated_on_a_crowdsec_reason():
    """The Investigate link opens the CrowdSec page for the IP: only a CrowdSec ban has evidence there."""
    source = (UI / "static" / "js" / "pages" / "bans.js").read_text(encoding="utf-8")
    link = source.index('"crowdsec.investigation.submit"')
    before = source[source.rindex("const investigateUrl", 0, link) : link]
    assert "row.reason" in before and '=== "crowdsec"' in before, "Investigate must depend on row.reason being crowdsec"
    assert re.search(r"isCrowdsecBan\s*\?", before)


def test_tooltips_are_wider_and_wrap_long_words():
    css = (UI / "static" / "css" / "overrides" / "base.css").read_text(encoding="utf-8")
    assert "--bs-tooltip-max-width: 320px;" in css
    assert re.search(r"\.tooltip-inner\s*{[^}]*overflow-wrap:\s*anywhere;", css)


def test_templates_delete_alert_names_templates_not_instances():
    html = (UI / "templates" / "templates.html").read_text(encoding="utf-8")
    line = next(line for line in html.splitlines() if "alert(message=" in line and "selected template" in line)
    assert 'message_key="modal.body.confirm_templates_deletion_alert"' in line
    assert "delete_confirmation_alert" not in line
