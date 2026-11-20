"""Root `/favicon.ico` must resolve, and both halves of that are load-bearing.

Why this is a defect and not a tidy-up, stated without reference to any current output: every
browser requests `/favicon.ico` unprompted, on every page, whatever the markup declares. The UI
mounts Flask's static folder at the URL root (`static_url_path="/"`), so that request resolves to
`app/static/favicon.ico` -- and with the file living under `static/img/` instead, it 404s every
time. `USE_BAD_BEHAVIOR` defaults to yes, 404 is in its status list, the threshold is 10 in 60
seconds and the ban is 86400 seconds. A guaranteed 404 on the one path nobody has to click is a
permanent baseline contributor to that counter, eating headroom before any legitimate 404 arrives.

Two halves, and taking either alone is worse than taking neither:

  * nginx must proxy `/favicon.ico` to the UI. It is no longer under `img/`, so the static
    location regex has to name it.
  * the file must sit at the static root -- but moving it there while `base.html` still declares
    `img/favicon.ico` orphans the declared reference and breaks the page's own icon.

Ported from dev e8a7bc4f2, which moves the file and widens the regex but does NOT repoint
`base.html`; 1.7 cannot take that verbatim.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UI_CONF = REPO / "src" / "common" / "core" / "ui" / "confs" / "default-server-http" / "ui.conf"
STATIC = REPO / "src" / "ui" / "app" / "static"
TEMPLATES = REPO / "src" / "ui" / "app" / "templates"

# The `$` inside the nginx pattern is nginx's, and nginx URIs cannot contain a newline, so the
# `\Z`-versus-`$` trailing-newline hazard that applies to the UI's own name validators does not
# apply here. Asserting Python's newline behaviour on it would pin an artefact of this harness.
_LOCATION = re.compile(r"^location ~ (\S+) \{", re.M)


def _static_location_pattern():
    source = UI_CONF.read_text(encoding="utf-8")
    patterns = [m.group(1) for m in _LOCATION.finditer(source)]
    assert patterns, f"no `location ~ ... {{` block found in {UI_CONF.name} -- the file was restructured, re-read it"
    asset_blocks = [p for p in patterns if "css" in p and "locales" in p]
    # What this drops, said out loud rather than filtered silently: ui.conf carries a SECOND asset
    # location for the setup wizard, `^/setup/(css|fonts|img|js|libs|locales)(.*)$`. It is not
    # widened and does not need to be -- the browser asks for `/favicon.ico` at the root whatever
    # path the page itself is served from, so the root block is the one that answers.
    setup = [p for p in asset_blocks if "setup" in p]
    assert len(setup) == 1, f"the /setup/ asset location changed shape, re-read ui.conf: {asset_blocks}"
    root = [p for p in asset_blocks if "setup" not in p]
    assert len(root) == 1, f"expected exactly one root static-asset location, found {len(root)}: {patterns}"
    return re.compile(root[0])


@pytest.mark.parametrize(
    "path",
    ["/favicon.ico", "/css/style.css", "/fonts/x.woff2", "/img/logo.png", "/js/main.js", "/libs/ace/ace.js", "/locales/en.json"],
)
def test_nginx_proxies_the_paths_the_login_page_needs(path):
    """`/favicon.ico` alongside the six asset directories: the browser asks for all of them on the
    login page, which is served before any session exists."""
    assert _static_location_pattern().search(path), f"{path} is not proxied to the UI by the static location"


@pytest.mark.parametrize("path", ["/faviconxico", "/notfavicon.ico", "/favicon.ico.bak", "/api/jobs", "/css"])
def test_the_widened_regex_did_not_become_a_catch_all(path):
    """The anchor matters. `favicon\\.ico$` and not `favicon` -- widening this location to more
    than it needs would route unauthenticated traffic at the UI."""
    assert not _static_location_pattern().search(path), f"{path} is now proxied as a static asset and must not be"


def test_the_file_sits_where_the_url_root_resolves():
    """`static_url_path="/"` means `/favicon.ico` resolves to `static/favicon.ico` and nowhere
    else. This is the half nginx cannot supply."""
    assert (STATIC / "favicon.ico").is_file(), "root /favicon.ico still 404s: the file is not at the static root"


def test_the_url_root_mount_that_this_depends_on_is_still_in_place():
    """A precondition, not a marker: if `static_url_path` stops being `/`, the file above resolves
    at `/static/favicon.ico` instead and the browser's unprompted request 404s again."""
    main = (REPO / "src" / "ui" / "main.py").read_text(encoding="utf-8")

    # NOT a bare `'static_url_path="/"' in main`: that string also appears in the comment at :175
    # explaining the mount, so the assertion passed on the comment alone and a changed constructor
    # would have gone unnoticed. Found by a mutation gate refusing `--expect 1` on two occurrences.
    # Anchored on the assignment: a bare `DynamicFlask\(` matches `class DynamicFlask(Flask):`
    # first and captures "Flask" as the arguments.
    call = re.search(r"^app = DynamicFlask\((?P<args>[^)]*)\)", main, re.M)
    assert call, "the app is no longer constructed by `app = DynamicFlask(...)` -- re-read main.py"

    assert 'static_url_path="/"' in call.group("args"), "the UI no longer mounts its static folder at the URL root"


def test_no_template_still_declares_the_old_location():
    """The orphan direction. `test_static_asset_references.py` proves every declared reference
    exists; this proves the move did not leave one behind pointing into `img/`."""
    stale = [t.name for t in TEMPLATES.rglob("*.html") if "img/favicon.ico" in t.read_text(encoding="utf-8")]

    assert not stale, f"these templates still point at the pre-move favicon: {stale}"
