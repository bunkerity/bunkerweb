"""The UI's enrollment surface: the code goes to a modal, never anywhere durable.

An enrollment code is a bearer credential for exactly one redemption. The UI's other instance
actions use the flash + redirect flow, and putting the code through it would write it into a
session cookie and a redirect URL -- i.e. into browser history and, for the URL, into the access
log of whatever sits in front of the UI. So these three routes answer JSON instead.

The blueprint half is asserted against the sources: importing ``app.routes.instances`` pulls
``app.dependencies``, which reads ``/usr/share/bunkerweb/settings.json`` at import time. The
*template* half is not — it is rendered for real against a real ``Instance``, because that is the
half where the interesting bug lived: ``Instance`` is an object with fixed attributes and no
``get``, so ``instance.get('enrollment_state')`` in a template raises ``UndefinedError`` and 500s
the whole page while every source-grep assertion still passes.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.models.instance import Instance
from app.utils import ENROLLABLE_METHODS, is_enrollable_method, is_ui_api_method

ROOT = Path(__file__).resolve().parents[3]
ROUTE_SOURCE = (ROOT / "src" / "ui" / "app" / "routes" / "instances.py").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "src" / "ui" / "app" / "templates" / "instances.html").read_text(encoding="utf-8")
PAGE_JS = (ROOT / "src" / "ui" / "app" / "static" / "js" / "pages" / "instances.js").read_text(encoding="utf-8")
API_CLIENT = (ROOT / "src" / "ui" / "app" / "api_client.py").read_text(encoding="utf-8")


def _handler(name):
    body = re.search(rf"^def {name}\(.*?(?=^@instances\.route|\Z)", ROUTE_SOURCE, re.M | re.S)
    assert body, f"{name} is gone from the instances blueprint"
    return body.group(0)


@pytest.mark.parametrize("name", ("instances_enroll", "instances_rotate", "instances_revoke"))
def test_every_credential_route_refuses_a_read_only_database(name):
    body = _handler(name)
    assert "API_CLIENT.readonly" in body
    # The refusal comes before any API call.
    assert body.index("API_CLIENT.readonly") < body.index("API_CLIENT." + ("enroll" if "enroll" in name else ("rotate" if "rotate" in name else "revoke")))


@pytest.mark.parametrize("name", ("instances_enroll", "instances_rotate", "instances_revoke"))
def test_every_credential_route_requires_a_login(name):
    decorated = re.search(rf'@instances\.route\("/instances/<string:hostname>/\w+", methods=\["POST"\]\)\s*@login_required\s*\ndef {name}\(', ROUTE_SOURCE)
    assert decorated, f"{name} lost @login_required or its route decorator"


def test_the_code_never_goes_through_flash_or_redirect():
    """The regression this guards: reusing the page's flash+redirect flow would persist the code
    in the session cookie and the redirect URL."""
    body = _handler("instances_enroll")
    assert "flash(" not in body
    assert "redirect(" not in body
    assert "jsonify(" in body


def test_the_ui_reaches_the_api_only_through_api_client():
    for method in ("enroll_instance", "rotate_instance_credential", "revoke_instance_credential"):
        assert f"def {method}(" in API_CLIENT, f"api_client lost {method}"
        assert f"API_CLIENT.{method}(" in ROUTE_SOURCE


def test_the_enroll_button_is_disabled_on_rows_the_control_plane_does_not_own():
    """Enrollment only applies to rows the control plane can own a credential on -- an `autoconf`
    row is cleared and re-inserted from its orchestrator, which would wipe the minted credential.
    The template must not offer it, and it must ask the ENROLLMENT predicate: gating this on
    `can_delete_instance` hides the button on `manual` rows, which are enrollable."""
    button = re.search(r'class="icon-btn enroll-instance\{% if ([^%]+)%\}', TEMPLATE)
    assert button, "the enroll button lost its disabled guard"
    assert "not can_enroll_instance" in button.group(1)
    assert "is_readonly" in button.group(1)


def test_rotate_and_revoke_are_gated_on_a_live_credential():
    """Not on the state string: a re-issued code makes an enrolled row "pending" while its
    credential is still live, and gating on the state hid revoke exactly when it was needed.
    `TestThePageActuallyRenders` proves the behaviour; this pins the predicate itself.

    The `can_enroll_instance and` half is the method check: an autoconf row can hold a real
    credential, and rotating one is refused by the API with a 409. It is deliberately NOT the
    delete predicate -- a `manual` row is rotatable and revocable but not deletable from here."""
    assert re.search(r"\{% if can_enroll_instance and instance\['credential_updated_at'\]\|default\(none, true\) %\}", TEMPLATE)


def test_the_modal_warns_that_the_code_is_shown_once():
    assert "modal.body.enroll_shown_once" in TEMPLATE


def test_the_page_posts_with_a_csrf_token():
    """CSRFProtect is on app-wide; a JSON action without the token is a 400 at runtime.

    The input itself lives in the shared chrome (`navbar.html`), which every dashboard page
    renders — the page must NOT declare a second one, that is a duplicate DOM id.
    """
    assert 'id="csrf_token"' in (ROOT / "src" / "ui" / "app" / "templates" / "navbar.html").read_text(encoding="utf-8")
    assert 'id="csrf_token"' not in TEMPLATE
    action = re.search(r"function credentialAction\(.*?\n  \}", PAGE_JS, re.S)
    assert action, "credentialAction is gone from instances.js"
    assert "csrf_token" in action.group(0)


def test_destructive_credential_actions_ask_first():
    assert "confirm.rotate_credential" in PAGE_JS
    assert "confirm.revoke_credential" in PAGE_JS


# --------------------------------------------------------------------------------------
# Real render of the page's content block against a real Instance
# --------------------------------------------------------------------------------------
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"

# The page extends the dashboard shell and imports four component macros. Stub the shell down to
# its content block and the macros down to whatever they wrap: everything under test lives in
# instances.html's own `{% block content %}`.
_STUBS = {
    "dashboard.html": "{% block page_head %}{% endblock %}{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}",
    # Jinja macros have no `**kwargs` in their signature; referencing `kwargs` in the body is what
    # makes a macro accept arbitrary keyword arguments.
    "components/card.html": "{% macro card() %}{{ kwargs and '' }}{{ caller() }}{% endmacro %}",
    "components/table-toolbar.html": "{% macro table_toolbar() %}{{ kwargs and '' }}{{ caller() }}{% endmacro %}",
    "components/status.html": "{% macro status() %}<span class=\"status\">{{ kwargs.get('type', '') }}</span>{% endmacro %}",
    "components/page-head.html": "{% macro page_head() %}{{ kwargs and '' }}{{ caller() }}{% endmacro %}",
}


def _instance(**overrides):
    now = datetime(2026, 9, 2, 12, 0, 0)
    kwargs = {
        "hostname": "bw-1",
        "name": "bw-1",
        "method": "ui",
        "status": "up",
        "type": "static",
        "creation_date": now,
        "last_seen": now,
        "apiCaller": None,
    }
    kwargs.update(overrides)
    return Instance(**kwargs)


def _render(instances, **context):
    env = Environment(loader=ChoiceLoader([DictLoader(_STUBS), FileSystemLoader(TEMPLATES)]), autoescape=True)
    # This harness's own `_`: it echoes the key AND the variables passed to it. conftest installs
    # the real English catalog, and these keys are not in it yet (they are handed to the
    # coordinator's merge in i18n-keys-L-A.json), so the catalog `_` would swallow the very
    # interpolation these tests exist to check.
    env.globals["_"] = lambda key, **variables: key + ("|" + "|".join(f"{k}={v}" for k, v in sorted(variables.items())) if variables else "")
    env.globals["url_for"] = lambda endpoint, **kwargs: f"/{kwargs.get('filename', endpoint)}"
    env.globals["csrf_token"] = lambda: "token"
    # The real helpers, not a local copy: the two predicates stopped being the same set on
    # 2026-09-02 (`manual` is enrollable but still not deletable from here), and a lambda copy of
    # either one would render a page these tests never see.
    env.globals["is_ui_api_method"] = is_ui_api_method
    env.globals["is_enrollable_method"] = is_enrollable_method
    env.filters["to_iso"] = lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value)
    base = {
        "instances": instances,
        "theme": "light",
        "is_readonly": False,
        "user_readonly": False,
        "script_nonce": "n",
        "style_nonce": "n",
        "columns_preferences_defaults": {},
    }
    base.update(context)
    return env.get_template("instances.html").render(**base)


class TestThePageActuallyRenders:
    def test_an_unenrolled_instance_renders_without_raising(self):
        """The regression: `.get` on an `Instance` raises UndefinedError and 500s /instances."""
        html = _render([_instance()])
        assert "bw-1" in html
        # No chip for a row that was never enrolled.
        assert "instance.enrollment." not in html

    def test_an_enrolled_instance_shows_its_chip_and_credential_age(self):
        html = _render([_instance(enrollment_state="enrolled", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "instance.enrollment.enrolled" in html
        assert "2026-09-02T11:00:00+00:00" in html

    @pytest.mark.parametrize("state", ("pending", "enrolled", "revoked"))
    def test_every_state_renders_its_own_chip(self, state):
        assert f"instance.enrollment.{state}" in _render([_instance(enrollment_state=state)])

    def test_the_tls_badge_only_shows_when_pinned(self):
        assert "instance.tls.pinned" in _render([_instance(tls_mode="pinned")])
        assert "instance.tls.pinned" not in _render([_instance(tls_mode="off")])

    def test_rotate_and_revoke_follow_the_credential_not_the_state(self):
        """A re-issued code moves an enrolled row to "pending" while it still holds a live
        credential. Gating on the state string took the revoke button away from an instance the
        control plane could still reach — for the whole TTL, and permanently after a burn."""
        enrolled = _render([_instance(enrollment_state="enrolled", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "rotate-credential" in enrolled and "revoke-credential" in enrolled

        reissued = _render([_instance(enrollment_state="pending", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "rotate-credential" in reissued and "revoke-credential" in reissued

        never_enrolled = _render([_instance(enrollment_state="pending")])
        assert "rotate-credential" not in never_enrolled and "revoke-credential" not in never_enrolled

    def test_an_env_sourced_row_shows_no_chip_and_no_rotate_button(self):
        """The autoconf reconcile's `env["API_TOKEN"]` puts a real credential on `autoconf` rows,
        so the derived state reads "enrolled". The page must not dress that up as an enrollment:
        the row cannot be enrolled, revoked or deleted from here, and rotating it locks the control
        plane out of a healthy instance."""
        html = _render([_instance(method="autoconf", enrollment_state="enrolled", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "instance.enrollment." not in html
        assert "rotate-credential" not in html

    def test_a_control_plane_row_with_the_same_credential_keeps_both(self):
        html = _render([_instance(method="ui", enrollment_state="enrolled", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "instance.enrollment.enrolled" in html
        assert "rotate-credential" in html

    def test_an_env_sourced_row_cannot_be_enrolled_from_the_page(self):
        html = _render([_instance(method="autoconf")])
        assert re.search(r'class="icon-btn enroll-instance[^"]*\bdisabled\b', html)

    def test_a_control_plane_row_can_be(self):
        html = _render([_instance(method="ui")])
        assert not re.search(r'class="icon-btn enroll-instance[^"]*\bdisabled\b', html)


class TestAnEnrolledManualRowIsFullyManageable:
    """A `manual` row -- BUNKERWEB_INSTANCES / BUNKERWEB_INSTANCE_*, the Docker and Linux default --
    became enrollable on 2026-09-02 because the config-save rebuild now carries its credential
    across. Gating this half of the page on the DELETE predicate (which `manual` is still, rightly,
    outside of) would leave that shape enrollable through the API and invisible in the UI."""

    def test_it_shows_its_chip_and_its_rotate_and_revoke_buttons(self):
        html = _render([_instance(method="manual", enrollment_state="enrolled", credential_updated_at="2026-09-02T11:00:00+00:00")])
        assert "instance.enrollment.enrolled" in html
        assert "rotate-credential" in html and "revoke-credential" in html

    def test_it_can_be_enrolled_from_the_page(self):
        html = _render([_instance(method="manual")])
        assert not re.search(r'class="icon-btn enroll-instance[^"]*\bdisabled\b', html)

    def test_it_still_cannot_be_deleted_from_the_page(self):
        """The environment re-creates it on the next config save, so a DELETE here is a lie. This
        is the assertion that fails if someone "simplifies" the two predicates back into one."""
        html = _render([_instance(method="manual")])
        assert re.search(r'class="icon-btn danger delete-instance[^"]*\bdisabled\b', html)


def test_the_ui_predicate_mirrors_the_database_tuple():
    """`src/ui/` cannot import `db_methods`, so `ENROLLABLE_METHODS` is a copy. Pin it to the
    authority the API guards actually read, or the two drift and the page lies about a state the
    API enforces."""
    source = (ROOT / "src" / "common" / "db" / "db_methods" / "instances.py").read_text(encoding="utf-8")
    declared = re.search(r"^ENROLLABLE_METHODS = \(([^)]*)\)", source, re.M)
    assert declared, "ENROLLABLE_METHODS is gone from db_methods/instances.py"
    assert set(re.findall(r'"([^"]+)"', declared.group(1))) == set(ENROLLABLE_METHODS)


class TestInstanceStaysBackwardCompatible:
    def test_the_new_attributes_are_optional(self):
        """Every existing caller builds `Instance` positionally with eight arguments."""
        instance = _instance()
        assert (instance.enrollment_state, instance.tls_mode, instance.credential_updated_at) == ("none", "off", None)

    def test_a_none_from_the_api_projection_still_lands_on_a_usable_default(self):
        instance = _instance(enrollment_state=None, tls_mode=None)
        assert (instance.enrollment_state, instance.tls_mode) == ("none", "off")
