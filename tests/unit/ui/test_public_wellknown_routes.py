"""The four public paths the UI answers without an account, and the one field that can leak.

Ported from dev `2eb795fad` and `4264af5c3`. `/robots.txt` is a static file; the other three are
routes: RFC 9116's `security.txt` at its canonical `/.well-known` location, the legacy root path
that redirects to it, and the W3C change-password URL a password manager follows.

All four are in ``app.utils.STATIC_EXACT_PATHS``, which means ``before_request`` returns **before**
its Host-header check, its authorization and its session-revocation check ever run. That is correct
for a document with no secrets in it -- and it is exactly why the ``Canonical`` field is the sharp
edge here. ``Canonical`` is built with ``_external=True``, so it is assembled from the request's own
Host header; emitted unconditionally it would reflect any Host a caller sends back inside a document
whose entire purpose is to be trusted. So it is emitted only when a real allowlist exists **and**
vets that host, and ``"*"`` is not a real allowlist. Half of this file is that one field.

The bodies are lifted out of ``main.py`` by AST rather than copied, so what runs here is shipped
code; importing ``main`` boots the whole UI.

One interaction is measured rather than assumed, because the UI mounts its static folder at the
URL root (``static_url_path="/"``, pinned by ``test_favicon_root_resolves.py``): under that mount
an explicit rule still wins over the static catch-all, so ``/security.txt`` reaches the redirect
even with a file of that name sitting in ``static/``, while ``/robots.txt`` -- which has no rule --
falls through to the file. Measured on a throwaway app with both present.
"""

from ast import FunctionDef, parse, unparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

flask = pytest.importorskip("flask")

MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"
STATIC = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static"

ROUTES = ("security_txt", "security_txt_redirect", "change_password_redirect")


def _tree():
    return parse(MAIN.read_text(encoding="utf-8"))


def _app(allowed_hosts=None, fake_now=None):
    """A bare Flask app carrying the three real route bodies plus a stand-in profile page."""
    application = flask.Flask("bw_ui_wellknown_test")
    application.config["ALLOWED_HOSTS"] = allowed_hosts or []

    namespace = {
        "app": application,
        "Response": flask.Response,
        "redirect": flask.redirect,
        "url_for": flask.url_for,
        "request": None,  # rebound by Flask's proxy below
        "timedelta": timedelta,
        "datetime": fake_now or datetime,
    }
    namespace["request"] = flask.request

    tree = _tree()
    # `_host_allowed` is lifted too rather than stubbed: a stub that answers True for everything
    # would make every Canonical test below pass regardless of what the real matcher does.
    for name in ("_host_allowed",) + ROUTES:
        fn = next(n for n in tree.body if isinstance(n, FunctionDef) and n.name == name)
        fn.decorator_list = []
        exec(compile(unparse(fn), str(MAIN), "exec"), namespace)  # noqa: S102

    profile = flask.Blueprint("profile", __name__)
    profile.add_url_rule("/profile", "profile_page", lambda: "profile")
    application.register_blueprint(profile)

    application.add_url_rule("/.well-known/security.txt", "security_txt", namespace["security_txt"])
    application.add_url_rule("/security.txt", "security_txt_redirect", namespace["security_txt_redirect"])
    application.add_url_rule("/.well-known/change-password", "change_password_redirect", namespace["change_password_redirect"])
    return application


def _fetch(path="/.well-known/security.txt", host="ui.example.com", allowed_hosts=None, fake_now=None):
    application = _app(allowed_hosts, fake_now)
    return application.test_client().get(path, headers={"Host": host})


def _fields(response):
    lines = [line for line in response.get_data(as_text=True).splitlines() if line]
    assert lines, "security.txt came back empty -- every assertion below would be vacuous"
    return dict(line.split(": ", 1) for line in lines)


# --------------------------------------------------------------------------------------
# The document itself
# --------------------------------------------------------------------------------------
def test_the_mandatory_rfc_9116_fields_are_present():
    """`Contact` and `Expires` are the two the RFC makes mandatory; a file missing either is not a
    security.txt, it is a text file at a well-known URL."""
    fields = _fields(_fetch())

    assert fields.get("Contact"), "no Contact field: a reporter has nowhere to send a finding"
    assert fields.get("Expires"), "no Expires field: RFC 9116 requires it and consumers reject the document without it"


def test_it_is_served_as_plain_text():
    """A `text/html` security.txt is rendered rather than read by half the tools that fetch it."""
    assert _fetch().headers["Content-Type"] == "text/plain; charset=utf-8"


def test_expires_is_generated_per_request_and_not_a_shipped_literal():
    """The whole reason this is a route and not a static file next to robots.txt.

    A committed date expires unattended and silently invalidates the document. Asserting merely
    that it is in the future would pass on a hard-coded literal for a year -- so the clock is moved
    and the answer has to move with it.
    """
    stamps = []
    for offset in (0, 40 * 365):
        moment = datetime.now(timezone.utc) + timedelta(days=offset)
        stamps.append(_fields(_fetch(fake_now=SimpleNamespace(now=lambda _m=moment: _m)))["Expires"])

    assert stamps[0] != stamps[1], "Expires did not follow the clock -- it is a fixed value, and it will go stale unattended"
    assert datetime.fromisoformat(stamps[0]) > datetime.now(timezone.utc), "the document is already expired as issued"


def test_expires_stays_within_the_year_the_rfc_recommends():
    """RFC 9116 says less than a year. A five-year Expires is how a document outlives the address
    in its own Contact field."""
    issued = datetime.fromisoformat(_fields(_fetch())["Expires"])

    assert issued <= datetime.now(timezone.utc) + timedelta(days=366), f"Expires is {issued}, more than a year out"


# --------------------------------------------------------------------------------------
# Canonical: the one field assembled from the caller's own Host header
# --------------------------------------------------------------------------------------
def test_canonical_is_absent_when_no_allowlist_is_configured():
    """The default deployment. Nothing has vetted the Host, so nothing derived from it is emitted."""
    assert "Canonical" not in _fields(_fetch(allowed_hosts=[]))


def test_a_wildcard_allowlist_is_not_an_allowlist():
    """`"*"` matches every host `_host_allowed` is ever asked about, so treating it as vetting is
    the same as emitting Canonical unconditionally. The check is on the *list*, not its answer."""
    assert "Canonical" not in _fields(_fetch(host="evil.example.net", allowed_hosts=["*"]))


def test_a_host_the_allowlist_does_not_cover_gets_no_canonical():
    assert "Canonical" not in _fields(_fetch(host="evil.example.net", allowed_hosts=["ui.example.com"]))


def test_a_vetted_host_gets_a_canonical_pointing_at_itself():
    """The other direction: the field must actually appear for a correctly configured UI, or the
    four tests above are satisfied by a function that never emits it at all."""
    canonical = _fields(_fetch(host="ui.example.com", allowed_hosts=["ui.example.com"])).get("Canonical")

    assert canonical, "no Canonical for a host the allowlist covers -- the field is dead code"
    assert canonical.endswith("/.well-known/security.txt")
    assert "ui.example.com" in canonical


def test_canonical_never_carries_a_host_the_allowlist_did_not_vet():
    """The attack this ordering exists to stop, stated as one assertion over every shape above."""
    for host, allowed in (("evil.example.net", []), ("evil.example.net", ["*"]), ("evil.example.net", ["ui.example.com"])):
        assert "evil.example.net" not in _fetch(host=host, allowed_hosts=allowed).get_data(as_text=True), f"Host {host!r} reflected with allowlist {allowed!r}"


# --------------------------------------------------------------------------------------
# The two redirects
# --------------------------------------------------------------------------------------
def test_the_legacy_root_location_redirects_to_the_canonical_one():
    """RFC 9116 keeps `/security.txt` for legacy fetchers; 301 because that move is permanent."""
    response = _fetch(path="/security.txt")

    assert response.status_code == 301
    assert response.headers["Location"].endswith("/.well-known/security.txt")


def test_change_password_points_a_password_manager_at_the_profile_page():
    response = _fetch(path="/.well-known/change-password")

    assert response.status_code == 302, "302, not 301: the page holding the form may move"
    assert response.headers["Location"].endswith("/profile")


# --------------------------------------------------------------------------------------
# The bodies above can be perfect and never run
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name,rule",
    [("security_txt", "/.well-known/security.txt"), ("security_txt_redirect", "/security.txt"), ("change_password_redirect", "/.well-known/change-password")],
)
def test_each_route_is_still_registered_at_its_well_known_path(name, rule):
    """A well-known URL is only useful at its well-known URL; a renamed rule is a 404 nobody
    reports, because the fetchers are scanners and password managers, not users."""
    fn = next(n for n in _tree().body if isinstance(n, FunctionDef) and n.name == name)
    decorators = [unparse(d) for d in fn.decorator_list]

    assert any(rule in d and "app.route" in d for d in decorators), f"{name} is no longer routed at {rule}: {decorators}"


@pytest.mark.parametrize("name", ROUTES)
def test_no_public_route_is_behind_a_login(name):
    """`@login_required` here would answer a scanner with a redirect to the login page. It is also
    unreachable: these paths are in STATIC_EXACT_PATHS, so `before_request` returns before the
    login check -- the decorator would be dead code that reads as protection."""
    fn = next(n for n in _tree().body if isinstance(n, FunctionDef) and n.name == name)

    assert "login_required" not in [unparse(d) for d in fn.decorator_list]


def test_robots_txt_is_the_one_that_is_a_file_and_it_disallows_everything():
    """The fourth public path. It is static because, unlike security.txt, nothing in it expires."""
    robots = (STATIC / "robots.txt").read_text(encoding="utf-8")

    assert "User-agent: *" in robots
    assert "Disallow: /" in robots


def test_the_ui_template_no_longer_asks_bunkerweb_to_answer_robots_txt():
    """The other half of shipping that file, and the reason dev `2eb795fad` touches a template.

    `USE_ROBOTSTXT` makes the `robotstxt` core plugin answer `/robots.txt` in the access phase
    (`core/robotstxt/robotstxt.lua:210`), before the request is ever proxied. With it set on the UI
    service, the file above is unreachable behind BunkerWeb and only serves a UI reached directly.
    The generated body and the shipped file say the same thing today, so re-adding the setting
    breaks nothing visibly -- which is precisely why it would be re-added during a template sync
    and why the loss would go unnoticed until someone edited robots.txt and nothing changed.
    """
    from json import loads

    template = loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "templates" / "templates" / "ui.json").read_text(encoding="utf-8"))
    declared = [setting for step in template["steps"] for setting in step["settings"]]

    assert "USE_ROBOTSTXT" not in template["settings"], "the UI template enables the robotstxt plugin again; static/robots.txt is now shadowed"
    assert "USE_ROBOTSTXT" not in declared, "USE_ROBOTSTXT is back in the template's step list"
