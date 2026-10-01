"""`translated()` must degrade to `None`, never raise, when Flask-Babel is not registered.

`translated()`'s own docstring documents this contract ("no translation available", not a crash):
every caller uses `translated(key) or "<english fallback>"`, so degrading to `None` falls through
to the English literal the caller already carries. Before FIX-QA5-I18N, the `gettext()` call was
unguarded -- a bare `Flask(__name__)` test harness (no `flask_babel.Babel(app)` call) hit
`KeyError: 'babel'` (confirmed here: `flask_babel.gettext()` reads `current_app.extensions["babel"]`,
which only exists once `Babel(app)` runs), 500ing every route this wave wired through `translated()`
(`report-FIX-QA5-I18N.md`, "A critical fix this pass surfaced").

An app context with NO Flask app at all is a *different*, milder case -- `flask_babel.gettext()`
already catches `RuntimeError` ("working outside of application context") internally and returns
the bare msgid, which `rendered == key` already turns into `None` with no guard needed. The real
regression is an app that exists but was never handed to `flask_babel.Babel(...)` -- exactly the
shape `test_global_settings_propagation.py`/`test_services_unknown_id_flash.py`/
`test_global_settings_save_flash_type.py` build (a bare `Flask(__name__)` around one route, no
`create_app()`). This test isolates the unit that owns the contract instead of relying on those
route tests to catch it as a collateral 500 three layers up.
"""

from flask import Flask

from app.i18n import translated


def _bare_app_context():
    """A Flask app with no `flask_babel.Babel(app)` call -- `current_app.extensions["babel"]` is
    simply absent, which is what raises the `KeyError` this test pins as caught."""
    app = Flask(__name__)
    return app.app_context()


def test_translated_returns_none_inside_an_app_with_no_babel_extension_registered():
    with _bare_app_context():
        assert translated("any.key.at.all") is None


def test_translated_returns_none_even_with_variables_and_no_babel_extension():
    """The `variables`-present branch (`gettext(key, **variables)`) is a different call shape than
    the bare one above -- both must degrade the same way."""
    with _bare_app_context():
        assert translated("any.key.at.all", name="value") is None


def test_translated_returns_none_with_no_flask_app_at_all():
    """No `Flask(__name__)`, no `app_context()` -- `flask_babel.gettext()` catches the resulting
    `RuntimeError` on its own and echoes the msgid, which the `rendered == key` check turns into
    `None`. Pinned so a future flask_babel upgrade that stops doing this is caught here too."""
    assert translated("any.key.at.all") is None
