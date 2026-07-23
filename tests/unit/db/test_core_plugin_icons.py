"""Convention check: every core plugin ships an in-dir ``icon.svg``.

Core plugins carry their icon in their own directory (``<id>/icon.svg``), auto-detected at DB
sync by ``resolve_plugin_icon(dir_path=...)`` and served straight off disk by the API icon
endpoint — no shared static asset, no data blob. The ``plugin.json`` ``icon`` field is an *optional*
override, not required (that is why it is not asserted here). The invariant every core plugin must
hold is: a sibling ``icon.svg`` exists, is non-empty, parses as XML with an ``<svg>`` root, and stays
under the 512KB serving cap. Pure filesystem assertions — no DB — so this guards against a new core
plugin (or a rename) landing without its shipped icon.
"""

from pathlib import Path

# Trusted input only: these SVGs are repo-committed core-plugin icons, never attacker-supplied,
# so stdlib ElementTree (no XXE/entity-expansion hardening) is fine here — no defusedxml dep.
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

CORE_PLUGIN_JSONS = sorted(CORE.glob("*/plugin.json"))

MAX_ICON_BYTES = 512 * 1024


def _local_name(tag: str) -> str:
    # Strip the ``{namespace}`` prefix ElementTree prepends for namespaced roots.
    return tag.rsplit("}", 1)[-1]


def test_all_core_plugins_ship_icon_svg():
    assert CORE_PLUGIN_JSONS, "no core plugin.json files found"
    missing_file = []
    bad_svg = []
    oversized = []
    for pj in CORE_PLUGIN_JSONS:
        pid = pj.parent.name
        svg = pj.parent / "icon.svg"
        if not svg.is_file():
            missing_file.append(pid)
            continue
        raw = svg.read_bytes()
        if not raw.strip():
            bad_svg.append((pid, "empty"))
            continue
        if len(raw) > MAX_ICON_BYTES:
            oversized.append((pid, len(raw)))
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as e:
            bad_svg.append((pid, f"unparseable: {e}"))
            continue
        if _local_name(root.tag) != "svg":
            bad_svg.append((pid, f"root <{_local_name(root.tag)}> is not <svg>"))
    assert not missing_file, f"core plugins missing their in-dir icon.svg: {missing_file}"
    assert not bad_svg, f"core plugins with an invalid icon.svg: {bad_svg}"
    assert not oversized, f"core plugins whose icon.svg exceeds 512KB: {oversized}"


def test_core_plugin_count_is_covered():
    # There are 42 core plugins today; every one is checked above. This asserts the glob
    # is actually finding them (a broken path would make the integrity test vacuous).
    assert len(CORE_PLUGIN_JSONS) == 42
