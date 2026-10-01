"""M36: the boot UI's `starting.html` must actually render, not crash into the 500 fallback.

`src/ui/temp.py` serves an unauthenticated placeholder on 0.0.0.0:7000 while the real UI starts.
`starting.html` extends `base.html`; both call `_()`, which only exists as a Jinja global once
Flask-Babel is wired up (`app.i18n.init_i18n`). `temp.py` never called it, so every request served
during boot hit `jinja2.exceptions.UndefinedError: '_' is undefined` at `starting.html:27`, fell
through to the dependency-free 500 fallback, and logged a traceback -- the designed starting page
never rendered.

`temp.py` is a *separate*, deliberately dependency-light Flask app (no DB, no API client -- that is
the point, it serves while those are not up yet), so this is a real import and a real render rather
than the AST-only checks in `test_temp_ui_error_detail.py` / `test_temp_ui_stop_contract.py`: the
defect is in what gettext and `url_for` actually resolve to at render time, which only a render can
prove. `tests/unit/conftest.py` already puts `src/common/{utils,db,api}` on `sys.path` and this
directory's `conftest.py` puts `src/ui` there too -- the same paths `temp.py`'s own
`/usr/share/bunkerweb/...` fallback stands in for in a built image -- so a plain `import temp` works
here exactly as it does in the container.
"""

import pytest


@pytest.fixture
def temp_app():
    import temp as temp_module

    return temp_module


def test_the_starting_page_renders_without_crashing_into_the_500_fallback(temp_app):
    client = temp_app.app.test_client()

    response = client.get("/pro")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "UndefinedError" not in body
    assert "BunkerWeb UI is starting" in body


def test_the_next_button_gets_a_real_label_not_the_raw_catalog_key(temp_app):
    """The exact call that crashed: `aria-label="{{ _('step.next') }}"` (`starting.html:27`)."""
    client = temp_app.app.test_client()

    body = client.get("/pro").get_data(as_text=True)

    assert 'aria-label="Next"' in body
    assert "step.next" not in body


def test_every_boot_request_shape_renders_the_same_page(temp_app):
    """The 404 handler and the catch-all both render `starting.html`; both must survive."""
    client = temp_app.app.test_client()

    for path in ("/", "/anything-at-all", "/services"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "BunkerWeb UI is starting" in response.get_data(as_text=True), path


def test_the_app_actually_wires_up_gettext(temp_app):
    """The render tests above cannot, on their own, tell a real `init_i18n(app)` call apart from
    this test suite's own `_` stub: `tests/unit/ui/conftest.py` installs `_`/`gettext`/`ngettext`
    into `jinja2.defaults.DEFAULT_NAMESPACE`, which every `Environment` -- including a fresh
    `Flask(__name__, ...)`'s -- copies at construction time, in-process, whether or not `temp.py`
    calls `init_i18n` at all. `flask_babel.Babel(app, ...)` registers itself under
    `app.extensions["babel"]`; only a real call sets that, so this is what actually pins the fix
    rather than the test double."""
    assert "babel" in temp_app.app.extensions, "temp.py's Flask app never wired up Flask-Babel (init_i18n)"
