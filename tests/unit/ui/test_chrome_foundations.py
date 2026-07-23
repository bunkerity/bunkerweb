"""Round-3 systemic chrome foundations: the shared page-head band
(``components/page-head.html``), the KPI ``tile`` restyle and the ``card`` panel-header
option. Render tests follow ``test_ui_components.py``'s standalone-Jinja-env pattern.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def _env():
    return Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)


# --------------------------------------------------------------------------------------
# page_head macro
# --------------------------------------------------------------------------------------
def _render_page_head(body, call=False):
    if call:
        source = '{% from "components/page-head.html" import page_head %}' f'{{% call {body} %}}<button id="act">Go</button>{{% endcall %}}'
    else:
        source = '{% from "components/page-head.html" import page_head %}' f"{{{{ {body} }}}}"
    return _env().from_string(source).render()


def test_page_head_renders_bare_h1_without_icon_or_subtitle():
    html = _render_page_head('page_head(title="Service templates", title_i18n="templates.title")')

    assert '<h1 class="bw-page-head-title mb-0" data-i18n="templates.title">Service templates</h1>' in html
    # Bare H1: no leading icon, no subtitle paragraph in the head band.
    assert "bx-" not in html.split("</h1>")[0]
    assert "page-head-subtitle" not in html


def test_page_head_breadcrumb_marks_last_crumb_current_and_links_earlier_ones():
    html = _render_page_head(
        'page_head(title="T", breadcrumb=['
        '("Configure", "navigation.configure", none), '
        '("Detail", "d.key", "/detail"), '
        '("Templates", "navigation.templates", none)])'
    )

    # Plain text crumb (no url) -> span; url crumb -> link; last -> current, no link.
    assert '<span data-i18n="navigation.configure">Configure</span>' in html
    assert '<a href="/detail" data-i18n="d.key">Detail</a>' in html
    assert '<span class="is-current" aria-current="page" data-i18n="navigation.templates">Templates</span>' in html
    # Two separators for three crumbs.
    assert html.count('<span class="sep" aria-hidden="true">/</span>') == 2


def test_page_head_omits_crumb_nav_when_no_breadcrumb():
    html = _render_page_head('page_head(title="T")')

    assert "bw-page-head-crumbs" not in html
    assert 'aria-label="Breadcrumb"' not in html


def test_page_head_actions_slot_renders_only_when_called():
    without = _render_page_head('page_head(title="T")')
    assert "bw-page-head-actions" not in without

    withcall = _render_page_head('page_head(title="T")', call=True)
    assert "bw-page-head-actions" in withcall
    assert '<button id="act">Go</button>' in withcall


# --------------------------------------------------------------------------------------
# tile macro (kit .mini-tile restyle)
# --------------------------------------------------------------------------------------
def _render_tile(**params):
    call = ", ".join(f"{key}={value!r}" for key, value in params.items())
    return _env().from_string('{% from "components/tile.html" import tile %}' f"{{{{ tile({call}) }}}}").render()


def test_tile_label_is_uppercase_hook_and_value_keeps_bw_kpi_value_class():
    html = _render_tile(title="Cache enabled", value="4/5", title_i18n="web_cache.enabled_instances")

    assert 'class="bw-kpi-label mb-0"' in html
    # JS (reports-*.js) writes into `.bw-kpi-value`; the class must survive byte-for-byte.
    assert 'class="don-jose bw-kpi-value"' in html
    assert ">4/5</span>" in html
    # Restyle killed the accent top-border wrapper markup.
    assert "bw-kpi-tile::before" not in html


def test_tile_i18n_sits_on_inner_span_so_inline_icon_survives_translation():
    html = _render_tile(title="Servers", value="3", title_i18n="tile.servers", icon="bx-server")

    # Icon rendered inline before the label text, i18n on the span (not the <p>).
    assert '<i class="bx bx-server" aria-hidden="true"></i>' in html
    assert '<span data-i18n="tile.servers">Servers</span>' in html
    assert 'data-i18n="tile.servers"><i' not in html


def test_tile_caption_line_is_optional():
    without = _render_tile(title="A", value="1")
    assert "bw-kpi-caption" not in without

    withcap = _render_tile(title="A", value="1", caption="IPs + CIDRs", caption_i18n="tile.cap")
    assert '<small class="bw-kpi-caption d-block" data-i18n="tile.cap">IPs + CIDRs</small>' in withcap


# --------------------------------------------------------------------------------------
# card panel-header option
# --------------------------------------------------------------------------------------
def _render_card(**params):
    call = ", ".join(f"{key}={value!r}" for key, value in params.items())
    return _env().from_string('{% from "components/card.html" import card %}' f"{{% call card({call}) %}}body{{% endcall %}}").render()


def test_card_uppercase_adds_panel_header_classes():
    html = _render_card(title="Requests", title_key="home.requests", subtitle="last 24 h", subtitle_key="home.range", uppercase=True)

    assert "bw-panel-title" in html
    assert "bw-panel-sub" in html


def test_card_header_default_is_unchanged_without_uppercase():
    html = _render_card(title="Requests", title_key="home.requests", subtitle="last 24 h", subtitle_key="home.range")

    assert "bw-panel-title" not in html
    assert "bw-panel-sub" not in html
    assert '<h5 class="card-title mb-0" data-i18n="home.requests">Requests</h5>' in html
