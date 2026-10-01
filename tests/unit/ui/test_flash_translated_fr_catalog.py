"""End-to-end proof that `flash(translated(key, ...) or "<english>", category)` actually surfaces
a translation when one exists, not just that the right key gets passed (a stub-`translated` test
would prove the latter only).

`translated()` (`app/i18n.py`) does a **local** `from flask_babel import gettext` inside the
function body, re-executed on every call -- so monkeypatching the `flask_babel` module's own
`gettext` attribute is picked up on the next call, with no Babel app/locale/`force_locale()`
ceremony needed at all (`test_i18n_runtime.py` uses that ceremony for real-catalog tests; this
one deliberately does not, per `report-FIX-QA5-I18N.md`'s method note for this exact test). A
fake fr entry lives in this file's own in-memory dict -- `fr.json` is never touched, per the
brief.
"""

import flask_babel
from flask import Flask, get_flashed_messages

from app.i18n import translated
from app.utils import flash

# A key this wave actually added (`routes/jobs.py`), so the mechanism under test is exercised
# with a real production key/fallback pair, not a synthetic one.
KEY = "jobs.flash.no_jobs_selected"
ENGLISH_FALLBACK = "No jobs selected."


def _fake_gettext(catalog):
    def gettext(key, **variables):
        text = catalog.get(key)
        if text is None:
            return key  # real gettext's own miss behavior -- translated() relies on this
        return text % variables if variables else text

    return gettext


def _flash_it(monkeypatch, catalog):
    monkeypatch.setattr(flask_babel, "gettext", _fake_gettext(catalog))

    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/"):
        flash(translated(KEY) or ENGLISH_FALLBACK, "error")
        return get_flashed_messages(with_categories=True)


def test_a_translated_flash_surfaces_the_fr_catalog_text_not_the_english_fallback(monkeypatch):
    messages = _flash_it(monkeypatch, {KEY: "Aucun job sélectionné."})

    assert messages == [("error", "Aucun job sélectionné.")]


def test_a_flash_with_no_matching_catalog_entry_falls_back_to_the_exact_english_text(monkeypatch):
    """The catalog miss case: `gettext()` echoes the key (real gettext's behavior on a miss),
    `translated()` turns that into `None`, and the caller's own `or "<english>"` must produce the
    byte-identical string it flashed before this wave's `translated()` wrapping existed."""
    messages = _flash_it(monkeypatch, {})

    assert messages == [("error", ENGLISH_FALLBACK)]


def test_a_translated_flash_with_variables_interpolates_through_the_fr_text(monkeypatch):
    key = "bans.flash.invalid_ip"
    english = "Invalid IP address: not-an-ip"
    monkeypatch.setattr(flask_babel, "gettext", _fake_gettext({key: "IP refusée : %(ip)s"}))

    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/"):
        flash(translated(key, ip="not-an-ip") or english, "error")
        messages = get_flashed_messages(with_categories=True)

    assert messages == [("error", "IP refusée : not-an-ip")]
