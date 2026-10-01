"""L13: the tab title (and `body[data-page-title]`) must never be the raw last path segment.

Before FIX-QA5-I18N-2, `main.py`'s `before_request` set `current_endpoint =
request.path.split("/")[-1]` and used it, unchanged, as the page title too -- fine for a list page
(`/templates` -> "templates"), but for a detail page (`/templates/<id>`) the last segment is the
id, so the tab read "011d056e 403a ... - BunkerWeb UI".

The fix (`app/i18n.py::resolve_page_title`) keeps `current_endpoint` as the last segment (menu
active-state, the `pro`-overlap check and the column-preferences key all still key off that), but
derives `page_title` separately from the *first* segment -- stable across a blueprint's list and
detail pages alike -- resolved through the existing `navigation.*` catalog (falling back to
`<endpoint>.title` for a page with no sidebar entry, e.g. `/totp`).

Exercises `resolve_page_title` directly rather than the full `before_request` hook: the two-line
title computation is the only thing this item changed, and `before_request` itself needs a real
app, DB and session to reach (see `test_global_settings_save_flash_type.py`'s harness for how heavy
that gets) -- an isolation `test_temp_ui_i18n.py`'s own docstring already argues for.
"""

import json
from pathlib import Path

import flask_babel
import pytest

from app.i18n import resolve_page_title

_EN_JSON = json.loads((Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "locales" / "en.json").read_text())
_FR_JSON = json.loads((Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "locales" / "fr.json").read_text())


def _flatten(catalog: dict, prefix: str = "") -> dict:
    flat = {}
    for key, value in catalog.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten(value, dotted))
        else:
            flat[dotted] = value
    return flat


_FLAT_EN = _flatten(_EN_JSON)
_FLAT_FR = _flatten(_FR_JSON)


@pytest.fixture(autouse=True)
def _real_catalog_as_gettext(monkeypatch):
    """`translated()` does a fresh `from flask_babel import gettext` every call, so patching the
    module attribute (not a local reference) is picked up on the next call -- no Babel app/request
    context needed at all (see `report-FIX-QA5-I18N.md`'s method note for `translated()` tests)."""

    def fake_gettext(key, **variables):
        text = _FLAT_EN.get(key)
        if text is None:
            return key
        return text % variables if variables else text

    monkeypatch.setattr(flask_babel, "gettext", fake_gettext)


def test_a_detail_page_uses_the_list_pages_title_not_the_raw_id():
    current_endpoint, page_title = resolve_page_title("/templates/011d056e-403a-4a1a-8b1a-abcdef123456")

    assert current_endpoint == "011d056e-403a-4a1a-8b1a-abcdef123456"
    assert page_title == "Templates"


def test_the_list_page_resolves_to_the_same_title_as_its_detail_page():
    _, list_title = resolve_page_title("/templates")
    _, detail_title = resolve_page_title("/templates/011d056e-403a-4a1a-8b1a-abcdef123456")

    assert list_title == detail_title == "Templates"


def test_totp_has_no_navigation_entry_but_still_gets_a_real_title():
    assert "totp" not in _EN_JSON.get("navigation", {}), "this test's premise (no sidebar entry) no longer holds"

    _, page_title = resolve_page_title("/totp")

    assert page_title == "Two-Factor"
    assert page_title != "totp"


def test_current_endpoint_keeps_using_the_last_segment_for_the_menu_and_column_prefs():
    """Unchanged by this fix -- `current_endpoint` still drives menu active-state, the `pro`
    overlap check and the column-preferences key, all of which rely on it being the *last*
    segment, not the first."""
    current_endpoint, _ = resolve_page_title("/resource_groups/abc123")

    assert current_endpoint == "abc123"


def test_root_path_yields_no_title_rather_than_raising():
    assert resolve_page_title("/") == ("", None)


@pytest.mark.parametrize(
    ("path", "title"),
    [
        ("/web-cache", "Web Cache"),
        ("/whats-new", "What's new"),
        ("/groups", "Resource groups"),
    ],
)
def test_pages_resolve_localized_titles(path, title):
    assert resolve_page_title(path)[1] == title


def test_pages_resolve_existing_french_catalog_titles(monkeypatch):
    monkeypatch.setattr(flask_babel, "gettext", lambda key, **variables: _FLAT_FR.get(key, key))

    assert resolve_page_title("/web-cache")[1] == "Cache web"
    assert resolve_page_title("/whats-new")[1] == "Nouveautés"
    assert resolve_page_title("/groups")[1] == "Groupes de ressources"  # codespell:ignore
