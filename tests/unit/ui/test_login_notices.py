"""Telling the user something that has to outlive their session.

Two messages reach the login page this way: the CSRF handler's "your submitted form was
discarded" and profile.py's "your password was changed". Both are produced while the session is
being destroyed, and BunkerWeb keeps its flash queue *in* the session -- two of them, in fact
(Flask's ``_flashes`` and ``session["flash_messages"]``, see ``app/utils.flash``). So neither
message can be flashed: it has to travel in the URL as a ``reason``, be looked up in
``LOGIN_NOTICES``, and render as a translated banner.

The tests below pin that premise rather than just the plumbing, because the plumbing looks like
needless indirection to anyone who has not measured the flash being eaten -- and "simplify this
into a flash()" is the regression this file exists to fail on.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages, session
from flask_login import LoginManager

from app.utils import LOGIN_NOTICES

from conftest import english

UI = Path(__file__).resolve().parents[3] / "src" / "ui"


@pytest.fixture(scope="module")
def routes():
    """`login` and `logout` loaded with the container-only dependencies stubbed.

    Same shape as ``test_onboarding_routes.py``. Both are registered under their real names,
    because ``login -> app.models.biscuit -> logout`` is a real edge: loading a second, unstubbed
    copy of either is what this fixture exists to avoid.
    """
    dependencies = ModuleType("app.dependencies")
    for name in ("API_CLIENT", "BW_CONFIG", "BW_INSTANCES_UTILS", "LOGGER"):
        setattr(dependencies, name, Mock())
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    # `login.py:12` imports `BiscuitTokenFactory` / `PrivateKey` from `app.models.biscuit`, which
    # imports `biscuit_auth` at module level. That wheel is deliberately NOT in
    # `tests/unit/requirements.txt`: `biscuit-python` needs a Rust toolchain, and the only lane
    # that genuinely exercises it pins its own copy in `tests/unit/api_app/requirements.txt`.
    # Unstubbed, every test in this file errors with `ModuleNotFoundError: No module named
    # 'biscuit_auth'` on a CI runner and on any developer machine that did not install that lane.
    # Same stub shape as `test_webauthn_routes.py:76-78`; nothing here issues a token.
    biscuit_module = ModuleType("app.models.biscuit")
    biscuit_module.BiscuitTokenFactory = Mock()
    biscuit_module.PrivateKey = Mock()

    loaded = {}
    stubs = {"app.dependencies": dependencies, "app.models.biscuit": biscuit_module, "qrcode": qrcode, "qrcode.main": qrcode_main}
    with patch.dict(sys.modules, stubs):
        for name in ("login", "logout"):
            spec = importlib.util.spec_from_file_location(f"app.routes.{name}", UI / "app" / "routes" / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"app.routes.{name}"] = module
            spec.loader.exec_module(module)
            loaded[name] = module
        yield loaded["login"], loaded["logout"]


@pytest.fixture
def app(routes):
    login, logout = routes
    application = Flask("bw_ui_login_notices_test")
    application.secret_key = "test"
    # logout_page() reads `current_user` and calls `logout_user()`; without a manager and a user
    # loader both raise into its own `except BaseException`, and every assertion below would then
    # be measuring the error path instead of the one that runs in production.
    manager = LoginManager()
    manager.init_app(application)
    manager.user_loader(lambda user_id: None)
    application.register_blueprint(login.login)
    application.register_blueprint(logout.logout)
    return application


def _source(relative):
    return ast.parse((UI / relative).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# The premise: a flash cannot survive the logout these messages are produced by
# --------------------------------------------------------------------------------------
def test_a_message_flashed_before_a_logout_is_destroyed_by_it(app, routes):
    """The measurement behind the whole mechanism.

    Both stores are checked, because sparing only one still renders nothing.
    """
    _, logout = routes

    with app.test_request_context("/logout"):
        session["flash_messages"] = [{"content": "The profile has been successfully updated."}]
        from flask import flash as flask_flash

        flask_flash("The profile has been successfully updated.")
        assert session.get("_flashes"), "precondition: Flask's store holds the message"

        logout.logout_page()

        assert not session.get("_flashes")
        assert not session.get("flash_messages")
        assert get_flashed_messages() == []


# --------------------------------------------------------------------------------------
# The lookup is a whitelist, and its values are message keys
# --------------------------------------------------------------------------------------
def test_every_notice_is_a_key_the_english_catalog_actually_has(routes):
    """A key that is missing translates to itself, so the user is shown
    `login.notice_session_expired`. `english()` reads the real compiled catalog."""
    login, _ = routes

    assert LOGIN_NOTICES, "no notices declared"
    for reason, key in LOGIN_NOTICES.items():
        assert key.startswith("login.notice_"), reason
        assert english(key) != key, f"{key} is not in the catalog"


def test_the_notice_is_a_message_key_and_not_an_english_sentence(routes):
    """The UI translates server-side; a literal here would be English in all 18 locales."""
    login, _ = routes

    for key in LOGIN_NOTICES.values():
        assert " " not in key and key.islower(), key


@pytest.mark.parametrize("reason", ["", "nope", "../../etc/passwd", "<script>alert(1)</script>", "login.notice_session_expired"])
def test_an_unknown_reason_yields_no_notice(routes, reason):
    """Looked up, never echoed -- including the message key itself, which is a value here, not
    an accepted input."""
    login, _ = routes

    assert LOGIN_NOTICES.get(reason) is None


# --------------------------------------------------------------------------------------
# logout forwards a known reason, and only a known one
# --------------------------------------------------------------------------------------
def test_logout_forwards_a_known_reason_to_the_login_page(app, routes):
    _, logout = routes

    with app.test_request_context("/logout?reason=password_changed"):
        response = logout.logout_page()

    assert response.headers["Location"] == "/login?reason=password_changed"


@pytest.mark.parametrize("reason", ["nope", "<script>alert(1)</script>", "//evil.example.com"])
def test_logout_drops_an_unknown_reason_rather_than_reflecting_it(app, routes, reason):
    _, logout = routes

    with app.test_request_context("/logout", query_string={"reason": reason}):
        response = logout.logout_page()

    assert response.headers["Location"] == "/login"


# --------------------------------------------------------------------------------------
# The page renders the translated sentence, not the key
# --------------------------------------------------------------------------------------
def _render(**context):
    """`test_auth_shell.py`'s harness: base.html stubbed to its two blocks, so the render is the
    auth shell and nothing else."""
    from test_auth_shell import _render as render_auth_page

    return render_auth_page("login.html", **context)


def test_the_login_page_renders_the_translated_notice(routes):
    login, _ = routes
    key = LOGIN_NOTICES["session_expired"]

    html = _render(notice=key)

    assert english(key) in html
    assert key not in html, "the raw message key reached the page"


@pytest.mark.parametrize("reason", ["session_expired", "password_changed", "session_timeout"])
def test_the_route_actually_puts_the_notice_into_the_template_context(app, routes, reason):
    """RULE 12: the marker tests above assert the call sites EXIST. This one asserts what the callee
    DOES, end to end -- the reason goes in as a query string, and the translated sentence comes out
    of the real template.

    Written because the guard failed its own audit. A mutant that kept `LOGIN_NOTICES`, kept the
    lookup, kept logout's forwarding and kept the template block, and changed only
    `if notice:` to `if False:` -- so the notice never reached the context -- left **all 2093 UI
    tests green**. Every marker present, banner never rendered. That is @security's mutant D in this
    lane's own work: a presence marker certifying the shape of a fix whose behaviour is neutered.
    """
    login, _ = routes
    captured = {}

    def fake_render(template, **context):
        captured.update(context)
        return _render(**context)

    with app.test_request_context(f"/login?reason={reason}"):
        with patch.object(login, "render_template", fake_render), patch.object(
            login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None)
        ):
            login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
            body = login.login_page()

    html = body[0] if isinstance(body, tuple) else body

    assert captured.get("notice") == LOGIN_NOTICES[reason], f"the route did not pass the notice for reason={reason}"
    assert english(LOGIN_NOTICES[reason]) in html, "the translated sentence never reached the page"


def test_an_unknown_reason_reaches_the_page_as_nothing_at_all(app, routes):
    """The other half: the whitelist has to hold end to end, not only in the dict."""
    login, _ = routes
    captured = {}

    def fake_render(template, **context):
        captured.update(context)
        return _render(**context)

    with app.test_request_context("/login?reason=<script>alert(1)</script>"):
        with patch.object(login, "render_template", fake_render), patch.object(
            login, "current_user", SimpleNamespace(is_authenticated=False, totp_secret=None)
        ):
            login.API_CLIENT.get_admin_user.return_value = {"username": "admin"}
            body = login.login_page()

    html = body[0] if isinstance(body, tuple) else body

    assert "notice" not in captured
    assert "alert(1)" not in html and 'role="alert"' not in html


def test_the_login_page_renders_no_banner_without_a_notice():
    assert 'role="alert"' not in _render()


# --------------------------------------------------------------------------------------
# The two call sites, checked in the source rather than by booting the app
# --------------------------------------------------------------------------------------
def test_the_session_lifetime_logout_says_why_it_signed_the_user_out():
    """The third producer, found by running RULE 11 backwards over this row: `main.py`'s
    `_enforce_session_lifetime` calls `session.clear()` and redirects to /login. Without a reason
    the user is dropped on a blank login page mid-work with no explanation.

    It gets its OWN key, not `session_expired`: that message says the user's change was discarded,
    and this path fires on a GET as often as a POST and usually discards nothing.
    """
    tree = _source("main.py")
    caller = next(node for node in ast.walk(tree) if isinstance(node, ast.If) and "_enforce_session_lifetime" in ast.unparse(node.test))
    body = ast.unparse(caller)

    assert "login.login_page" in body
    assert "reason='session_timeout'" in body, "the lifetime logout redirects to /login with no reason"
    assert "session_expired" not in body, "session_timeout and session_expired are different messages"


def test_the_password_change_hands_its_reason_to_the_logout_it_redirects_to():
    """`profile.py` flashes success, then redirects to /logout -- which eats the flash. Without
    the reason, a password change ends in silence on the login page."""
    calls = [
        node
        for node in ast.walk(_source("app/routes/profile.py"))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "url_for"
        and node.args
        and getattr(node.args[0], "value", None) == "logout.logout_page"
    ]

    assert calls, "profile.py no longer redirects to the logout page"
    for call in calls:
        assert {kw.arg: getattr(kw.value, "value", None) for kw in call.keywords} == {"reason": "password_changed"}


def test_the_csrf_handler_reports_a_discarded_post_and_stays_quiet_on_a_get():
    """A GET that fails CSRF discarded nothing, so it must not claim a change was lost. The
    guard is what makes that true, so it is asserted, not the presence of the string."""
    handler = next(node for node in ast.walk(_source("main.py")) if isinstance(node, ast.FunctionDef) and node.name == "handle_csrf_error")
    guarded = [node for node in ast.walk(handler) if isinstance(node, ast.If) and ast.unparse(node.test) == "request.method == 'POST'"]

    assert len(guarded) == 1, "the session_expired redirect is not behind a single POST guard"
    body = ast.unparse(guarded[0])
    assert "reason='session_expired'" in body
    assert "login.login_page" in body
    # And nowhere else in the handler.
    assert ast.unparse(handler).count("session_expired") == 1


# --------------------------------------------------------------------------------------
# Every producer, not the three that existed the day this was written
# --------------------------------------------------------------------------------------
REASON_TARGETS = ("login.login_page", "logout.logout_page")

# Files whose reason is computed rather than written out. Each entry states WHY the expression
# cannot be resolved statically, and each is a file this guard has read. Adding a file here is a
# deliberate act; the scanner treats anything not listed as a failure, never as an exemption.
UNRESOLVABLE_ALLOWLIST = {
    # `**({"reason": reason} if reason in LOGIN_NOTICES else {})` -- the whitelist IS the check,
    # and `test_logout_drops_an_unknown_reason_rather_than_reflecting_it` exercises it end to end.
    "app/routes/logout.py",
}


def _reason_producers(tree, relative):
    """Every `url_for(<auth endpoint>, reason=...)` in one module, split into what can be read off
    the source and what cannot.

    MUTANT H: the second half is the conservative one -- an expression this cannot resolve is
    reported as unresolved, never quietly skipped. That is the half real data barely reaches (one
    file today) and the half that holds when someone writes a producer nobody anticipated.
    """
    literals, unresolved = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
        if name != "url_for" or not node.args:
            continue
        target = node.args[0]
        if not (isinstance(target, ast.Constant) and target.value in REASON_TARGETS):
            continue
        for keyword in node.keywords:
            if keyword.arg == "reason":
                if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    literals.append(keyword.value.value)
                else:
                    unresolved.append((relative, ast.unparse(keyword.value)))
            elif keyword.arg is None and "reason" in ast.unparse(keyword.value):
                unresolved.append((relative, ast.unparse(keyword.value)))
    return literals, unresolved


def _scan_ui_sources():
    literals, unresolved = [], []
    for path in sorted(UI.rglob("*.py")):
        relative = path.relative_to(UI).as_posix()
        found, unknown = _reason_producers(ast.parse(path.read_text(encoding="utf-8")), relative)
        literals.extend((relative, reason) for reason in found)
        unresolved.extend(unknown)
    return literals, unresolved


def test_every_reason_any_caller_sends_is_a_key_the_login_page_knows():
    """The silent failure this exists to prevent: Jinja's non-strict `Undefined` is falsy, so a
    reason that is not in LOGIN_NOTICES renders as an empty page with no banner and no error. The
    three per-producer tests above each pin one literal; none of them notices a FOURTH producer
    inventing a reason of its own, which is the realistic way this breaks."""
    literals, _ = _scan_ui_sources()

    unknown = [(where, reason) for where, reason in literals if reason not in LOGIN_NOTICES]
    assert not unknown, f"these callers send a reason the login page cannot render: {unknown}"
    # Floor, not equality: growth here is collaboration -- a new producer SHOULD widen this, and
    # the assertion above is what keeps the new one honest.
    assert len(literals) >= 3, f"reason producers disappeared -- only {len(literals)} left: {literals}"


def test_a_reason_this_cannot_read_is_reported_rather_than_skipped():
    """The conservative half, over real sources: exactly the files that compute their reason are
    allowlisted, and the allowlist is not a wildcard."""
    _, unresolved = _scan_ui_sources()

    unlisted = [(where, expr) for where, expr in unresolved if where not in UNRESOLVABLE_ALLOWLIST]
    assert not unlisted, f"a computed reason in a file this guard has not read: {unlisted}"
    # RULE 19: NOT `assert unresolved`. That was here, and it pinned the current shape of
    # logout.py as a requirement -- rewriting it to pass a literal reason is a fine change and
    # would have turned this red for it. The conservative branch is covered by the synthetic case
    # below, which does not care how many computed producers the repo happens to have today.


def test_the_conservative_branch_actually_catches_an_unfamiliar_producer():
    """MUTANT H, stated by @integration: a guard cannot validate a branch real data never reaches,
    and this repo has exactly one computed producer today. Synthetic input is the only way in --
    without this, narrowing `_reason_producers` to literals only would leave every test above green
    while the conservative half was weakened to nothing."""
    synthetic = ast.parse('url_for("login.login_page", **{"reason": whatever_the_caller_decided})\n')

    literals, unresolved = _reason_producers(synthetic, "app/routes/invented.py")

    assert literals == [], "a computed reason was read as a literal"
    assert unresolved and unresolved[0][0] == "app/routes/invented.py", "an unresolvable producer was skipped instead of reported"
    assert unresolved[0][0] not in UNRESOLVABLE_ALLOWLIST, "the synthetic file must not be exempt, or this proves nothing"
