"""The UI's `overrides.css` as the browser (and every image) ends up with it.

In the tree the sheet is an `@import` index over `css/overrides/<part>.css`; image builds inline
it with `misc/build/merge_css_imports.py`. Tests that assert on rule text read the merged form
through `overrides_css()`, so they do not care where a rule lives.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STATIC = REPO / "src" / "ui" / "app" / "static"
OVERRIDES_INDEX = STATIC / "css" / "overrides.css"

sys.path.insert(0, str(REPO / "misc" / "build"))

from merge_css_imports import merged_text  # noqa: E402


def overrides_css() -> str:
    return merged_text(OVERRIDES_INDEX)
