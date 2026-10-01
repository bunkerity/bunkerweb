"""C2/decision 7: the CrowdSec page had no sidebar entry at all (QA-UI-3). It now sits in the
`menu.html` Overview group like every other core page (`navigation.crowdsec` already existed in
`en.json`), and `main.py` no longer also seeds it into the generic Extra Pages fallback -- that
seed is what gave it a second, mis-titled entry the moment the first one was added.
"""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"

STUBS = {
    "base.html": "{% block head %}{% endblock %}{% block page %}{% endblock %}",
}


def _render_menu(extra_pages=(), plugins=None):
    loaders = [DictLoader(STUBS), FileSystemLoader(TEMPLATES)]
    env = Environment(loader=ChoiceLoader(loaders), autoescape=True, undefined=ChainableUndefined)
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + "/".join([endpoint, *(str(v) for v in kwargs.values())]),
        endpoint_exists=lambda endpoint: False,
        request=SimpleNamespace(path="/home"),
    )
    return env.get_template("menu.html").render(
        theme="light",
        bw_version="1.7.0",
        current_endpoint="home",
        plugins=plugins or {},
        extra_pages=list(extra_pages),
        is_pro_version=False,
        pro_diamond_url="/d.svg",
    )


def test_crowdsec_has_its_own_overview_entry():
    html = _render_menu()

    assert 'data-tour="nav-crowdsec"' in html
    assert "bx-radar" in html
    assert "/crowdsec.crowdsec_page" in html


def test_crowdsec_is_not_also_seeded_as_a_generic_extra_page():
    """Regression for the duplicate this fix removed: `EXTRA_PAGES` no longer names crowdsec
    (`main.py`), so even if a stale/foreign config passed it in, the real fix is the sidebar
    entry existing at all -- this only pins today's call shape."""
    html = _render_menu(extra_pages=())

    assert html.count('href="/crowdsec') == 1, "the menu-group entry is the only link to the page"


def test_a_stray_extra_pages_entry_would_still_duplicate_it():
    """Documents *why* `main.py` had to stop seeding `EXTRA_PAGES = ["crowdsec"]`: the Extra
    Pages loop renders unconditionally from that list, with no de-dup against menu_groups."""
    html = _render_menu(extra_pages=("crowdsec",))

    assert html.count('href="/crowdsec') >= 2
