"""The breadcrumb renders one crumb per path segment — and none for the empty first one.

`request.path.split("/")` opens with an empty string: `"/profile"` is `["", "profile"]`. The
template emitted an `<li>` for it, and the label is built by concatenation, so the key was
`"breadcrumb." ~ ""`. gettext cannot find `breadcrumb.` and **echoes what it cannot find**, so every
page in the UI showed a first crumb reading `breadcrumb.` — and `common.js` builds the document
title out of the crumb anchors, so the page title read `breadcrumb. - Profile - BunkerWeb UI`.

This is the colvis defect from the i18n work one layer down: there, an empty `data-i18n` key made
`t("")` **blank** a label; here an empty key makes gettext **echo** one. Same cause, opposite
symptom, and neither fails anything on its own.

The loop still visits the empty segment on purpose. The `/configs` and `/cache` branches test
`loop.index` against positions that count it, so dropping it from the iteration would silently move
every one of them by one; only the emission is skipped.
"""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"

ROUTES = {"configs": "/configs", "cache": "/cache", "profile": "/profile", "services": "/services"}


def _render(path, current_endpoint=None, extra_pages=()):
    """`breadcrumb.html` on its own, with the globals the app gives it."""

    def url_for(endpoint, **values):
        url = ROUTES.get(endpoint, "#")
        if url != "#" and values:
            url += "?" + "&".join(f"{name}={value}" for name, value in values.items())
        return url

    environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    # The template asks `endpoint_exists` before building, so a route that is absent costs no
    # warning; both globals have to agree here or the harness tests a template the app never renders.
    environment.globals.update(url_for=url_for, endpoint_exists=lambda endpoint: endpoint in ROUTES)
    return environment.get_template("breadcrumb.html").render(
        request=SimpleNamespace(path=path),
        current_endpoint=current_endpoint if current_endpoint is not None else path.strip("/").split("/")[0],
        breadcrumbs_url=path,
        extra_pages=list(extra_pages),
    )


def _crumbs(html):
    """The rendered crumbs as `(text, href)`, read the way a reader sees them."""
    import re

    return [
        (re.sub(r"<[^>]+>", "", item).strip(), (re.search(r'href="([^"]*)"', item) or [None, None])[1])
        for item in re.findall(r'<li class="breadcrumb-item.*?</li>', html, re.DOTALL)
    ]


def test_the_empty_leading_segment_gets_no_crumb():
    """The one that shipped: `["", "profile"]` produced two crumbs, the first reading `breadcrumb.`"""
    crumbs = _crumbs(_render("/profile"))

    assert [text for text, _ in crumbs] == ["Profile"]


def test_no_crumb_is_ever_an_echoed_key():
    """Stated as the rule rather than the instance: a label that is a bare key ending in a dot is
    gettext echoing something it could not find, whatever produced it."""
    for path in ("/profile", "/configs", "/cache", "/services", "/configs/new", "/"):
        for text, _ in _crumbs(_render(path)):
            assert not text.endswith("."), f"{path} renders an untranslated key: {text!r}"
            assert not text.startswith("breadcrumb."), f"{path} renders an untranslated key: {text!r}"


def test_the_configs_positions_still_line_up():
    """`/configs/new` is the path whose second and third `loop.index` branches both fire. If the
    empty segment were dropped from the iteration rather than from the output, `new` would fall at
    index 2 instead of 3 and lose its `?action=new` link — with the crumb still looking right.
    """
    crumbs = _crumbs(_render("/configs/new", current_endpoint="new"))

    assert crumbs == [("Configs", "/configs"), ("New", "/configs?action=new")]


def test_the_root_path_renders_no_crumbs_rather_than_one_empty_one():
    assert _crumbs(_render("/")) == []
