"""The 495/496 error location of ``server-http/mtls.conf`` (S3 of the mTLS fix wave).

nginx answers a missing (496) or an invalid (495) client certificate with its own stock 400 page. The
template routes both to a named location that marks the request with ``$mtls_cert_error`` (read by Bad
Behavior, which skips the request unless ``MTLS_COUNT_BAD_BEHAVIOR`` is yes), forces the status to 400 and
renders BunkerWeb's 400 page when the errors plugin owns the 400 code. The stream block has no error pages.
"""

import re

import pytest

from _t4_helpers import full_renderer


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def http(render, **variables):
    base = {"MULTISITE": "no", "SERVER_NAME": "no-cached-ca.example.com", "USE_MTLS": "yes", "MTLS_VERIFY_CLIENT": "on"}
    return render(**(base | variables))["server-http/mtls.conf"]


def location(text):
    """The body of ``location @mtls_cert_error { ... }`` as stripped directive lines."""
    match = re.search(r"location @mtls_cert_error \{\n(.*?)\n\}", text, re.S)
    assert match, text
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


@pytest.mark.parametrize("mode", ["on", "optional", "optional_no_ca"])
def test_both_certificate_failures_go_to_the_marking_location_with_an_explicit_400(render, mode):
    text = http(render, MTLS_VERIFY_CLIENT=mode)
    assert text.count("error_page 495 496 =400 @mtls_cert_error;") == 1
    body = location(text)
    assert body[:4] == ["internal;", "auth_basic off;", "modsecurity off;", 'set $mtls_cert_error "yes";']


def test_the_default_setup_renders_bunkerwebs_400_page(render):
    body = location(http(render))
    assert "root /usr/share/bunkerweb/core/errors/files;" in body
    assert "ngx.status = ngx.HTTP_BAD_REQUEST" in body
    assert 'require("errors.errors"):new():render_template("400")' in body
    assert "return 400;" not in body


@pytest.mark.parametrize(
    "variables",
    [{"INTERCEPTED_ERROR_CODES": "404 500"}, {"INTERCEPTED_ERROR_CODES": ""}, {"ERRORS": "400=/custom400.html"}],
    ids=["400 not intercepted", "nothing intercepted", "custom 400 page"],
)
def test_a_setup_that_does_not_give_the_400_to_the_errors_plugin_keeps_the_stock_page(render, variables):
    body = location(http(render, **variables))
    assert body[-1] == "return 400;"
    assert not any("content_by_lua_block" in line for line in body)
    assert 'set $mtls_cert_error "yes";' in body


def test_html_injection_is_blocked_on_the_page_like_on_the_errors_plugin_page(render):
    assert "sub_filter '</head>' '</head>';" in location(http(render, INJECT_HEAD="<meta>"))
    assert "sub_filter '</head>' '</head>';" not in location(http(render))


def test_the_error_location_is_part_of_every_mtls_service_not_of_a_disabled_one(render):
    assert "@mtls_cert_error" not in http(render, USE_MTLS="no")


@pytest.mark.parametrize("use_mtls", ["yes", "no"])
@pytest.mark.parametrize("multisite", ["no", "yes"])
def test_the_marker_has_an_empty_default_for_every_request_of_every_service(render, use_mtls, multisite):
    """Bad Behavior reads ``$mtls_cert_error`` for any counted failure, on any service.

    nginx logs ``using uninitialized "mtls_cert_error" variable`` (warn) for a variable that a ``set`` declared
    somewhere in the configuration and that the request never set. A request that fails before the rewrite phase
    (an invalid Content-Length) never runs a server-level ``set`` either, so the default is an http-level ``map``
    that has a value for every request, and it is rendered whether or not a service uses mTLS.
    """
    base = {"MULTISITE": multisite, "SERVER_NAME": "app.example.com", "USE_MTLS": use_mtls}
    text = render(**base)["http/mtls.conf"]
    directives = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert directives == ['map "" $mtls_cert_error {', 'default "";', "}"]


def test_the_error_location_overrides_the_http_level_default(render):
    # a `set` on a map variable replaces its value for the request, so the location still marks the request
    assert 'set $mtls_cert_error "yes";' in location(http(render))


def test_the_stream_block_has_no_http_error_pages(render):
    text = render(MULTISITE="no", SERVER_NAME="stream.example.com", USE_MTLS="yes", SERVER_TYPE="stream", MTLS_VERIFY_CLIENT="on")["server-stream/mtls.conf"]
    assert "error_page" not in text and "mtls_cert_error" not in text


def test_the_marked_location_cannot_be_reached_from_outside(render):
    # `internal` makes a direct request answer 404, so nobody can set the mark on a request they send
    assert location(http(render))[0] == "internal;"


def test_every_help_string_of_the_plugin_stays_under_the_configurator_cap():
    """Configurator drops a whole plugin.json whose help exceeds 512 characters, so no mTLS setting would exist."""
    import json
    from pathlib import Path

    settings = json.loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "mtls" / "plugin.json").read_text())["settings"]
    assert {"MTLS_HTTP_POLICY", "MTLS_COUNT_BAD_BEHAVIOR"} <= set(settings)
    assert all(len(setting["help"]) <= 512 for setting in settings.values())


@pytest.mark.parametrize("protocols", ["TLSv1.3", "TLSv1.2 TLSv1.3"])
def test_the_error_location_does_not_depend_on_the_tls_protocols(render, protocols):
    assert "error_page 495 496 =400 @mtls_cert_error;" in http(render, SSL_PROTOCOLS=protocols)
