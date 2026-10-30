"""SearchPane source checks for pages shared with dev."""

import re
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages"
KEY_MATCH = re.compile(r'rowData\[\d+\]\s*\.includes\(\s*"([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)"')


@pytest.mark.parametrize(
    "path",
    sorted(path for path in PAGES.glob("*.js") if path.name not in {"configs.js", "instances.js", "jobs.js", "plugins.js", "services.js"}),
    ids=lambda path: path.name,
)
def test_no_filter_matches_a_translation_key(path):
    offenders = sorted(set(KEY_MATCH.findall(path.read_text(encoding="utf-8"))))

    assert not offenders, f"{path.name} filters on translation keys instead of data-value: {offenders}"
