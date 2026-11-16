"""Trial prospects need the checkout payment-method instruction on every entry page."""

import pytest

from test_auth_shell import _render
from test_system_pages_chrome import _pro_context, _render_dashboard_page


@pytest.mark.parametrize("page", ["starting", "loading", "setup", "pro"])
def test_trial_entry_page_renders_the_checkout_payment_method(page):
    if page == "pro":
        html = _render_dashboard_page("pro.html", **_pro_context())
    else:
        html = _render(f"{page}.html")

    assert "Free 30 Days Trial" in html
    assert "pro.free_trial_hint" not in html
    if page in ("starting", "loading"):
        assert 'href="https://panel.bunkerweb.io/store/bunkerweb-pro?' in html
        assert "&lt;a " not in html
