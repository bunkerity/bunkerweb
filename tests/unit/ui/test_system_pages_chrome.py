"""System-group page-head adoption (Pro / Support / About): each page swaps the legacy
dashboard shell breadcrumb+mode row for the shared ``components/page-head.html`` band
(breadcrumb "System / <page>" + bare H1). Support additionally moves its "contact/order"
CTA into the band as a navy ``btn-primary`` (brand rule: green stays reserved for the
explicit PRO-upsell CTA on the Pro page).

Render harness mirrors ``test_templates_gallery.py``'s standalone-Jinja-env pattern.
"""

import re
from pathlib import Path

from conftest import english  # what a converted template renders for a key
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

    assert f'<h1 class="bw-page-head-title mb-0">{english("pro.title")}</h1>' in html
    assert f'<span>{english("navigation.system")}</span>' in html
    assert f'<span class="is-current" aria-current="page">{english("navigation.pro")}</span>' in html
    # No page-head actions slot -- the license CTA stays inline in its card (tightly coupled
    # to the status/overlap conditional logic), untouched.
    assert "bw-page-head-actions" not in html
    # Explicit PRO-upsell CTA keeps its sanctioned green accent (brand rule exception).
    assert "btn-pro-now" in html
    assert english("pro.button.upgrade_to_pro") in html


def test_pro_page_offers_a_local_ui_plugin_refresh_without_a_download():
    html = _render_dashboard_page("pro.html", **_pro_context())

    assert 'action="/pro/refresh-ui"' in html
    assert english("button.refresh_ui_plugins") in html
    assert english("tooltip.button.refresh_ui_plugins") in html


def test_support_page_head_moves_cta_to_navy_primary_and_drops_link_card():
    html = _render_dashboard_page(
        "support.html",
        services=["svc-a"],
        is_pro_version=False,
        pro_status="inactive",
    )

    assert f'<h1 class="bw-page-head-title mb-0">{english("support.title")}</h1>' in html
    assert f'<span class="is-current" aria-current="page">{english("navigation.support")}</span>' in html
    assert "bw-page-head-actions" in html
    # CTA fully swapped to navy -- this is not the "Upgrade to PRO" upsell CTA.
    assert "btn-pro-now" not in html
    assert "btn-primary btn-sm don-jose" in html
    assert english("button.open_support_ticket") in html
    # PRO badge preserved as a decoration next to the CTA, not on the CTA itself.
    assert english("plan.pro") in html
    # The now-empty "Support Link" card is gone; its column neighbours reclaim the row.
    assert english("support.card.support_link.title") not in html
    assert "col-xl-3" not in html and "col-xl-5" not in html
    assert "col-6 col-xl-4" in html and "col-6 col-xl-8" in html
    # Orientation subtitle paragraph dropped -- the kit's bare-H1 head has no subtitle slot.
    assert "support.subtitle" not in html


def test_about_page_head_band_has_bare_title_and_no_actions_slot():
    html = _render_dashboard_page("about.html", bw_version="1.7.0")

    assert f'<h1 class="bw-page-head-title mb-0">{english("about.title")}</h1>' in html
    assert f'<span class="is-current" aria-current="page">{english("navigation.about")}</span>' in html
    assert "bw-page-head-actions" not in html


def _github_link(html):
    """The repository link's own opening tag.

    Scoped deliberately: asserting `"aria-label" not in <the whole page>` passes only by accident
    today and would break the moment any other control on the page grows one. The `"` after the
    repository name keeps this off the LICENSE link further down, which is a longer URL.
    """
    match = re.search(r'<a\b[^>]*href="https://github\.com/bunkerity/bunkerweb"[^>]*>', html)
    assert match, "the GitHub link is no longer on the about page"
    return match.group(0)


def test_the_github_link_states_the_star_count_in_its_accessible_name():
    """The reason the vendored github-buttons widget was removed: its label sat in a closed shadow
    root, so no translation could reach it and the count was announced as bare digits.

    Both branches matter and only one is reachable from the test above, which renders with no count.
    Every string here is derived from the catalog rather than written out -- a test that hardcodes
    English copy stops testing anything the day someone rewords the key, and stops *silently*,
    which is the wrong direction to fail in.
    """
    stars = "10.8k"
    label = english("aria.label.github_stars", count=stars)
    page_with_count = _render_dashboard_page("about.html", bw_version="1.7.0", github_stars=stars)
    page_without_count = _render_dashboard_page("about.html", bw_version="1.7.0", github_stars=None)

    assert stars in label, "aria.label.github_stars no longer interpolates its count"
    assert f'aria-label="{label}"' in _github_link(page_with_count)
    # A placeholder mismatch between the JSON catalog and the compiled PO renders the literal
    # instead of the number, and reads as plausible markup until a screen reader announces it.
    assert "%(count)s" not in page_with_count and "{{count}}" not in page_with_count

    # No count (GitHub unreachable, or a fresh boot before the first refresh) degrades to a plain
    # link rather than to an accessible name ending in "None".
    assert "aria-label" not in _github_link(page_without_count)
    assert english("button.github_stars") in page_without_count

    # The widget it replaces is gone from every page, and with it the browser's call to GitHub.
    assert "github-button" not in page_with_count
