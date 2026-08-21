"""Two-factor enrolment has to survive the page being rendered again.

`/profile` used to mint a new TOTP secret on **every** GET. Any second render — a second tab, a
refresh, or the extra request the onboarding drawer was issuing on every page — silently replaced
the secret behind the QR code the user was already looking at. Their authenticator then produced a
code for a secret the server had thrown away, `/profile/totp-enable` checked the *newest* one, and
enrolment could not be completed through the UI at all. The integration arm proved the code was
correct for the secret that had been displayed and was rejected anyway.

What is pinned here is the property, not the symptom. "It works when nothing re-renders" is not the
same guarantee and would break again the next time something did; these tests render the page twice
before submitting, which is what the old code could not survive.

The second property is the one a smaller fix would have got wrong. The form posts `secret_token`,
so verifying against *that* would also have made the flow work — and would let anyone able to get a
user to submit a crafted form enrol a secret of their choosing. The candidate is read only from the
server-side session, and only for the user it was minted for.

Route module loaded with its container-only dependencies stubbed, following `test_bans_stats.py`
and `test_onboarding_routes.py`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Blueprint, Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "profile.py"


def _stub(name, **attributes):
    """A module object that also passes as a package, so `from x.y import z` resolves."""
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


@pytest.fixture(scope="module")
def route_module():
    """`profile.py` with everything it reaches at import time replaced.

    None of it is exercised here: `user_agents` parses session user agents, `qrcode` draws the
    enrolment image, `passlib` and `webauthn` back the credential models — and none is in the
    unit-test venv. What is under test is which secret the route hands to which check.
    """
    client = Mock()
    stubs = {
        "app.dependencies": _stub("app.dependencies", API_CLIENT=client, DATA={}, BW_CONFIG=Mock(), BW_INSTANCES_UTILS=Mock(), LOGGER=Mock()),
        "user_agents": _stub("user_agents", parse=Mock()),
        "qrcode": _stub("qrcode", make=Mock()),
        "qrcode.main": _stub("qrcode.main", QRCode=Mock()),
        "qrcode.image": _stub("qrcode.image"),
        "qrcode.image.pil": _stub("qrcode.image.pil", PilImage=Mock()),
        # Both models read or write container-only paths as they import — the TOTP model opens
        # `/var/lib/bunkerweb/.totp_encryption_keys.json`. Every one of their members used here is
        # replaced per-test anyway.
        "app.models.totp": _stub("app.models.totp", totp=Mock()),
        "app.models.webauthn": _stub(
            "app.models.webauthn",
            webauthn=Mock(),
            WebauthnCeremonyError=type("WebauthnCeremonyError", (Exception,), {}),
            WebauthnDisabledError=type("WebauthnDisabledError", (Exception,), {}),
        ),
    }

    module_name = "app.routes._profile_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def enrolment(route_module, monkeypatch):
    """The profile routes with a plain-dict session, so state carries across requests the way a
    real session does — the whole defect lives in what survives between two of them."""
    module, client = route_module
    client.reset_mock(return_value=True, side_effect=True)

    minted = iter(f"SECRET-{n}" for n in range(1, 9))
    totp = SimpleNamespace(
        generate_totp_secret=lambda: next(minted),
        generate_qrcode=lambda username, secret: f"qr-for:{secret}",
        get_totp_pretty_key=lambda secret: secret,
        generate_recovery_codes=lambda: ["recovery-1"],
        # A token is "valid" only for the secret it was derived from — the point of the whole test.
        verify_totp=lambda token, *, totp_secret=None, user=None: bool(totp_secret) and token == f"code-for:{totp_secret}",
        verify_recovery_code=lambda token, user=None: False,
    )

    session, rendered = {}, []
    monkeypatch.setattr(module, "session", session)
    monkeypatch.setattr(module, "TOTP", totp)
    monkeypatch.setattr(module, "WEBAUTHN", SimpleNamespace(enabled=False))
    monkeypatch.setattr(module, "get_last_sessions", lambda *a, **k: ([], 0))
    monkeypatch.setattr(module, "render_template", lambda name, **kwargs: rendered.append(kwargs) or "")
    monkeypatch.setattr(
        module,
        "current_user",
        SimpleNamespace(
            totp_secret=None,
            get_id=lambda: "alice",
            check_password=lambda password: password == "right",
            list_recovery_codes=[],
            theme="light",
            method="ui",
            language="en",
        ),
    )
    client.readonly = False

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.profile)

    def render():
        with app.test_request_context("/profile"):
            module.profile_page.__wrapped__()
        return rendered[-1]

    def enable(form):
        with app.test_request_context("/profile/totp-enable", method="POST", data=form):
            return module.totp_enable.__wrapped__()

    return SimpleNamespace(module=module, client=client, session=session, render=render, enable=enable, rendered=rendered)


def test_the_displayed_secret_survives_the_page_being_rendered_again(enrolment):
    """The defect itself. The second render used to replace the secret behind the first one's QR."""
    first = enrolment.render()
    second = enrolment.render()

    assert first["totp_secret"] == second["totp_secret"] == "SECRET-1"
    assert first["totp_qr_image"] == "qr-for:SECRET-1", "the QR has to encode the secret the page shows"


def test_a_code_for_the_secret_the_user_was_shown_is_accepted_after_a_re_render(enrolment):
    """End to end, in the order that used to fail: render, render again, then submit."""
    shown = enrolment.render()["totp_secret"]
    enrolment.render()

    response = enrolment.enable({"password": "right", "totp_token": f"code-for:{shown}"})

    assert response.status_code == 302
    assert enrolment.client.update_user.called, "a code for the secret the page displayed was rejected"
    assert enrolment.client.update_user.call_args.kwargs["totp_secret"] == shown
    assert "tmp_totp_secret" not in enrolment.session, "the candidate is consumed once it is promoted"


def test_the_posted_secret_token_is_never_trusted(enrolment):
    """The small fix that must not be taken: honouring the form's `secret_token` would let a
    crafted form enrol a secret the attacker chose."""
    shown = enrolment.render()["totp_secret"]

    response = enrolment.enable({"password": "right", "totp_token": "code-for:ATTACKER-SECRET", "secret_token": "ATTACKER-SECRET"})

    assert response.status_code == 302
    assert not enrolment.client.update_user.called, "a token minted for a client-supplied secret must not enrol it"
    assert enrolment.session["tmp_totp_secret"] == shown, "and the real candidate is left intact"


def test_a_candidate_minted_for_another_user_is_not_reused(enrolment):
    """A session that outlives a user change must not hand the next one a secret someone else has
    already seen."""
    enrolment.session.update({"tmp_totp_secret": "SOMEONE-ELSES", "tmp_totp_user": "bob"})

    shown = enrolment.render()["totp_secret"]

    assert shown == "SECRET-1"
    assert enrolment.session["tmp_totp_user"] == "alice"


def test_enabling_with_no_candidate_in_flight_is_refused_cleanly(enrolment):
    """Without a candidate there is nothing to verify against. Falling through would ask
    `verify_totp` to check an empty secret, which it reads as "use the enrolled one" — and at
    enrolment time there is none."""
    response = enrolment.enable({"password": "right", "totp_token": "code-for:SECRET-1"})

    assert response.status_code == 302
    assert not enrolment.client.update_user.called


def test_a_wrong_password_still_stops_enrolment(enrolment):
    """The candidate being stable must not weaken anything else on the path."""
    shown = enrolment.render()["totp_secret"]

    response = enrolment.enable({"password": "wrong", "totp_token": f"code-for:{shown}"})

    assert response.status_code == 302
    assert not enrolment.client.update_user.called


# ── A password change has to revoke the user's other sessions ──────────────────────────
#
# It did not. `/profile/edit` changed the password, flashed success and redirected the caller to
# `/logout`, which revokes exactly one id: the caller's own. Every other session of that user --
# including the one an attacker was holding, which is the reason a password gets changed in a hurry
# -- stayed live until it aged out: 12 h idle by default, `SESSION_ABSOLUTE_HOURS` (7 days) in
# continuous use. Nothing in the UI said so.
#
# The failure branch is tested as hard as the success one on purpose. A revocation that fails
# leaves exactly the sessions the user was trying to kill, so "log it and redirect to /logout"
# is not good enough: `logout.py` calls `session.clear()`, which destroys Flask's `_flashes` and
# our own `session["flash_messages"]` alike, so a warning flashed on the way out is never
# rendered at all (measured in `.cache/results-2026-08-20/flash-survives-logout.py`).


@pytest.fixture
def password_change(route_module, monkeypatch):
    module, client = route_module
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    # The caller is session 2. 1 and 3 are the "other" sessions -- one older, one newer.
    client.get_user_sessions.return_value = [{"id": 1}, {"id": 2}, {"id": 3}]

    state = SimpleNamespace(session={"session_id": 2, "flash_messages": []}, flashed=[], revoked=None, revoke_error="")

    def fake_revoke(ids):
        state.revoked = list(ids)
        return state.revoke_error

    monkeypatch.setattr(module, "session", state.session)
    monkeypatch.setattr(module, "revoke_sessions", fake_revoke)
    monkeypatch.setattr(module, "flash", lambda message, category="success", *args, **kwargs: state.flashed.append((message, category)))
    monkeypatch.setattr(module, "gen_password_hash", lambda password: b"hashed")
    monkeypatch.setattr(
        module,
        "current_user",
        SimpleNamespace(
            username="alice",
            get_id=lambda: "alice",
            email=None,
            totp_secret=None,
            method="ui",
            theme="light",
            language="en",
            check_password=lambda password: password == "right",
        ),
    )

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.profile)
    logout = Blueprint("logout", __name__)
    logout.add_url_rule("/logout", "logout_page", lambda: "")
    app.register_blueprint(logout)

    def change_password(new="N3wP@ssw0rd!"):
        form = {"password": "right", "new_password": new, "new_password_confirm": new}
        with app.test_request_context("/profile/edit", method="POST", data=form):
            return module.edit_profile.__wrapped__()

    state.change_password = change_password
    state.client = client
    return state


def test_changing_the_password_revokes_every_other_session(password_change):
    """The defect: the other sessions used to survive the password change entirely."""
    response = password_change.change_password()

    assert response.status_code == 302
    assert password_change.revoked == [1, 3], "every session but the caller's own must be revoked"
    assert password_change.client.delete_user_sessions.called, "the other session rows are never pruned"
    assert password_change.client.delete_user_sessions.call_args.kwargs["keep_session_id"] == 2
    # The reason rides out in the URL because the logout destroys the flash queue the success
    # message would otherwise use -- see tests/unit/ui/test_login_notices.py.
    assert response.headers["Location"].endswith("/logout?reason=password_changed")


def test_the_caller_is_not_revoked_out_from_under_themselves(password_change):
    """They are redirected to /logout, which ends their session cleanly. Revoking it here would
    also mean the id kept being rejected for the rest of the session lifetime."""
    password_change.change_password()

    assert 2 not in password_change.revoked


def test_a_failed_revocation_warns_the_user_instead_of_only_the_log(password_change):
    """Deliberate divergence from dev 9603eeb84, which logs and continues.

    The log line reaches an operator who is not watching; the only person who can act is the user,
    and they would otherwise see an unqualified success message. The redirect goes to /profile
    rather than /logout for a measured reason: session.clear() in logout.py destroys the flash
    before anything renders it -- and /profile is where "Wipe other sessions" is.
    """
    password_change.revoke_error = "No session backend available to record the revocation"

    response = password_change.change_password()

    warnings = [message for message, category in password_change.flashed if category == "error"]
    assert warnings, "a failure to revoke must reach the user, not only the log"
    assert "could not be revoked" in warnings[0]
    assert "/logout" not in response.headers["Location"], "the warning would be destroyed by session.clear()"
    assert response.headers["Location"].endswith("#sessions")


def test_a_failed_revocation_does_not_delete_the_rows_it_could_not_revoke(password_change):
    """Deleting them would remove the session list the user needs to see -- without ending a single
    one of those sessions, since it is the revocation that stops them, not the row."""
    password_change.revoke_error = "backend down"

    password_change.change_password()

    # Both halves, or this passes vacuously against a route that never revokes anything at all --
    # which is exactly what the pre-fix route did.
    assert password_change.revoked is not None, "revocation was not even attempted"
    assert not password_change.client.delete_user_sessions.called


def test_the_password_change_itself_still_stands_when_revocation_fails(password_change):
    """The password is already changed by then; reporting failure or rolling back would be worse."""
    password_change.revoke_error = "backend down"

    password_change.change_password()

    assert password_change.client.update_user.called
    # profile.py decodes bytes before handing them to the API client.
    assert password_change.client.update_user.call_args.kwargs["password"] == "hashed"


def test_the_revocation_is_wired_into_the_password_branch_itself():
    """Source-level, so the branch cannot be quietly rewritten around the stubbed helper above."""
    source = ROUTE_PATH.read_text(encoding="utf-8")
    branch = source.split('if "new_password" in request.form:')[-1]
    assert "revoke_sessions(" in branch
    assert "keep_session_id=" in branch
