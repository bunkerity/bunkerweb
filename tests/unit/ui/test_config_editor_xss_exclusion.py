"""ModSecurity/CRS must not block a config-editor POST whose body is itself an XSS rule pattern.

`/configs/new` and `/configs/<service>/<type>/<name>` accept arbitrary custom-config text --
including someone pasting a CRS/ModSecurity exclusion that itself looks like an XSS payload
(e.g. a `<script>` snippet in a `SecRule ... "z:xss"` line). CRS rules 941140/941160/941210
anomaly-score that pattern in ARGS:value and block the save. The fix scopes a POST-only,
config-editor-only target removal for those three rule IDs -- narrow enough that it must not
match the sibling `/configs/.+$` id:1007773 rule's broader surface (which stays active for
GET and for every other configs sub-path). (port of dev 6d381f2f0)

Every assertion below is scoped to the `id:1007782` rule block itself (bounded by the marker
comment and the next distinct rule), not the whole file -- a whole-file scan would still pass
if the POST gate or the ARGS:value scoping were deleted from 1007782 as long as some other,
unrelated rule in the file happened to contain the same substring.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HTTP_CONF = REPO / "src" / "common" / "core" / "ui" / "confs" / "http" / "ui.modsec-crs"
CRS_CONF = REPO / "src" / "common" / "core" / "ui" / "confs" / "modsec-crs" / "ui.conf"

TARGET_RULE_IDS = ("941140", "941160", "941210")
MARKER = "# Configuration content may contain XSS rule patterns."
NEXT_RULE = 'SecRule REQUEST_FILENAME "@endsWith /logs"'


def _extract_block(text: str) -> str:
    start = text.index(MARKER)
    end = text.index(NEXT_RULE, start)
    return text[start:end]


def _extract_rx_pattern(block: str) -> str:
    match = re.search(r'REQUEST_FILENAME\s+"@rx\s+(?P<pattern>[^"]+)"', block)
    assert match, f"no REQUEST_FILENAME @rx rule in the id:1007782 block:\n{block}"
    return match.group("pattern")


def _assert_scoped_to_config_editor(text: str, path: Path) -> None:
    block = _extract_block(text)
    assert "id:1007782," in block, f"{path}: no id:1007782 rule found before the next rule"

    pattern = _extract_rx_pattern(block)
    rx = re.compile(pattern)

    assert rx.search("/configs/new"), f"{path}: id:1007782 must match the new-config editor path"
    assert rx.search("/configs/app.example.com/http/api.conf"), f"{path}: id:1007782 must match an existing config's editor path"
    assert not rx.search("/configs"), f"{path}: id:1007782 must not match the bare /configs listing"
    assert not rx.search("/services/app.example.com"), f"{path}: id:1007782 must not broaden beyond the config editor"

    for rule_id in TARGET_RULE_IDS:
        assert f"ctl:ruleRemoveTargetById={rule_id};ARGS:value" in block, (
            f"{path}: id:1007782 must scope its target removal to ARGS:value on rule {rule_id} " "only, not remove the rule outright"
        )

    assert re.search(r'REQUEST_METHOD\s+"@streq POST"', block), f"{path}: the exclusion must be POST-only, so a GET request is still scanned normally"


def test_http_ui_modsec_crs_xss_exclusion_scoped_to_config_editor():
    _assert_scoped_to_config_editor(HTTP_CONF.read_text(), HTTP_CONF)


def test_modsec_crs_ui_conf_xss_exclusion_scoped_to_config_editor():
    _assert_scoped_to_config_editor(CRS_CONF.read_text(), CRS_CONF)


def test_http_ui_modsec_crs_exclusion_still_requires_the_ui_host():
    block = _extract_block(HTTP_CONF.read_text())
    assert "REQUEST_HEADERS:Host" in block, f"{HTTP_CONF}: the multisite variant must still gate on ui_hosts like every other rule here"
