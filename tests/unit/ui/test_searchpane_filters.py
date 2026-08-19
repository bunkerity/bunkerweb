"""DataTables SearchPane filters must key off `data-value`, never a translation key.

A client-side SearchPane filter is a predicate over `rowData[n]` -- the cell's *rendered HTML*.
Twenty-two of them used to test for the cell's `data-i18n="<key>"` attribute. That only ever
worked because the key sat in the markup waiting for a DOM pass to replace it, and it broke the
moment the cell's macro started arriving translated: `components/badge.html` and
`components/status.html` no longer emit the key at all, so every one of those filters silently
matched nothing -- a filter that returns an empty table, with no error anywhere.

`data-value` is the machine-readable half those macros already carried for exactly this. This
test bans the old form outright, because the next template conversion (Lot C) would otherwise
re-break whichever filters still read a key today.
"""

import re
from pathlib import Path

import pytest

PAGES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages"

# `rowData[4].includes("interval.day")` — a dotted lowercase token is a catalog key, not markup.
KEY_MATCH = re.compile(r'rowData\[\d+\]\s*\.includes\(\s*"([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)"')


@pytest.mark.parametrize("path", sorted(PAGES.glob("*.js")), ids=lambda path: path.name)
def test_no_filter_matches_a_translation_key(path):
    offenders = sorted(set(KEY_MATCH.findall(path.read_text(encoding="utf-8"))))

    assert not offenders, f"{path.name} filters on translation keys instead of data-value: {offenders}"


def test_the_filters_that_were_broken_now_read_data_value():
    """Named explicitly so a future refactor cannot make the test above pass by deleting them."""
    expected = {
        "jobs.js": ("day", "hour", "week", "once"),
        "instances.js": ("up", "down", "loading", "static", "container", "pod"),
        "plugins.js": ("pro", "external", "ui", "core"),
        # `type` and `security_mode` left this list when the services table moved to `serverSide`
        # (Perf Lot C): the pane options and their counts come from `/services/fetch`, which
        # filters on the stored value — asserted in `test_services_fetch.py`. Their badges still
        # carry `data-value`, checked below, because the bulk-conversion filter reads it back off
        # `#type-<name>` for a service the user selected on a page they have since left.
        "services.js": ("none",),
        "configs.js": ("global", "none"),
    }
    missing = []
    for name, values in expected.items():
        source = (PAGES / name).read_text(encoding="utf-8")
        missing += [f"{name}:{value}" for value in values if f'data-value=\\"{value}\\"' not in source and f'data-value="{value}"' not in source]

    assert not missing, f"filters no longer select on these values: {missing}"

    services = (PAGES / "services.js").read_text(encoding="utf-8")
    assert 'data-value="${draft ? "draft" : "online"}"' in services
    assert 'data-value="${detect ? "detect" : "block"}"' in services
