"""Threatmap page: the gate, the error mapping, and the template's two shapes.

The page itself is drawn client-side, so what the Flask layer decides is narrow but load-bearing:
whether there is anything to draw at all (``METRICS_PERSIST_TO_DB``), whether a bad window is
told apart from a dead API, and whether the shell it renders carries the hooks threatmap.js
looks for. A template that renders but whose ids drifted is a blank page with a green test.
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from conftest import english  # what a converted template renders for a key
import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.api_client import ApiClient, ApiClientError, ApiUnavailableError

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"
STATIC = ROOT / "src" / "ui" / "app" / "static"

EPOCH = 1704067200
DAY = 86400

PAYLOAD = {
    "status": "success",
    "count": 3,
    "by_country": [{"name": "US", "count": 2}, {"name": "local", "count": 1}],
    "by_server": [{"name": "app.example.com", "count": 3}],
    "by_reason": [{"name": "blacklist", "count": 3}],
    "recent": [{"request_id": "r1", "country": "US", "ip": "1.2.3.4", "reason": "blacklist", "server_name": "app.example.com", "date": EPOCH}],
}


@pytest.fixture(scope="module")
def threatmap_module():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.LOGGER = Mock()
    # reports.py owns the METRICS_PERSIST_TO_DB probe (and its 30s cache); threatmap reuses it
    # rather than keeping a second copy of the same config read.
    reports = ModuleType("app.routes.reports")
    reports._persist_to_db_enabled = Mock(return_value=True)
    route_utils = ModuleType("app.routes.utils")
    route_utils.cors_required = lambda function: function

    module_name = "app.routes._threatmap_test"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "src" / "ui" / "app" / "routes" / "threatmap.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "app.utils": app_utils,
        "app.routes.reports": reports,
        "app.routes.utils": route_utils,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, reports._persist_to_db_enabled


@pytest.fixture
def route(threatmap_module):
    module, client, persist = threatmap_module
    client.reset_mock(return_value=True, side_effect=True)
    persist.reset_mock(return_value=True, side_effect=True)
    persist.return_value = True
    client.get_threatmap.return_value = dict(PAYLOAD)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.threatmap)
    return module, client, persist, app


@pytest.fixture(scope="module")
def page():
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "dashboard.html": "{% block page_head %}{% endblock %}{% block head %}{% endblock %}{% block content %}{% endblock %}{% block scripts %}{% endblock %}"
                    }
                ),
                FileSystemLoader(str(TEMPLATES)),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(url_for=lambda endpoint, **kwargs: "/x", csrf_token=lambda: "t")
    return env.get_template("threatmap.html")


def _render(page, **overrides):
    context = {"enabled": True, "recent_limit": 50, "style_nonce": "s", "script_nonce": "j"}
    context.update(overrides)
    return page.render(**context)


class TestData:
    def test_it_forwards_the_window_and_returns_the_payload(self, route):
        module, client, _, app = route

        with app.test_request_context(f"/threatmap/data?start={EPOCH}&end={EPOCH + DAY}"):
            response = module.threatmap_data.__wrapped__()

        assert response.get_json() == PAYLOAD
        assert client.get_threatmap.call_args.kwargs["start"] == EPOCH
        assert client.get_threatmap.call_args.kwargs["end"] == EPOCH + DAY
        # Bounds the payload: one facet row per distinct service means thousands of rows per poll
        # on a large deployment, to render five of them.
        assert client.get_threatmap.call_args.kwargs["facet_limit"] == module.FACET_LIMIT

    def test_persistence_off_is_a_409_not_an_empty_map(self, route):
        """An empty map and a map that is never going to fill look identical to an operator, so
        the page has to be able to tell them apart."""
        module, client, persist, app = route
        persist.return_value = False

        with app.test_request_context(f"/threatmap/data?start={EPOCH}&end={EPOCH + DAY}"):
            response, status = module.threatmap_data.__wrapped__()

        assert status == 409
        assert client.get_threatmap.call_count == 0

    def test_a_non_numeric_window_is_a_400_not_a_500(self, route):
        module, client, _, app = route

        with app.test_request_context("/threatmap/data?start=yesterday&end=now"):
            response, status = module.threatmap_data.__wrapped__()

        assert status == 400
        assert client.get_threatmap.call_count == 0

    def test_a_missing_window_is_a_400_not_a_500(self, route):
        module, _, _, app = route

        with app.test_request_context("/threatmap/data"):
            _, status = module.threatmap_data.__wrapped__()

        assert status == 400

    def test_a_rejected_range_stays_a_400_while_a_dead_api_is_a_503(self, route):
        """Both arrive as ApiClientError. Collapsing them would tell an operator the metrics
        service is down when in fact they asked for a window the API refuses."""
        module, client, _, app = route

        client.get_threatmap.side_effect = ApiClientError("window too large", status_code=400)
        with app.test_request_context(f"/threatmap/data?start={EPOCH}&end={EPOCH + DAY}"):
            _, status = module.threatmap_data.__wrapped__()
        assert status == 400

        client.get_threatmap.side_effect = ApiClientError("boom", status_code=404)
        with app.test_request_context(f"/threatmap/data?start={EPOCH}&end={EPOCH + DAY}"):
            _, status = module.threatmap_data.__wrapped__()
        assert status == 503

    def test_an_unreachable_api_is_a_503(self, route):
        module, client, _, app = route
        client.get_threatmap.side_effect = ApiUnavailableError("down")

        with app.test_request_context(f"/threatmap/data?start={EPOCH}&end={EPOCH + DAY}"):
            _, status = module.threatmap_data.__wrapped__()

        assert status == 503


class TestPage:
    def test_the_shell_reports_whether_persistence_is_on(self, route):
        module, _, persist, app = route
        persist.return_value = False

        with app.test_request_context("/threatmap"):
            with patch.object(module, "render_template", Mock(return_value="")) as render:
                module.threatmap_page.__wrapped__()

        assert render.call_args.kwargs["enabled"] is False

    def test_it_carries_every_hook_the_page_script_reaches_for(self, page):
        """threatmap.js addresses the DOM by id. A renamed id fails silently at runtime — the page
        renders, the map just never fills."""
        html = _render(page)
        script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

        for element_id in (
            "threatmap-map",
            "threatmap-tile-count",
            "threatmap-tile-countries",
            "threatmap-tile-target",
            "threatmap-tile-reason",
            "threatmap-ticker",
            "threatmap-top-country",
            "threatmap-top-server",
            "threatmap-top-reason",
            "threatmap-empty",
            "threatmap-error",
        ):
            assert f'id="{element_id}"' in html, element_id
            assert element_id in script, element_id

    def test_the_disabled_state_replaces_the_map_rather_than_sitting_under_it(self, page):
        """With nothing being recorded there is nothing to draw, so booting Leaflet and polling
        an endpoint that answers 409 would be pure noise."""
        html = _render(page, enabled=False)

        assert "threatmap-disabled" in html
        assert 'id="threatmap-map"' not in html
        # url_for is stubbed, so the script tag itself is the observable, not its path.
        assert "__threatmapConfig" not in html

    def test_the_enabled_state_loads_its_libraries_locally(self):
        """The UI's CSP allows no remote host, so a CDN reference is a blank map. Asserted
        against the template source: the test env stubs url_for, so a render carries no paths."""
        source = (TEMPLATES / "threatmap.html").read_text(encoding="utf-8")

        assert "libs/leaflet/leaflet.min.js" in source
        assert "libs/topojson-client/topojson-client.min.js" in source
        assert "components/country-flag.js" in source
        assert "//cdn" not in source

    def test_it_carries_the_wall_display_affordances(self, page):
        """The page is meant to be left running on a screen for days, which needs three things a
        normal page does not: chrome it can drop, a heartbeat, and a way to say it froze."""
        html = _render(page)

        assert 'id="threatmap-board"' in html  # what goes fullscreen — not the whole document
        assert 'id="threatmap-fullscreen"' in html
        assert 'id="threatmap-updated-time"' in html
        assert 'id="threatmap-stale"' in html

    def test_the_wall_display_hooks_are_the_ones_the_script_drives(self, page):
        script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

        for element_id in ("threatmap-board", "threatmap-fullscreen", "threatmap-updated", "threatmap-updated-time", "threatmap-stale"):
            assert element_id in script, element_id

    def test_an_expired_session_reloads_instead_of_freezing(self):
        """Flask-Login answers an expired session with a redirect to the login page, so the fetch
        comes back 200-with-HTML. Left unhandled, a display parked overnight sits on a stuck error
        panel forever instead of showing a login screen someone can act on."""
        script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

        assert "response.redirected" in script
        assert "window.location.reload()" in script

    def test_the_reload_is_rate_limited_across_documents(self):
        """A reload wipes every in-page guard, so an unconditional one turns any persistent
        redirect into an endless reload loop on a screen nobody is standing in front of. The
        limiter therefore has to live in sessionStorage, not in a variable."""
        script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

        assert "sessionStorage" in script
        # Only an auth redirect reloads. A proxy 502 in front of the UI is also not JSON, and
        # reloading on that would loop against a service that is already down.
        assert 'indexOf("json")' not in script

    def test_the_freshness_stamp_ages_without_a_successful_fetch(self):
        """If staleness were only recomputed on a successful poll, the one case it exists for —
        polls that stopped succeeding — would never mark the board stale."""
        script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

        assert "setInterval(paintFreshness" in script

    def test_it_says_the_map_is_delayed_rather_than_live(self, page):
        """Freshness is bounded by the once-a-minute scrape job. Calling it live is a claim an
        operator could act on during an incident."""
        assert english("threatmap.freshness") in _render(page)


def test_the_client_calls_the_single_round_trip_endpoint():
    client = ApiClient("http://api.test", "token")
    try:
        client._get = Mock(return_value=PAYLOAD)
        client.get_threatmap(start=EPOCH, end=EPOCH + DAY)
        assert client._get.call_args.args[0] == "/metrics/threatmap"
        assert client._get.call_args.kwargs["params"]["start"] == EPOCH
    finally:
        client.session.close()


class TestChoroplethBands:
    """The one piece of real algorithm on the page, executed rather than grepped.

    Same trick ``tests/unit/metrics/test_metrics_timings.py`` uses for pure Lua: pull the function
    out of the shipped file and run it under the real interpreter, so the test cannot drift from
    the source it claims to cover.
    """

    @staticmethod
    def _bands(values):
        node = shutil.which("node")
        if not node:
            pytest.skip("node is not available")
        source = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")
        match = re.search(r"function computeThresholds\(values\) \{.*?\n  \}", source, re.S)
        assert match, "computeThresholds not found — the extraction regex needs updating"

        script = match.group(0) + """
var palette = { steps: [0, 0, 0, 0, 0] };
function stepFor(count, thresholds) {
  var index = 0;
  while (index < thresholds.length && count >= thresholds[index]) index++;
  return Math.min(palette.steps.length - 1, index);
}
var values = %s;
var cuts = computeThresholds(values);
console.log(JSON.stringify({cuts: cuts, steps: values.map(function (v) { return stepFor(v, cuts); })}));
""" % json.dumps(values)
        out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    def test_the_busiest_country_never_shares_the_top_band(self):
        """The whole point of the map. A quantile split collapses on ties and puts the worst
        offender in with the quiet ones; log bands leave it alone at the top."""
        result = self._bands([8, 3, 3, 3, 3, 2])

        assert result["steps"][0] == 4
        assert max(result["steps"][1:]) < 4

    def test_a_power_law_still_separates_the_middle(self):
        """One country at 9000 and the rest in single digits is the normal shape of attack
        traffic. Against count/max every one of the others lands in the base band."""
        result = self._bands([9000, 12, 7, 3, 1])

        assert result["steps"][0] == 4
        assert len(set(result["steps"][1:])) > 1, "the tail collapsed into a single band"

    def test_uniform_traffic_produces_one_band(self):
        result = self._bands([5, 5, 5, 5])

        assert len(set(result["steps"])) == 1

    def test_a_single_hit_everywhere_needs_no_bands(self):
        """With nothing to distinguish, inventing five shades would be noise."""
        result = self._bands([1, 1, 1])

        assert result["cuts"] == []
        assert set(result["steps"]) == {0}

    def test_bands_are_strictly_increasing(self):
        """Two identical cuts would render two legend rows covering the same range."""
        cuts = self._bands([40, 9, 9, 4, 2, 1])["cuts"]

        assert cuts == sorted(set(cuts))


def test_the_page_is_reachable_from_the_menu_and_from_the_home_map():
    """Two entry points were the point: the home map stays the history view and hands off to the
    live one, and the menu covers anyone who never scrolls to it."""
    assert "threatmap.threatmap_page" in (TEMPLATES / "menu.html").read_text(encoding="utf-8")
    assert "url_for('threatmap')" in (TEMPLATES / "home.html").read_text(encoding="utf-8")


def test_every_i18n_key_the_page_uses_exists_in_english():
    """data-i18n keys are looked up at runtime; a missing one renders the raw key to the user."""
    import json
    import re

    html = (TEMPLATES / "threatmap.html").read_text(encoding="utf-8")
    script = (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")
    english = json.loads((STATIC / "locales" / "en.json").read_text(encoding="utf-8"))

    keys = set(re.findall(r'data-i18n="(threatmap\.[a-z_]+)"', html))
    keys |= set(re.findall(r'"(threatmap\.[a-z_]+)"', html + script))
    keys |= {"breadcrumb.threatmap", "navigation.threatmap"}
    assert keys, "no threatmap i18n keys found — the scan is broken, not the page"

    for key in keys:
        namespace, _, leaf = key.partition(".")
        assert leaf in english.get(namespace, {}), key


class TestExpandableTops:
    """The panels show five rows and can be expanded to whatever the route fetched.

    The failure this guards is silent: a panel that truncates without saying so reads as "these
    are all the services that were hit", which is a wrong answer to the only question the panel
    exists to answer.
    """

    @staticmethod
    def _script():
        return (STATIC / "js" / "pages" / "threatmap.js").read_text(encoding="utf-8")

    def test_a_truncated_panel_offers_a_way_to_see_the_rest(self):
        script = self._script()

        assert "threatmap.show_more" in script
        assert "threatmap.show_less" in script

    def test_it_says_how_many_rows_the_payload_itself_is_hiding(self):
        """``facet_limit`` truncates server-side too, so "show more" can still be short of the
        truth. ``distinct`` is what lets the panel admit that rather than imply completeness."""
        script = self._script()

        assert "threatmap.more_hidden" in script
        assert "distinct" in script

    def test_the_toggle_is_a_button_that_reports_its_state(self):
        """A div with a click handler is invisible to a screen reader and unreachable by keyboard;
        aria-expanded is what makes the collapsed state audible."""
        script = self._script()

        assert 'createElement("button")' in script
        assert "aria-expanded" in script

    def test_the_toggle_keeps_keyboard_focus_across_the_re_render(self):
        """Expanding rebuilds the list, which detaches the button that was clicked. Without an
        explicit restore, focus falls to <body> and a keyboard user is thrown back to the top of
        the document every time they open a panel."""
        script = self._script()

        assert ".focus()" in script

    def test_the_hidden_count_is_shown_collapsed_too(self):
        """ "Show all 25" is a false promise when the payload was capped at 25 of 30, and the
        operator needs to know that before they open the list, not after."""
        script = self._script()

        # Guards the regression directly: the note used to be gated on the expanded state.
        assert "if (open && distinct" not in script

    def test_the_three_new_keys_ship_in_every_locale(self):
        """The parity test would catch a missing key, but not one added to en.json alone in a way
        that leaves 17 languages rendering a raw i18n path."""
        for locale in sorted((STATIC / "locales").glob("*.json")):
            keys = json.loads(locale.read_text(encoding="utf-8")).get("threatmap", {})
            missing = {"show_more", "show_less", "more_hidden"} - set(keys)
            assert not missing, f"{locale.name} is missing {sorted(missing)}"
