"""BunkerWeb's own ModSecurity rules stay inside the ID ledger.

BunkerWeb owns 9,800,000-9,899,999 (CRS plugin range). OSS core uses one 1,000-ID block per component:
modsecurity 9,800,000, antibot 9,801,000, ui 9,802,000, api template 9,803,000. The CRS setup overrides
(900001, 900110, 900200, 900230, 900990) are the sanctioned crs-setup pattern and keep their IDs.
1-99,999 is local-use only and 1,000,000-8,999,999 belongs to other vendors, so nothing shipped may sit there.

The per-service UI and API exclusions declare ``phase:1`` explicitly, like their global-mode twins. libmodsecurity v3
already defaults a rule without a phase to phase 1, so this is consistency, and the test keeps the two variants aligned.
"""

import re
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
CRS_SETUP_IDS = {900001, 900110, 900200, 900230, 900990}
BLOCKS = {
    "modsecurity": 9800000,
    "antibot": 9801000,
    "ui": 9802000,
    "templates": 9803000,
}
PHASE_1_FILES = [
    CORE / "ui" / "confs" / "modsec-crs" / "ui.conf",
    CORE / "templates" / "templates" / "api" / "configs" / "modsec-crs" / "api.conf",
]


def rule_directives(path: Path):
    """Yield every SecRule/SecAction as one logical line (continuations joined, comments dropped)."""
    logical = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not logical and line.startswith("#"):
            continue
        logical += line[:-1] + " " if line.endswith("\\") else line
        if line.endswith("\\"):
            continue
        if re.match(r"(?:SecRule|SecAction)\b", logical):
            yield logical
        logical = ""


def shipped_rule_files():
    for path in sorted(CORE.rglob("*")):
        relative = path.relative_to(CORE)
        # `<component>/files/` holds the vendored CRS, which keeps its own IDs
        if not path.is_file() or len(relative.parts) < 2 or relative.parts[1] == "files":
            continue
        if not any(part in ("confs", "configs") for part in relative.parts) or path.suffix in {".md", ".json", ".lua", ".py", ".html", ".js"}:
            continue
        if any(True for _ in rule_directives(path)):
            yield path


def rule_ids(path: Path):
    ids = []
    for directive in rule_directives(path):
        match = re.search(r"\bid:'?(\d+)'?", directive)
        if match:
            ids.append(int(match.group(1)))
    return ids


def test_the_scan_finds_the_shipped_rule_files():
    names = {path.name for path in shipped_rule_files()}
    assert {"modsecurity-rules.conf.modsec", "ui.conf", "api.conf", "antibot.conf", "ip-host.conf"} <= names


@pytest.mark.parametrize("path", list(shipped_rule_files()), ids=lambda p: str(p.relative_to(CORE)))
def test_every_shipped_rule_id_lies_in_its_component_block(path):
    component = path.relative_to(CORE).parts[0]
    start = BLOCKS[component] if component in BLOCKS else None
    for rule_id in rule_ids(path):
        if rule_id in CRS_SETUP_IDS:
            continue
        assert not 1 <= rule_id <= 99999, f"{path.name}: {rule_id} is in the local-use range"
        assert not 1000000 <= rule_id <= 8999999, f"{path.name}: {rule_id} is in a range owned by other vendors"
        assert start is not None, f"{path.name}: component {component} has no block in the ledger"
        assert start <= rule_id < start + 1000, f"{path.name}: {rule_id} is outside the {component} block {start}-{start + 999}"


@pytest.mark.parametrize("path", PHASE_1_FILES, ids=lambda p: p.name)
def test_per_service_exclusions_run_in_phase_1(path):
    checked = 0
    for directive in rule_directives(path):
        if "id:" not in directive:
            continue  # a chained follower inherits the phase of its head
        checked += 1
        assert re.search(r"\bphase:1\b", directive), f"{path.name}: rule without phase:1: {directive[:120]}"
    assert checked >= 5
