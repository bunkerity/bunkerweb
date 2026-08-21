"""Dismissable notices, the "system" theme mode, and hideable Home cards (#3820, items C/D/E).

All three ride the existing ``bw_ui_user_preferences`` key/value table — no model change and no
Alembic revision — so what these tests pin is the *decision* each feature makes, not the storage.
The shapes that matter:

* dismissing is per user and defaults to "show it" (a new account sees the reminder again);
* "system" is a MODE: ``bw_ui_users.theme`` keeps storing a resolved ``light``/``dark``, which is
  what keeps ``THEMES_ENUM`` — and the schema — still;
* an unknown card id is ignored, so a card that leaves the product hides nothing and a card added
  later is visible by default.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from conftest import english
from app.utils import human_readable_number
from flask import Flask, get_flashed_messages, session
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
TEMPLATES = UI / "app" / "templates"
STATIC = UI / "app" / "static"


def _load(module_name, relative, extra_stubs=None):
    """Exec one route module with the container-only dependencies stubbed."""
    dependencies = ModuleType("app.dependencies")
    client = Mock()
    dependencies.API_CLIENT = client
    dependencies.LOGGER = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main}
    stubs.update(extra_stubs or {})
    spec = importlib.util.spec_from_file_location(module_name, UI / relative)
    module = importlib.util.module_from_spec(spec)
    stubs[module_name] = module
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module, client, dependencies


# --------------------------------------------------------------------------------------
# The preference blueprint itself
# --------------------------------------------------------------------------------------


@pytest.fixture
def prefs():
    module, client, dependencies = _load("app.routes.preferences", "app/routes/preferences.py")
    app = Flask("bw_prefs_test")
    app.secret_key = "test"
    # @login_required needs a manager on the app even though every call below drives the view
    # function directly.
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.preferences)
    return SimpleNamespace(module=module, client=client, data=dependencies.DATA, app=app)


def _post(prefs, view, payload):
    """Call the view past @login_required/@cors_required — this drives the body, not the guards
    (which `test_the_routes_are_login_and_cors_protected` pins separately)."""
    with prefs.app.test_request_context("/preferences", method="POST", json=payload):
        with patch.object(prefs.module, "current_user", SimpleNamespace(get_id=lambda: "admin")):
            return view.__wrapped__.__wrapped__()


class TestReads:
    def test_an_absent_blob_means_nothing_is_dismissed(self, prefs):
        prefs.client.get_user_preferences.return_value = {}
        assert prefs.module.dismissed_notices("admin") == {"mfa": False, "newsletter": False}

    def test_a_stored_blob_is_reported_as_booleans(self, prefs):
        prefs.client.get_user_preferences.return_value = {"mfa": True}
        assert prefs.module.dismissed_notices("admin") == {"mfa": True, "newsletter": False}

    def test_an_unreachable_api_shows_the_notice_rather_than_breaking_the_page(self, prefs):
        prefs.client.get_user_preferences.side_effect = RuntimeError("down")
        assert prefs.module.dismissed_notices("admin") == {"mfa": False, "newsletter": False}

    def test_an_unknown_card_id_is_ignored(self, prefs):
        """A card removed from the product must not keep hiding something, and a crafted id
        must not be able to blank a page."""
        prefs.client.get_user_preferences.return_value = {"ids": ["home-card-news", "home-card-that-left"]}
        assert prefs.module.hidden_home_cards("admin") == ["home-card-news"]

    def test_a_card_added_later_is_visible_by_default(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": ["home-card-news"]}
        hidden = prefs.module.hidden_home_cards("admin")
        assert set(prefs.module.HIDEABLE_HOME_CARDS) - set(hidden), "everything hidden by default"
        assert "home-card-timeseries" not in hidden

    def test_a_corrupt_hidden_blob_hides_nothing(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": "home-card-news"}
        assert prefs.module.hidden_home_cards("admin") == []

    @pytest.mark.parametrize("mode", ["light", "dark", "system"])
    def test_the_theme_mode_round_trips(self, prefs, mode):
        prefs.client.get_user_preferences.return_value = {"mode": mode}
        assert prefs.module.theme_mode("admin") == mode

    @pytest.mark.parametrize("stored", [{}, {"mode": "solarized"}, {"mode": None}])
    def test_an_unusable_theme_mode_falls_back_to_the_column(self, prefs, stored):
        prefs.client.get_user_preferences.return_value = stored
        assert prefs.module.theme_mode("admin") is None


class TestNoticeWrites:
    def test_dismissing_writes_the_flag_for_the_current_user(self, prefs):
        prefs.client.get_user_preferences.return_value = {}
        response = _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa"})

        assert response.get_json() == {"status": "success", "saved": True, "state": {"mfa": True}}
        prefs.client.update_user_preferences.assert_called_once_with("admin", "dismissed_notices", {"mfa": True})

    def test_dismissing_one_notice_leaves_the_other_alone(self, prefs):
        prefs.client.get_user_preferences.return_value = {"newsletter": True}
        _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa"})

        assert prefs.client.update_user_preferences.call_args.args[2] == {"newsletter": True, "mfa": True}

    def test_a_notice_can_be_un_dismissed(self, prefs):
        prefs.client.get_user_preferences.return_value = {"mfa": True}
        _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa", "dismissed": False})

        assert prefs.client.update_user_preferences.call_args.args[2] == {"mfa": False}

    @pytest.mark.parametrize("notice", ["", "nope", "../../etc/passwd", None])
    def test_an_unknown_notice_is_rejected(self, prefs, notice):
        response, status = _post(prefs, prefs.module.dismiss_notice, {"notice": notice})

        assert status == 400
        prefs.client.update_user_preferences.assert_not_called()

    def test_a_read_only_database_says_so_instead_of_pretending(self, prefs):
        prefs.client.get_user_preferences.return_value = {}
        prefs.data["READONLY_MODE"] = True

        response = _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa"})

        assert response.get_json()["saved"] is False
        prefs.client.update_user_preferences.assert_not_called()

    def test_an_unexpected_write_failure_is_not_swallowed(self, prefs):
        """Only the two API exceptions are handled; anything else must surface as a 500 rather
        than be reported to the user as a saved preference."""
        prefs.client.get_user_preferences.return_value = {}
        prefs.client.update_user_preferences.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa"})

    def test_an_api_error_on_write_is_a_502(self, prefs):
        prefs.client.get_user_preferences.return_value = {}
        prefs.client.update_user_preferences.side_effect = prefs.module.ApiUnavailableError("down")

        _response, status = _post(prefs, prefs.module.dismiss_notice, {"notice": "mfa"})

        assert status == 502

    def test_the_session_cache_is_invalidated_so_the_change_shows_immediately(self, prefs):
        prefs.client.get_user_preferences.return_value = {}
        with prefs.app.test_request_context("/preferences", method="POST", json={"notice": "mfa"}):
            session[prefs.module.SESSION_KEYS["dismissed_notices"]] = {"mfa": False}
            with patch.object(prefs.module, "current_user", SimpleNamespace(get_id=lambda: "admin")):
                prefs.module.dismiss_notice.__wrapped__.__wrapped__()
            assert prefs.module.SESSION_KEYS["dismissed_notices"] not in session


class TestCardWrites:
    def test_hiding_a_card_adds_it_to_the_stored_list(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": []}
        _post(prefs, prefs.module.set_home_cards, {"card": "home-card-news"})

        prefs.client.update_user_preferences.assert_called_once_with("admin", "hidden_home_cards", {"ids": ["home-card-news"]})

    def test_hiding_is_idempotent(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": ["home-card-news"]}
        _post(prefs, prefs.module.set_home_cards, {"card": "home-card-news"})

        assert prefs.client.update_user_preferences.call_args.args[2] == {"ids": ["home-card-news"]}

    def test_restoring_clears_every_hidden_card(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": ["home-card-news", "home-card-timeseries"]}
        _post(prefs, prefs.module.set_home_cards, {"restore": True})

        assert prefs.client.update_user_preferences.call_args.args[2] == {"ids": []}

    def test_one_card_can_be_brought_back_on_its_own(self, prefs):
        prefs.client.get_user_preferences.return_value = {"ids": ["home-card-news", "home-card-timeseries"]}
        _post(prefs, prefs.module.set_home_cards, {"card": "home-card-news", "hidden": False})

        assert prefs.client.update_user_preferences.call_args.args[2] == {"ids": ["home-card-timeseries"]}

    @pytest.mark.parametrize("card", ["", "nope", None, "home-card-that-left"])
    def test_an_unknown_card_is_rejected(self, prefs, card):
        prefs.client.get_user_preferences.return_value = {"ids": []}
        _response, status = _post(prefs, prefs.module.set_home_cards, {"card": card})

        assert status == 400
        prefs.client.update_user_preferences.assert_not_called()

    def test_the_routes_are_login_and_cors_protected(self):
        """Unauthenticated writes to another user's preferences would be the whole bug."""
        source = (UI / "app" / "routes" / "preferences.py").read_text(encoding="utf-8")
        for view in ("def dismiss_notice(", "def set_home_cards("):
            block = source[: source.index(view)]
            assert block.rsplit("@preferences.route", 1)[-1].count("@login_required") == 1, view
            assert block.rsplit("@preferences.route", 1)[-1].count("@cors_required") == 1, view

    def test_the_hideable_set_is_not_empty(self, prefs):
        # RULE 13: a list-driven guard that silently empties would accept every id or none.
        assert len(prefs.module.HIDEABLE_HOME_CARDS) >= 5


# --------------------------------------------------------------------------------------
# C — the 2FA reminder at login
# --------------------------------------------------------------------------------------


@pytest.fixture
def login_app():
    biscuit_module = ModuleType("app.models.biscuit")
    biscuit_module.BiscuitTokenFactory = Mock()
    biscuit_module.PrivateKey = Mock()
    module, client, _dependencies = _load("app.routes.login", "app/routes/login.py", {"app.models.biscuit": biscuit_module})

    app = Flask("bw_login_notice_test")
    app.secret_key = "test"
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.login)
    app.add_url_rule("/loading", "loading", lambda: "")
    app.add_url_rule("/profile", "profile.profile_page", lambda: "")
    app.add_url_rule("/home", "home.home_page", lambda: "")
    return SimpleNamespace(module=module, client=client, app=app)


def _login(login_app, dismissed):
    """Drive a successful password login for a user with no TOTP and no passkey."""
    from bcrypt import gensalt, hashpw

    password = hashpw(b"P@ssw0rd", gensalt(rounds=4)).decode("utf-8")
    login_app.client.get_admin_user.return_value = {"username": "admin"}
    login_app.client.get_user_for_auth.return_value = {
        "username": "admin",
        "password": password,
        "method": "manual",
        "totp_secret": None,
        "webauthn_credentials_count": 0,
        "roles": [],
        "theme": "light",
        "language": "en",
    }
    # `translated()` needs a live Flask-Babel; the label itself is asserted from the catalog
    # separately, so resolve it through the same compiled catalog the harness uses.
    with patch.object(login_app.module, "_establish_session", lambda *a, **k: True), patch.object(
        login_app.module, "dismissed_notices", lambda username: {"mfa": dismissed}
    ), patch.object(login_app.module, "translated", english):
        with login_app.app.test_request_context("/login", method="POST", data={"username": "admin", "password": "P@ssw0rd"}):
            login_app.module.login_page()
            return [message for _category, message in get_flashed_messages(with_categories=True)]


class TestMfaReminder:
    def test_it_is_shown_to_a_user_who_has_not_dismissed_it(self, login_app):
        messages = _login(login_app, dismissed=False)

        assert any("two-factor authentication" in message for message in messages), messages

    def test_it_is_not_shown_again_once_dismissed(self, login_app):
        """The whole feature. `if not dismissed(...)` -> `if True:` makes this go red."""
        messages = _login(login_app, dismissed=True)

        assert not any("two-factor authentication" in message for message in messages), messages

    def test_the_reminder_carries_its_own_dismiss_control(self, login_app):
        messages = _login(login_app, dismissed=False)
        reminder = next(message for message in messages if "two-factor authentication" in message)

        assert 'data-dismiss-notice="mfa"' in reminder
        # ...and still points at the place where 2FA is actually enabled: dismissing must not
        # take the security signal away, only stop it repeating.
        assert "/profile" in reminder

    def test_the_dismiss_label_comes_from_the_catalog(self):
        assert english("notice.dismiss_mfa") != "notice.dismiss_mfa"


# --------------------------------------------------------------------------------------
# C — the newsletter block
# --------------------------------------------------------------------------------------


def _render(template, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "dashboard.html": "{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}",
                        "base.html": "{% block content %}{% endblock %}",
                    }
                ),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals["url_for"] = lambda endpoint, **kwargs: f"/{kwargs.get('filename', endpoint)}"
    env.globals["_"] = english
    env.globals["csrf_token"] = lambda: "token"
    env.globals["human_readable_number"] = human_readable_number
    return env.get_template(template).render(**context)


class TestNewsletterNotice:
    def test_the_signup_block_is_rendered_by_default(self):
        html = _render("sidebar-news.html", theme="light", dismissed_notices={}, script_nonce="n")

        assert "newsletter-signup" in html

    def test_it_disappears_once_the_user_says_they_already_subscribed(self):
        html = _render("sidebar-news.html", theme="light", dismissed_notices={"newsletter": True}, script_nonce="n")

        assert "newsletter-signup" not in html

    def test_it_offers_the_control_that_dismisses_it(self):
        html = _render("sidebar-news.html", theme="light", dismissed_notices={}, script_nonce="n")

        assert 'data-dismiss-notice="newsletter"' in html
        assert english("notice.already_subscribed") in html


class TestNewsletterNoticeInTheOtherDrawer:
    """The signup block is duplicated verbatim in the notifications drawer. Gating only the news
    one leaves the user still being asked on every page — found in a browser, not by a test."""

    @pytest.mark.parametrize("template", ["sidebar-news.html", "sidebar-notifications.html"])
    def test_both_drawers_honour_the_same_preference(self, template):
        assert "newsletter-signup" in _render(template, theme="light", dismissed_notices={}, script_nonce="n")
        assert "newsletter-signup" not in _render(template, theme="light", dismissed_notices={"newsletter": True}, script_nonce="n")

    @pytest.mark.parametrize("template", ["sidebar-news.html", "sidebar-notifications.html"])
    def test_both_drawers_offer_the_dismiss_control(self, template):
        assert 'data-dismiss-notice="newsletter"' in _render(template, theme="light", dismissed_notices={}, script_nonce="n")

    def test_no_third_copy_of_the_block_slipped_past_the_gate(self):
        """RULE 13-style floor on the sweep itself: if a new copy appears, this fails rather
        than the feature silently half-working again."""
        copies = [path for path in TEMPLATES.rglob("*.html") if 'class="newsletter-signup' in path.read_text(encoding="utf-8")]
        assert len(copies) >= 2, copies
        ungated = [path.name for path in copies if "dismissed_notices" not in path.read_text(encoding="utf-8")]
        # components/drawer.html carries an unused slot: every caller passes newsletter=false,
        # and a macro imported without context could not read the preference anyway.
        assert ungated == ["drawer.html"], ungated


class TestDismissScript:
    def test_the_handler_is_loaded_on_every_page(self):
        assert "js/components/ui-preferences.js" in (TEMPLATES / "base.html").read_text(encoding="utf-8")

    def test_it_exists_and_posts_to_the_two_preference_routes(self):
        script = (STATIC / "js" / "components" / "ui-preferences.js").read_text(encoding="utf-8")

        assert "/preferences/notice" in script
        assert "/preferences/home-cards" in script
        # Delegated, because the MFA reminder is a toast injected after load.
        assert 'document.addEventListener("click"' in script

    def test_it_does_not_reload_when_the_write_was_refused(self):
        """A read-only database answers `saved: false`; reloading would put the notice straight
        back and read as a dead button."""
        script = (STATIC / "js" / "components" / "ui-preferences.js").read_text(encoding="utf-8")

        assert "data.saved" in script


# --------------------------------------------------------------------------------------
# D — the "system" theme mode
# --------------------------------------------------------------------------------------


def _set_theme():
    """Exec main.py's `set_theme` alone, against stubs — importing main.py boots the app."""
    source = (UI / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="main.py")
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "set_theme")
    node.decorator_list = []
    namespace = {}
    exec(compile(ast.Module([node], type_ignores=[]), "main.py", "exec"), namespace)
    return namespace["set_theme"], namespace


class TestSetTheme:
    def _call(self, form, readonly=False):
        view, namespace = _set_theme()
        client, responses, popped = Mock(), [], []

        class _Response:
            def __init__(self, status=200, response=None, content_type=None):
                self.status = status
                self.response = response
                responses.append(self)

        namespace.update(
            DATA={"READONLY_MODE": readonly},
            request=SimpleNamespace(form=form),
            current_user=SimpleNamespace(get_id=lambda: "admin"),
            API_CLIENT=client,
            LOGGER=Mock(),
            Response=_Response,
            dumps=lambda payload: payload,
            THEME_MODE_KEY="theme_mode",
            PREFERENCE_SESSION_KEYS={"theme_mode": "bw_theme_mode"},
            session=SimpleNamespace(pop=lambda key, default=None: popped.append(key)),
        )
        return view(), client, popped

    def test_an_explicit_choice_stores_both_the_value_and_the_mode(self):
        response, client, _popped = self._call({"theme": "dark", "mode": "dark"})

        assert response.status == 200
        client.update_user.assert_called_once_with("admin", theme="dark")
        client.update_user_preferences.assert_called_once_with("admin", "theme_mode", {"mode": "dark"})

    def test_system_mode_still_stores_a_RESOLVED_value_in_the_column(self):
        """This is what keeps THEMES_ENUM — and therefore the schema — still."""
        response, client, _popped = self._call({"theme": "dark", "mode": "system"})

        assert response.status == 200
        client.update_user.assert_called_once_with("admin", theme="dark")
        client.update_user_preferences.assert_called_once_with("admin", "theme_mode", {"mode": "system"})

    def test_the_column_whitelist_did_not_grow(self):
        response, client, _popped = self._call({"theme": "system", "mode": "system"})

        assert response.status == 400
        client.update_user.assert_not_called()

    def test_an_unknown_mode_is_rejected(self):
        response, client, _popped = self._call({"theme": "dark", "mode": "solarized"})

        assert response.status == 400
        client.update_user.assert_not_called()

    def test_an_absent_mode_means_the_explicit_choice(self):
        _response, client, _popped = self._call({"theme": "light"})

        client.update_user_preferences.assert_called_once_with("admin", "theme_mode", {"mode": "light"})

    def test_a_read_only_database_writes_nothing(self):
        response, client, _popped = self._call({"theme": "dark", "mode": "dark"}, readonly=True)

        assert response.status == 423
        client.update_user_preferences.assert_not_called()

    def test_the_session_cache_is_invalidated(self):
        _response, _client, popped = self._call({"theme": "dark", "mode": "system"})

        assert "bw_theme_mode" in popped


class TestThemeSurfaces:
    def test_the_profile_select_offers_system(self):
        source = (TEMPLATES / "profile.html").read_text(encoding="utf-8")

        assert '"value": "system"' in source
        assert english("theme.system") != "theme.system"

    def test_the_profile_select_shows_the_mode_not_the_resolved_value(self):
        """Rendering the resolved value would show "Light" to a user whose mode is System."""
        source = (TEMPLATES / "profile.html").read_text(encoding="utf-8")

        assert "value=theme_mode" in source

    def test_the_pre_paint_block_also_runs_for_a_logged_in_system_user(self):
        """The column holds the value resolved at the LAST write; the OS may have flipped since,
        so an authenticated system-mode page has to resolve before first paint too."""
        source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        assert "theme_mode == 'system'" in source

    def test_the_pre_paint_block_ignores_a_stale_stored_choice_in_system_mode(self):
        source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        assert 'if (serverMode === "system") return null;' in source

    def test_the_browser_resolves_and_keeps_following_the_os(self):
        script = (STATIC / "js" / "utils.js").read_text(encoding="utf-8")

        assert 'window.matchMedia("(prefers-color-scheme: dark)")' in script
        assert 'themeMediaQuery.addEventListener("change"' in script
        # ...and stops following it the moment the user picks a side.
        assert 'if (window.__bwThemeMode !== "system") return;' in script

    def test_the_select_keeps_showing_the_mode_after_the_theme_is_applied(self):
        """Caught in a browser, invisible to a render test: the profile select also carries
        `name="theme"`, so the blanket `$("[name='theme']").val(theme)` wrote the RESOLVED value
        into it and "System" snapped back to "Light" one tick after being chosen."""
        script = (STATIC / "js" / "utils.js").read_text(encoding="utf-8")

        assert '$("[name=\'theme\']").not("#theme-toggle").val(theme);' in script
        assert "$themeSelector.val(mode);" in script
        # The old form would reintroduce the bug verbatim.
        assert "$(\"[name='theme']\").val(theme);" not in script

    def test_the_browser_persists_the_mode_alongside_the_resolved_value(self):
        script = (STATIC / "js" / "utils.js").read_text(encoding="utf-8")

        assert 'data.append("mode", mode || theme);' in script
        assert 'localStorage.setItem("theme", mode === "system" ? "system" : theme);' in script


class TestProfileThemeBranch:
    """`routes/profile.py` cannot be exec'd in this venv (`user_agents` is a container-only
    wheel, deliberately absent from tests/unit/requirements.txt — RULE 15: this is not a skipped
    behavioural test, the behaviour is asserted on the parsed source instead), so the theme
    branch is read off its AST."""

    @staticmethod
    def _branch():
        tree = ast.parse((UI / "app" / "routes" / "profile.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Subscript):
                source = ast.unparse(node)
                if source.startswith("request.form['theme']") and "not in" in source:
                    return source
        raise AssertionError("the profile theme validation disappeared")

    def test_the_form_accepts_the_system_mode(self):
        assert "system" in self._branch()

    def test_it_still_accepts_exactly_the_three_modes(self):
        assert self._branch() == "request.form['theme'] not in ('dark', 'light', 'system')"

    def test_system_never_reaches_the_theme_column(self):
        """Writing "system" into bw_ui_users.theme is the migration this design exists to avoid."""
        source = (UI / "app" / "routes" / "profile.py").read_text(encoding="utf-8")
        start = source.index('elif "theme" in request.form:')
        end = source.index('    else:\n        return handle_error("No fields were updated.')
        block = source[start:end]
        assert 'if theme_mode == "system":' in block
        assert block.index('if theme_mode == "system":') < block.index('user_data["theme"] = theme_mode')


# --------------------------------------------------------------------------------------
# E — hideable Home cards
# --------------------------------------------------------------------------------------


class TestHiddenCardsDoNotBreakTheDashboardScript:
    """`home.js` is one flat `$(async function () {...})`: an exception anywhere at its top
    level takes every chart after it, and the surviving cards keep their spinners forever.
    Hiding a card deletes its `#*-data` island, and `JSON.parse($("#missing").text())` is
    `JSON.parse("")` -> SyntaxError. This is the half a server-side render test cannot see:
    the page is perfectly valid HTML, the damage is entirely in the browser.
    """

    HOME_JS = STATIC / "js" / "pages" / "home.js"

    def test_no_island_is_parsed_without_a_guard(self):
        script = self.HOME_JS.read_text(encoding="utf-8")

        code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))

        assert "JSON.parse($(" not in code, "an unguarded island read is back"
        assert "function readIsland(" in script

    def test_the_helper_survives_an_absent_and_an_empty_island(self):
        """Absent (card hidden) and empty (metrics not in yet) are both normal states."""
        script = self.HOME_JS.read_text(encoding="utf-8")
        start = script.index("function readIsland(")
        end = script.index("const fmtCompact")
        body = script[start:end]

        assert "if (!el) return fallback;" in body
        assert "if (!raw) return fallback;" in body
        assert "catch" in body  # malformed JSON must not throw either

    def test_every_island_read_goes_through_the_helper(self):
        script = self.HOME_JS.read_text(encoding="utf-8")

        for island in ("requests-map-data", "requests-blocking-data", "requests-stats-data", "requests-ips-data"):
            assert f'readIsland("{island}"' in script, island

    def test_leaflet_is_not_started_without_its_mount(self):
        """`L.map()` on a missing element throws before any chart below it gets a chance."""
        script = self.HOME_JS.read_text(encoding="utf-8")

        assert 'const mapMount = document.getElementById("requests-map");' in script
        assert "if (map) loadGeoData();" in script
        assert "if (map) legend.addTo(map);" in script

    @pytest.mark.parametrize(
        ("function", "mount"),
        [("renderStatsChart", "#requests-stats"), ("renderBlockingStatus", "#requests-blocking")],
    )
    def test_each_chart_renderer_returns_early_without_its_mount(self, function, mount):
        """Guarded in the renderer, not at the call site: `updateChartsWithTranslations`
        calls both again on every theme/language change."""
        script = self.HOME_JS.read_text(encoding="utf-8")
        start = script.index(f"function {function}(")
        end = start + 400
        body = script[start:end]

        assert f'if (!document.querySelector("{mount}")) return;' in body

    @pytest.mark.parametrize(
        "hidden",
        [
            "home-card-timeseries",
            "home-card-status-codes",
            "home-card-top-reasons",
            "home-card-world-map",
            "home-card-blocking",
            "home-card-news",
        ],
    )
    def test_hiding_one_card_leaves_every_other_mount_in_place(self, hidden):
        """The server half of the same guarantee: hiding one card must not remove another
        card's mount or data island."""
        full = _home()
        partial = _home(hidden_home_cards=[hidden])
        mounts = {
            "home-card-timeseries": ["home-timeseries-chart"],
            "home-card-status-codes": ["requests-stats", "requests-stats-data"],
            "home-card-top-reasons": ["home-top-reasons-body"],
            "home-card-world-map": ["requests-map", "requests-map-data"],
            "home-card-blocking": ["requests-blocking", "requests-blocking-data"],
        }
        # News mounts nothing and carries no data island -- it is the one card of six whose
        # markup a script never touches, which is exactly why hiding it proved nothing.
        for card, ids in mounts.items():
            for element_id in ids:
                if card == hidden:
                    assert f'id="{element_id}"' not in partial, f"{element_id} survived hiding {card}"
                else:
                    assert f'id="{element_id}"' in full and f'id="{element_id}"' in partial, f"{element_id} lost when hiding {hidden}"
        if hidden == "home-card-news":
            assert "news-carousel" not in partial
        else:
            assert "news-carousel" in partial

    def test_the_ip_donut_is_never_hidden_so_its_island_always_ships(self):
        """`#requests-ips` is not in the hideable set; if that ever changes, its renderer needs
        the same early return the other two got."""
        for hidden in ("home-card-world-map", "home-card-blocking", "home-card-status-codes"):
            assert 'id="requests-ips-data"' in _home(hidden_home_cards=[hidden])


class TestPreferenceRequestsSurviveASubpathDeployment:
    """The documented production topology mounts the UI on a subpath behind BunkerWeb
    (`REVERSE_PROXY_URL` + `X-Forwarded-Prefix` -> `SCRIPT_NAME`). A root-absolute
    `fetch("/preferences/...")` leaves the app there, and this file used to swallow the
    failure whole -- hide, restore and both dismissals would silently do nothing."""

    SCRIPT = STATIC / "js" / "components" / "ui-preferences.js"

    def test_no_root_absolute_preference_url_is_left(self):
        script = self.SCRIPT.read_text(encoding="utf-8")

        assert '"/preferences' in script  # the paths are still there...
        assert 'fetch("/preferences' not in script  # ...but never fetched root-absolute
        assert "fetch(`${appRoot}${path}`" in script

    def test_the_base_comes_from_the_page_rather_than_being_assumed(self):
        script = self.SCRIPT.read_text(encoding="utf-8")

        assert 'document.body?.getAttribute("data-app-root")' in script
        assert '|| ""' in script  # empty at the domain root -- unchanged behaviour there

    def test_base_html_publishes_the_mount_point(self):
        source = (TEMPLATES / "base.html").read_text(encoding="utf-8")

        assert "data-app-root=\"{{ request.script_root if request else '' }}\"" in source

    def test_a_failed_request_is_logged_rather_than_swallowed(self):
        script = self.SCRIPT.read_text(encoding="utf-8")
        start = script.index("function post(")
        end = script.index("document.addEventListener")
        body = script[start:end]

        assert body.count("console.warn") >= 2  # the !ok branch and the network catch


class TestSystemModeSurvivesAStaleColumn:
    """The state the first browser pass could not reach: mode is `system` and
    `bw_ui_users.theme` disagrees with the current OS resolution (the OS flipped since the
    last write). Passing the RESOLVED value into `applyTheme` there stamps `dark`/`light` onto
    `window.__bwThemeMode`, which kills the media-query listener for the page and writes the
    resolved value into the profile select -- the "System snapped back to Light" defect again,
    and self-perpetuating, because a mid-session repaint does not persist."""

    SCRIPT = STATIC / "js" / "utils.js"

    def test_the_load_reconcile_passes_the_mode_not_the_resolved_value(self):
        script = self.SCRIPT.read_text(encoding="utf-8")

        assert 'applyTheme(serverMode === "system" ? "system" : desiredTheme);' in script
        # The old form would reintroduce it verbatim.
        assert "\n    applyTheme(desiredTheme);\n" not in script

    def test_the_listener_gate_still_reads_the_mode(self):
        """The fix is only worth anything because this gate exists."""
        script = self.SCRIPT.read_text(encoding="utf-8")

        assert 'if (window.__bwThemeMode !== "system") return;' in script


class TestThePrePaintListenerStandsDownForAnExplicitChoice:
    """`base.html`'s anti-FOUC block keeps its own media-query listener, and on a system-mode
    page its `readStored()` returns null *unconditionally* -- so after the user picks Light or
    Dark from the navbar toggle (present on every page, no reload involved), utils.js's listener
    goes quiet but this one kept repainting to the OS theme on the next flip, silently reverting
    the choice until a reload.

    The gate is keyed on the closure's `serverMode`, NOT on the global alone: on an anonymous
    page `__bwThemeMode` holds light|dark by design, and a blanket check would kill OS tracking
    there."""

    TEMPLATE = TEMPLATES / "base.html"

    def test_the_listener_defers_to_an_explicit_choice_made_without_a_reload(self):
        source = self.TEMPLATE.read_text(encoding="utf-8")

        assert 'if (serverMode === "system" && window.__bwThemeMode !== "system") return;' in source

    def test_the_ungated_two_line_body_is_gone(self):
        """The old body, verbatim -- reintroducing it must not read as still-fixed."""
        source = self.TEMPLATE.read_text(encoding="utf-8")
        old_body = """                mq.addEventListener("change", function () {
                  if (readStored()) return; // explicit choice wins
                  apply(osTheme());
                });"""

        assert old_body not in source

    def test_anonymous_pages_keep_following_the_os(self):
        """The gate must not fire when the page was not rendered in system mode; a blanket
        `window.__bwThemeMode !== "system"` would stop anonymous OS tracking dead."""
        source = self.TEMPLATE.read_text(encoding="utf-8")

        assert 'window.__bwThemeMode !== "system") return;\n                  if (readStored())' in source
        assert 'if (window.__bwThemeMode !== "system") return;\n                  if (readStored())' not in source

    def test_the_explicit_choice_check_survives(self):
        """Both guards matter: the new one covers the no-reload case, `readStored()` the rest."""
        source = self.TEMPLATE.read_text(encoding="utf-8")

        assert "if (readStored()) return; // explicit choice wins" in source


class TestAReadOnlyRefusalIsVisible:
    """A read-only database answers `saved: false`; the click then does nothing on purpose. With
    no console trace that is indistinguishable from the silent-failure bug this file shipped
    once already."""

    SCRIPT = STATIC / "js" / "components" / "ui-preferences.js"

    def test_the_refusal_is_logged_with_its_reason(self):
        """Asserted on the branch body rather than one literal line: prettier wraps a long
        `console.warn(...)` across three lines, and a whole-line match would go red on a
        reformat while the behaviour is untouched."""
        script = self.SCRIPT.read_text(encoding="utf-8")
        start = script.index('if (data.status === "success" && !data.saved) {')
        end = script.index('if (data.status === "success" && data.saved) done();')
        branch = script[start:end]

        assert "console.warn(" in branch
        assert "Preference not saved:" in branch
        assert "data.message" in branch

    def test_a_refused_write_still_does_not_reload(self):
        """Reloading would put the notice straight back -- honest, but it reads as a dead click."""
        script = self.SCRIPT.read_text(encoding="utf-8")

        assert 'if (data.status === "success" && data.saved) done();' in script


class TestCardMacro:
    def _card(self, **kwargs):
        env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
        env.globals["_"] = english
        template = env.from_string(
            "{% from 'components/card.html' import card %}{% call card(**kwargs) %}body{% endcall %}",
        )
        return template.render(kwargs=kwargs)

    def test_a_hideable_card_renders_its_control(self):
        html = self._card(id="home-card-news", title="News", hideable=True)

        assert 'data-hide-card="home-card-news"' in html
        assert english("dashboard.card.hide") in html

    def test_an_ordinary_card_is_unchanged(self):
        assert "data-hide-card" not in self._card(id="home-card-news", title="News")

    def test_a_card_with_no_id_gets_no_control(self):
        """The control posts the id; without one it would post nothing and 400."""
        assert "data-hide-card" not in self._card(title="News", hideable=True)

    def test_the_header_right_slot_still_works_next_to_it(self):
        html = self._card(id="home-card-news", title="News", hideable=True, header_right="<span>slot</span>")

        assert "<span>slot</span>" in html and "data-hide-card" in html


def _home(**overrides):
    context = dict(
        columns_preferences_defaults={"reports": {}},
        columns_preferences={},
        is_readonly=True,
        user_readonly=False,
        theme="light",
        theme_mode="light",
        script_nonce="nonce",
        style_nonce="nonce",
        current_user=SimpleNamespace(get_id=lambda: "admin"),
        is_pro_version=False,
        pro_diamond_url="/diamond.png",
        memory_info={"total_gb": 8.0, "used_gb": 4.0, "used_percent": 50.0, "available_gb": 4.0, "memory_state": "good"},
        instances=[],
        services=[],
        plugins={},
        request_errors={},
        request_countries={},
        request_ips={},
        blocked_unique_ips=0,
        time_buckets={},
        home_stats_days=7,
        is_initialized=False,
        first_config_saved=False,
        jobs_count=0,
        bans_active=0,
        top_reasons=[],
        hidden_home_cards=[],
    )
    context.update(overrides)
    return _render("home.html", **context)


class TestHomeCards:
    def test_every_hideable_card_is_rendered_by_default(self):
        html = _home()

        for card in ("home-card-timeseries", "home-card-status-codes", "home-card-top-reasons", "home-card-world-map", "home-card-blocking", "home-card-news"):
            assert f'data-hide-card="{card}"' in html, card

    @pytest.mark.parametrize(
        ("card", "marker"),
        [
            ("home-card-news", "news-carousel"),
            ("home-card-timeseries", "home-timeseries-chart"),
            ("home-card-world-map", "requests-map-async"),
            ("home-card-blocking", "requests-blocking-async"),
            ("home-card-status-codes", "requests-stats"),
            ("home-card-top-reasons", "requests-reasons-async"),
        ],
    )
    def test_a_hidden_card_is_not_rendered_at_all(self, card, marker):
        """Not hidden with CSS: the markup is never built, so the page is smaller too."""
        assert marker in _home()
        assert marker not in _home(hidden_home_cards=[card])

    def test_hiding_one_card_leaves_the_others(self):
        html = _home(hidden_home_cards=["home-card-news"])

        assert "news-carousel" not in html
        assert "home-timeseries-chart" in html

    def test_the_restore_control_only_appears_when_something_is_hidden(self):
        assert "data-restore-cards" not in _home()
        assert "data-restore-cards" in _home(hidden_home_cards=["home-card-news"])

    def test_the_restore_label_is_translated(self):
        assert english("dashboard.card.restore") in _home(hidden_home_cards=["home-card-news"])

    def test_the_card_ids_the_page_uses_are_the_ids_the_route_accepts(self, prefs):
        """A rename on one side only leaves a control that 400s, or a preference nothing reads."""
        html = _home()
        rendered = {value.split('"')[0] for value in html.split('data-hide-card="')[1:]}

        assert rendered == set(prefs.module.HIDEABLE_HOME_CARDS)
