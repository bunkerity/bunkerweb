"""External CAPTCHA pages must tell the visitor when the provider fails, and offer a reload.

Dev #3867 (0e88c7d0a): when the provider script is blocked or fails to load, or the widget
reports an error or an expiry, the page used to stay blank (or reload at once on expiry). Each
page now shows an accessible message (``#challenge-error``, ``role="alert"``) and a
``#challenge-retry`` button that reloads the challenge.

The templates are rendered with the real ``resty.template`` (plain Lua, no nginx) and driven in
Chromium with the provider hosts blocked or stubbed, under a CSP that only allows nonced inline
scripts. Needs ``playwright`` + a Chromium build, and ``lua``; skipped without them.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[3]
FILES = ROOT / "src" / "common" / "core" / "antibot" / "files"
TEMPLATE_LIB = ROOT / "src" / "deps" / "src" / "lua-resty-template" / "lib"

ORIGIN = "https://antibot.test"
CHALLENGE = f"{ORIGIN}/challenge"
NONCE = "nonce-test"
LUA = """
package.path = arg[1] .. "/?.lua;" .. package.path
local template = require "resty.template"
local vars = { antibot_uri = "/challenge", nonce_script = arg[3], nonce_style = arg[3], next = "/",
  recaptcha_sitekey = "rk", recaptcha_classic = arg[4] == "classic", hcaptcha_sitekey = "hk",
  turnstile_sitekey = "tk", mcaptcha_sitekey = "mk", mcaptcha_url = "https://mcaptcha.test",
  capjs_url = "https://cap.test", capjs_sitekey = "ck" }
io.write(template.process_file(arg[2], vars))
"""
CSP = f"script-src 'nonce-{NONCE}' https://js.hcaptcha.com https://challenges.cloudflare.com " "https://www.google.com https://unpkg.com https://cap.test"

# id -> (template, recaptcha mode, URL pattern of the provider script(s))
CASES = {
    "hcaptcha": ("hcaptcha.html", "", "https://js.hcaptcha.com/**"),
    "turnstile": ("turnstile.html", "", "https://challenges.cloudflare.com/**"),
    "mcaptcha": ("mcaptcha.html", "", "https://unpkg.com/**"),
    "recaptcha-classic": ("recaptcha.html", "classic", "https://www.google.com/recaptcha/**"),
    "recaptcha-enterprise": ("recaptcha.html", "enterprise", "https://www.google.com/recaptcha/**"),
    "capjs": ("capjs.html", "", "https://cap.test/**"),
}


def render(name: str, mode: str = "") -> str:
    done = subprocess.run(
        ["lua", "-", str(TEMPLATE_LIB), str(FILES / name), NONCE, mode],
        input=LUA,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.fixture(scope="module")
def browser():
    try:
        subprocess.run(["lua", "-v"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("lua is not installed")
    with sync_api.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch()
        except sync_api.Error as exc:
            pytest.skip(f"chromium is not available: {exc}")
        yield instance
        instance.close()


def open_challenge(browser, case: str, provider=None):
    """Load the rendered page; ``provider`` is a route handler for the provider hosts (default: abort)."""
    name, mode, pattern = CASES[case]
    page = browser.new_page()
    requests = []
    page.on("request", lambda request: requests.append(request.url) if request.url.split("?")[0] == CHALLENGE else None)

    def serve(route):
        html = render("capjs_frame.html") if "capjs_frame=1" in route.request.url else render(name, mode)
        route.fulfill(body=html, content_type="text/html", headers={"Content-Security-Policy": CSP})

    page.route(CHALLENGE + "**", serve)
    page.route(pattern, provider or (lambda route: route.abort()))
    page.goto(CHALLENGE)
    return page, requests


def stub(script: str):
    """Provider route that answers every script request with ``script`` (``__URL__`` = the request URL)."""

    def handler(route):
        route.fulfill(body=script.replace("__URL__", json.dumps(route.request.url)), content_type="text/javascript")

    return handler


def assert_recovery(page):
    page.wait_for_function("() => (document.getElementById('challenge-error') || { textContent: '' }).textContent.trim() !== ''", timeout=5000)
    error = page.locator("#challenge-error")
    assert error.get_attribute("role") == "alert"
    assert error.is_visible()
    assert page.locator("#challenge-retry").is_visible()
    assert page.locator("h3").first.is_visible()  # the page is not blank
    assert page.locator("#token, #mcaptcha__token").first.input_value() == ""  # nothing was submitted


@pytest.mark.parametrize("case", CASES)
def test_a_provider_script_that_fails_to_load_shows_the_message_and_a_working_reload(browser, case):
    page, requests = open_challenge(browser, case)
    try:
        assert_recovery(page)
        page.locator("#challenge-retry").click()
        for _ in range(50):
            if len(requests) >= 2:
                break
            page.wait_for_timeout(100)
        assert len(requests) >= 2, "the reload button must request the challenge page again"
    finally:
        page.close()


@pytest.mark.parametrize("case", CASES)
def test_every_inline_script_carries_the_nonce_and_no_inline_handler_exists(case):
    name, mode, _ = CASES[case]
    html = render(name, mode)
    for tag in re.findall(r"<script\b[^>]*>", html):
        assert f'nonce="{NONCE}"' in tag, tag
    assert not re.search(r"\son[a-z]+\s*=", html)


# --- widget callbacks (provider stubbed) -----------------------------------------------------

HCAPTCHA_STUB = "window.hcaptcha = { render: function (id, opts) { window.__opts = opts; } }; window.addEventListener('load', function () { window.renderHCaptcha && window.renderHCaptcha(); });"


@pytest.mark.parametrize("callback", ["error-callback", "expired-callback", "chalexpired-callback"])
def test_hcaptcha_widget_errors_show_the_message(browser, callback):
    page, _ = open_challenge(browser, "hcaptcha", stub(HCAPTCHA_STUB))
    try:
        page.wait_for_function("() => window.__opts")
        page.evaluate(f"window.__opts[{callback!r}]()")
        assert_recovery(page)
    finally:
        page.close()


def test_hcaptcha_success_clears_the_message(browser):
    page, _ = open_challenge(browser, "hcaptcha", stub(HCAPTCHA_STUB))
    try:
        page.wait_for_function("() => window.__opts")
        page.evaluate("window.__opts['error-callback']()")
        assert_recovery(page)
        page.evaluate("document.getElementById('form').submit = function () {}; window.__opts.callback('tok')")
        assert page.locator("#challenge-error").text_content() == ""
        assert page.locator("#token").input_value() == "tok"
    finally:
        page.close()


@pytest.mark.parametrize("attribute", ["data-error-callback", "data-expired-callback", "data-timeout-callback"])
def test_turnstile_declares_error_expiry_and_timeout_callbacks(browser, attribute):
    page, _ = open_challenge(browser, "turnstile", stub("/* turnstile stub */"))
    try:
        name = page.locator(".cf-turnstile").get_attribute(attribute)
        assert name, f"{attribute} is missing on the widget"
        page.evaluate(f"window[{name!r}]()")
        assert_recovery(page)
        assert not page.locator(".lds-roller").is_visible()  # no endless spinner next to the error
    finally:
        page.close()


def recaptcha_stub(callback: str, execute: str = "Promise.resolve('tok')") -> str:
    return (
        "window.grecaptcha = { ready: function (f) { f(); }, execute: function () { return " + execute + "; },"
        " render: function (id, opts) { window.__opts = opts; }, enterprise: { ready: function (f) { f(); },"
        " execute: function () { return " + execute + "; }, render: function (id, opts) { window.__opts = opts; } } };"
        f"window.addEventListener('load', function () {{ window.{callback}(); }});"
    )


def only(callback: str, stub_script: str):
    """Answer only the script whose ``onload`` is ``callback``; any other recaptcha script is a no-op."""

    def handler(route):
        if f"onload={callback}" in route.request.url:
            route.fulfill(body=stub_script, content_type="text/javascript")
        else:
            route.fulfill(body="/* not loaded */", content_type="text/javascript")

    return handler


@pytest.mark.parametrize("callback", ["error-callback", "expired-callback"])
def test_recaptcha_v2_widget_errors_show_the_message(browser, callback):
    page, _ = open_challenge(browser, "recaptcha-classic", only("onv2Callback", recaptcha_stub("onv2Callback")))
    try:
        page.wait_for_function("() => window.__opts")
        page.evaluate(f"window.__opts[{callback!r}]()")
        assert_recovery(page)
    finally:
        page.close()


def test_recaptcha_v3_execute_failure_shows_the_message(browser):
    page, _ = open_challenge(browser, "recaptcha-classic", only("onv3Callback", recaptcha_stub("onv3Callback", "Promise.reject(new Error('x'))")))
    try:
        page.locator("#recaptcha-verify").click()
        assert_recovery(page)
    finally:
        page.close()


@pytest.mark.parametrize("callback", ["error-callback", "expired-callback"])
def test_recaptcha_enterprise_widget_errors_show_the_message(browser, callback):
    page, _ = open_challenge(browser, "recaptcha-enterprise", only("onVisibleCallback", recaptcha_stub("onVisibleCallback")))
    try:
        page.wait_for_function("() => window.__opts")
        page.evaluate(f"window.__opts[{callback!r}]()")
        assert_recovery(page)
    finally:
        page.close()


def test_recaptcha_enterprise_invisible_execute_failure_shows_the_message(browser):
    page, _ = open_challenge(
        browser,
        "recaptcha-enterprise",
        only("onInvisibleCallback", recaptcha_stub("onInvisibleCallback", "Promise.reject(new Error('x'))")),
    )
    try:
        assert_recovery(page)
    finally:
        page.close()
