"""The ``@bwerror*`` handlers must keep rendering the error page whatever ``DENY_HTTP_STATUS`` is.

rc4 made the intercepted-error handlers ``return 444`` when ``DENY_HTTP_STATUS=444`` (an attempt to
close the connection on denied requests, #3448). That short-circuit also swallowed the error pages of
every intercepted code, custom ones included, so a site that rewrote its 404 page got a closed
connection instead (#3490). The handlers now always render the page through the errors plugin; the
444 is applied where the denial happens, not here. The test pins both the service and the default
server handlers with ``DENY_HTTP_STATUS`` at 444.

Refs: #3490 (and the template side of #3448).
"""

import re

import pytest

from _t4_helpers import full_renderer

INTERCEPTED = "400 401 403 404 405 429 500 501 502 503 504"


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def location_block(text, target):
    """The text of the ``location`` on ``target`` (e.g. ``@bwerror404``), up to the next top-level ``location`` / ``error_page``.

    Not "up to the closing brace": the Lua block has braces of its own and whitespace control can glue
    the closing brace to the previous line.
    """
    match = re.search(rf"^location\s+{re.escape(target)}\s*{{", text, re.M)
    assert match, f"location {target} not rendered"
    rest = text[match.end() :]  # noqa: E203
    following = re.search(r"^(?:location|error_page)\b", rest, re.M)
    return rest[: following.start()] if following else rest


@pytest.mark.parametrize("template", ["server-http/errors.conf", "default-server-http/errors.conf"])
@pytest.mark.parametrize("code", ["401", "403", "404", "429", "500"])
def test_handler_renders_the_page_even_when_denials_are_444(render, template, code):
    tree = render(MULTISITE="no", SERVER_NAME="app.example.com", DENY_HTTP_STATUS="444", INTERCEPTED_ERROR_CODES=INTERCEPTED)
    block = location_block(tree[template], f"@bwerror{code}")
    assert "return 444" not in block
    assert "content_by_lua_block" in block
    assert "errors:render_template(tostring(ngx.status))" in block


@pytest.mark.parametrize("template", ["server-http/errors.conf", "default-server-http/errors.conf"])
def test_the_400_handler_is_not_short_circuited_either(render, template):
    tree = render(MULTISITE="no", SERVER_NAME="app.example.com", DENY_HTTP_STATUS="444", INTERCEPTED_ERROR_CODES=INTERCEPTED)
    block = location_block(tree[template], "= /bwerror400")
    assert "return 444" not in block
    assert "errors:render_template(tostring(ngx.status))" in block


def test_a_rewritten_404_page_is_still_served_with_denials_at_444(render):
    """The reported shape: a custom 404 page next to DENY_HTTP_STATUS=444 and the other codes left default."""
    tree = render(MULTISITE="no", SERVER_NAME="app.example.com", DENY_HTTP_STATUS="444", ERRORS="404=/404.html", INTERCEPTED_ERROR_CODES=INTERCEPTED)
    rendered = tree["server-http/errors.conf"]
    assert "error_page 404 @bwcustomerror404;" in rendered
    assert "rewrite ^ /404.html break;" in location_block(rendered, "@bwcustomerror404")
    assert "return 444" not in rendered


def test_the_rendered_handlers_do_not_depend_on_the_denial_status(render):
    """Same handlers for 444 as for any other ``DENY_HTTP_STATUS``: nothing in these templates reads it."""
    variables = {"MULTISITE": "no", "SERVER_NAME": "app.example.com", "INTERCEPTED_ERROR_CODES": INTERCEPTED}
    reference = render(DENY_HTTP_STATUS="403", **variables)
    candidate = render(DENY_HTTP_STATUS="444", **variables)
    for template in ("server-http/errors.conf", "default-server-http/errors.conf"):
        assert candidate[template] == reference[template]
