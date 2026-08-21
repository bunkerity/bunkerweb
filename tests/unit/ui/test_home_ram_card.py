"""The dashboard RAM card (#3820).

Two defects, one test file:

* the colour was chosen from how **big** the machine is (``total_gb < 8`` -> amber for life),
  not from how loaded it is. The bands now read ``used_percent`` only.
* ``psutil.virtual_memory()`` reads ``/proc/meminfo``, which is not cgroup-aware, so inside a
  container the card described the *host*. ``read_memory()`` prefers the cgroup limit.

Every reader test builds a fake cgroup tree under ``tmp_path`` and monkeypatches
``virtual_memory`` to an unmistakable sentinel, so the host this suite runs on can never be
the one supplying the answer (RULE 17): a test that passes because the runner happens to be
in a container -- or happens not to be -- proves nothing.
"""

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

# `psutil` is a container-only dependency (src/ui/requirements.txt); the unit venv does not
# carry it. Stub it the way test_home_dashboard.py does so the module under test imports --
# every test that matters monkeypatches the symbol anyway, so the stub is never consulted.
if "psutil" not in sys.modules:
    try:
        import psutil  # noqa: F401
    except ImportError:
        _stub = ModuleType("psutil")
        _stub.virtual_memory = lambda: SimpleNamespace(total=0, used=0, available=0)
        sys.modules["psutil"] = _stub

from app import system_memory  # noqa: E402
from app.system_memory import memory_state, read_memory  # noqa: E402

TEMPLATES = Path(__file__).parents[3] / "src" / "ui" / "app" / "templates"
LOCALES = TEMPLATES.parent / "static" / "locales"
TRANSLATIONS = TEMPLATES.parents[1] / "translations"

GIB = 1024**3

# Deliberately unlike every cgroup figure below, so "the fallback leaked in" is visible.
SENTINEL = SimpleNamespace(total=777 * GIB, used=111 * GIB, available=666 * GIB)


@pytest.fixture
def no_host_memory(monkeypatch):
    """Neutralise the psutil path: any test that does not *mean* to fall back gets caught."""
    monkeypatch.setattr(system_memory, "virtual_memory", lambda: SENTINEL)
    return SENTINEL


def _write(root: Path, **files: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (root / name.replace("__", ".")).write_text(content, encoding="utf-8")
    return root


# --------------------------------------------------------------------------------------
# Bands -- usage only
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("used_percent", "expected"),
    [
        (0.0, "good"),
        (69.9, "good"),
        (70.0, "neutral"),
        (84.9, "neutral"),
        (85.0, "warning"),
        (94.9, "warning"),
        (95.0, "danger"),
        (100.0, "danger"),
    ],
)
def test_bands_follow_usage_and_switch_exactly_at_70_85_95(used_percent, expected):
    assert memory_state(used_percent) == expected


def test_a_small_box_at_moderate_load_is_not_amber():
    """The reported symptom: 6 GB and 12 GB labs at 50-60 % were permanently amber/neutral.

    The band function has no way to know the size any more, so the regression is expressed
    the only way it still can be -- a moderate load is green, full stop.
    """
    assert memory_state(50.0) == "good"
    assert memory_state(60.0) == "good"


# --------------------------------------------------------------------------------------
# Reader -- cgroup v2
# --------------------------------------------------------------------------------------


def test_cgroup_v2_limit_wins_over_the_host(tmp_path, no_host_memory):
    root = _write(
        tmp_path,
        memory__max=str(4 * GIB),
        memory__current=str(3 * GIB),
        memory__stat="anon 1073741824\ninactive_file 1073741824\nslab 512\n",
    )
    figures = read_memory(root)
    assert figures["total"] == 4 * GIB
    # 3 GiB current minus 1 GiB reclaimable page cache -- what `docker stats` shows.
    assert figures["used"] == 2 * GIB
    assert figures["available"] == 2 * GIB
    assert figures["total"] != SENTINEL.total


def test_cgroup_v2_without_a_memory_stat_still_reports(tmp_path, no_host_memory):
    root = _write(tmp_path, memory__max=str(2 * GIB), memory__current=str(1 * GIB))
    assert read_memory(root) == {"total": 2 * GIB, "used": 1 * GIB, "available": 1 * GIB}


def test_cgroup_v2_unlimited_falls_back_to_the_host(tmp_path, no_host_memory):
    root = _write(tmp_path, memory__max="max", memory__current=str(1 * GIB))
    assert read_memory(root)["total"] == SENTINEL.total


def test_used_never_exceeds_the_limit(tmp_path, no_host_memory):
    """`memory.current` can momentarily exceed `memory.max`; a >100 % bar is a bug, not news."""
    root = _write(tmp_path, memory__max=str(GIB), memory__current=str(3 * GIB))
    figures = read_memory(root)
    assert figures["used"] == GIB
    assert figures["available"] == 0


# --------------------------------------------------------------------------------------
# Reader -- cgroup v1 and the fallback
# --------------------------------------------------------------------------------------


def test_cgroup_v1_is_used_when_v2_is_absent(tmp_path, no_host_memory):
    root = _write(
        tmp_path / "memory",
        memory__limit_in_bytes=str(8 * GIB),
        memory__usage_in_bytes=str(5 * GIB),
        memory__stat="cache 2147483648\ntotal_inactive_file 2147483648\n",
    ).parent
    figures = read_memory(root)
    assert figures["total"] == 8 * GIB
    assert figures["used"] == 3 * GIB


@pytest.mark.parametrize(
    ("sentinel", "page_size"),
    [
        ("9223372036854771712", "4K pages"),
        # LONG_MAX rounded DOWN to PAGE_SIZE, so a 64K-page kernel (aarch64 RHEL, Ampere)
        # writes a SMALLER number than the 4K one. A bound taken from the 4K value reads this
        # as a real 8 EiB limit and the card reports "0.0 % of 8388608.0 GB".
        ("9223372036854710272", "64K pages"),
    ],
)
def test_cgroup_v1_unlimited_sentinel_falls_back_to_the_host(tmp_path, no_host_memory, sentinel, page_size):
    root = _write(
        tmp_path / "memory",
        memory__limit_in_bytes=sentinel,
        memory__usage_in_bytes=str(GIB),
    ).parent
    assert read_memory(root)["total"] == SENTINEL.total, page_size


def test_a_real_multi_terabyte_limit_is_still_read_as_a_limit(tmp_path, no_host_memory):
    """The unlimited bound must not swallow a genuine (if enormous) cgroup limit."""
    limit = 4096 * GIB  # 4 TiB -- larger than any machine this runs on, still nowhere near 4 EiB
    root = _write(
        tmp_path / "memory",
        memory__limit_in_bytes=str(limit),
        memory__usage_in_bytes=str(GIB),
    ).parent
    assert read_memory(root)["total"] == limit


def test_no_cgroup_at_all_falls_back_to_the_host(tmp_path, no_host_memory):
    assert read_memory(tmp_path / "nothing-here") == {
        "total": SENTINEL.total,
        "used": SENTINEL.used,
        "available": SENTINEL.available,
    }


def test_garbage_in_the_cgroup_files_falls_back_rather_than_raising(tmp_path, no_host_memory):
    root = _write(tmp_path, memory__max="not-a-number", memory__current="also-not")
    assert read_memory(root)["total"] == SENTINEL.total


# --------------------------------------------------------------------------------------
# The card itself
# --------------------------------------------------------------------------------------


def _render_ram_band(memory_state_value):
    """Render just the status band of home.html with a given memory state."""
    env = Environment(
        loader=ChoiceLoader([DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}), FileSystemLoader(TEMPLATES)]),
        autoescape=True,
    )
    env.globals.setdefault("url_for", lambda *a, **k: "#")
    from conftest import english  # noqa: PLC0415 -- fixture-side helper, imported lazily

    env.globals["_"] = english
    source = (TEMPLATES / "home.html").read_text(encoding="utf-8")
    start = source.index('<div class="sb-col sb-ram">')
    end = source.index('<div class="sb-divider"></div>', start)
    return env.from_string(source[start:end]).render(
        memory_info={"total_gb": 8.0, "used_gb": 4.0, "used_percent": 50.0, "available_gb": 4.0, "memory_state": memory_state_value},
    )


@pytest.mark.parametrize(
    ("state", "chip", "bar"),
    [
        ("good", "sb-chip-green", ""),
        ("neutral", "sb-chip-muted", ""),
        ("warning", "sb-chip-warn", "is-warn"),
        ("danger", "sb-chip-danger", "is-danger"),
    ],
)
def test_each_band_paints_its_own_chip_and_bar(state, chip, bar):
    html = _render_ram_band(state)
    assert chip in html
    if bar:
        assert bar in html
    else:
        assert "is-warn" not in html and "is-danger" not in html


def test_the_template_knows_the_state_vocabulary_the_route_emits():
    """A rename on one side only would silently paint every card green."""
    emitted = {memory_state(p) for p in (10.0, 75.0, 90.0, 99.0)}
    assert emitted == {"good", "neutral", "warning", "danger"}
    source = (TEMPLATES / "home.html").read_text(encoding="utf-8")
    for state in emitted - {"good"}:  # "good" is the else-branch, it has no literal
        assert f"'{state}'" in source


# --------------------------------------------------------------------------------------
# The hardware-advice strings are gone everywhere
# --------------------------------------------------------------------------------------


def test_the_hardware_advice_keys_are_gone_from_every_catalog():
    catalogs = sorted(LOCALES.glob("*.json"))
    assert len(catalogs) >= 18, catalogs  # RULE 13: the list must not silently empty out
    for path in catalogs:
        ram = json.loads(path.read_text(encoding="utf-8"))["dashboard"]["card"]["ram"]
        assert "info_medium" not in ram, path
        assert "good_high" not in ram, path


def test_the_hardware_advice_keys_are_gone_from_every_gettext_catalog():
    catalogs = sorted(TRANSLATIONS.glob("*/LC_MESSAGES/messages.po"))
    assert len(catalogs) >= 18, catalogs
    for path in catalogs:
        body = path.read_text(encoding="utf-8")
        assert "dashboard.card.ram.info_medium" not in body, path
        assert "dashboard.card.ram.good_high" not in body, path
