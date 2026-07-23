"""System-group page-head adoption (Pro / Support / About): each page swaps the legacy
dashboard shell breadcrumb+mode row for the shared ``components/page-head.html`` band
(breadcrumb "System / <page>" + bare H1). Support additionally moves its "contact/order"
CTA into the band as a navy ``btn-primary`` (brand rule: green stays reserved for the
explicit PRO-upsell CTA on the Pro page).

Render harness mirrors ``test_templates_gallery.py``'s standalone-Jinja-env pattern.
"""

from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def _render_dashboard_page(template, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(
        csrf_token=lambda: "test-token",
        url_for=lambda endpoint, **_kwargs: f"/{endpoint}",
    )
    return env.get_template(template).render(**context)


def _pro_context(**overrides):
    context = dict(
        pro_status="inactive",
        pro_overlapped=False,
        is_pro_version=False,
        online_services=0,
        pro_services=0,
        draft_services=0,
        pro_expire="",
        pro_expires_in="Unknown",
        pro_license_key="",
        is_readonly=False,
        user_readonly=False,
    )
    context.update(overrides)
    return context


def test_pro_page_head_band_has_system_breadcrumb_and_keeps_green_upsell_cta():
    html = _render_dashboard_page("pro.html", **_pro_context())

    assert '<h1 class="bw-page-head-title mb-0" data-i18n="pro.title">Pro license</h1>' in html
    assert '<span data-i18n="navigation.system">System</span>' in html
    assert '<span class="is-current" aria-current="page" data-i18n="navigation.pro">Pro</span>' in html
    # No page-head actions slot -- the license CTA stays inline in its card (tightly coupled
    # to the status/overlap conditional logic), untouched.
    assert "bw-page-head-actions" not in html
    # Explicit PRO-upsell CTA keeps its sanctioned green accent (brand rule exception).
    assert "btn-pro-now" in html
    assert 'data-i18n="pro.button.upgrade_to_pro"' in html


def test_support_page_head_moves_cta_to_navy_primary_and_drops_link_card():
    html = _render_dashboard_page(
        "support.html",
        services=["svc-a"],
        is_pro_version=False,
        pro_status="inactive",
    )

    assert '<h1 class="bw-page-head-title mb-0" data-i18n="support.title">Support</h1>' in html
    assert '<span class="is-current" aria-current="page" data-i18n="navigation.support">Support</span>' in html
    assert "bw-page-head-actions" in html
    # CTA fully swapped to navy -- this is not the "Upgrade to PRO" upsell CTA.
    assert "btn-pro-now" not in html
    assert "btn-primary btn-sm don-jose" in html
    assert 'data-i18n="button.open_support_ticket">Open a Support Ticket' in html
    # PRO badge preserved as a decoration next to the CTA, not on the CTA itself.
    assert 'data-i18n="plan.pro"' in html
    # The now-empty "Support Link" card is gone; its column neighbours reclaim the row.
    assert "support.card.support_link.title" not in html
    assert "col-xl-3" not in html and "col-xl-5" not in html
    assert "col-6 col-xl-4" in html and "col-6 col-xl-8" in html
    # Orientation subtitle paragraph dropped -- the kit's bare-H1 head has no subtitle slot.
    assert "support.subtitle" not in html


def test_about_page_head_band_has_bare_title_and_no_actions_slot():
    html = _render_dashboard_page("about.html", bw_version="1.7.0")

    assert '<h1 class="bw-page-head-title mb-0" data-i18n="about.title">About BunkerWeb</h1>' in html
    assert '<span class="is-current" aria-current="page" data-i18n="navigation.about">About</span>' in html
    assert "bw-page-head-actions" not in html
