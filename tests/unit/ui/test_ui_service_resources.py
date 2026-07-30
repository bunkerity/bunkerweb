"""Service page resources band: route contract + the band partial's DOM contract."""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


@pytest.fixture(scope="module")
def services_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = Mock()
    # services.py imports from routes.configs, which itself needs these two (unused by
    # services.py's own routes) to import cleanly.
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    # services.py -> app.routes.configs -> app.routes.utils imports qrcode.main.QRCode,
    # unavailable in the pared-down unit-test venv (same stub as test_templates_gallery.py).
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._services_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "services.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client


def test_new_service_does_not_query_resources(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    result = module.build_service_attachments("new")
    assert result["upstream"]["items"] == []
    client.get_upstreams.assert_not_called()


def test_attachments_shape_is_per_family(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.get_upstreams.return_value = {"upstreams": [{"id": "u1", "name": "pool-a"}]}
    client.get_certificates.return_value = {"certificates": []}
    client.get_redirects.return_value = {"redirects": []}
    client.get_workflows.return_value = {"workflows": []}
    result = module.build_service_attachments("app.example.com")
    assert set(result) == {"upstream", "certificate", "redirect", "workflow"}
    assert result["upstream"]["items"][0]["name"] == "pool-a"


# --------------------------------------------------------------------------------------
# models/service_resources_band.html -- the DOM contract Tasks 4 and 5 bind to.
#
# The partial reads ``service_id``, ``attachments`` and (since Task 5's attach modal)
# ``attach_candidates``, plus calls ``csrf_token()`` for the modal's hidden field. It
# renders straight off a plain FileSystemLoader with a stubbed ``csrf_token`` global --
# no dashboard.html stub or other app globals needed (unlike the full-page renders in
# test_row_actions.py / test_home_components.py).
# --------------------------------------------------------------------------------------

_FAMILIES = ("upstream", "certificate", "redirect", "workflow")


def _empty_attachments():
    return {family: {"items": [], "error": None} for family in _FAMILIES}


def _render_band(service_id, attachments, attach_candidates=None, is_readonly=False):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals["csrf_token"] = lambda: "test-csrf-token"
    # The attach modal's form action now goes through url_for (I1's fix) instead of a
    # hardcoded string, so the raw FileSystemLoader environment needs a stand-in --
    # Flask's app-bound url_for is not available outside a request/app context.
    env.globals["url_for"] = lambda endpoint, **kwargs: f"/services/{kwargs.get('service', '')}/resources/attach"
    return env.get_template("models/service_resources_band.html").render(
        service_id=service_id,
        attachments=attachments,
        attach_candidates=attach_candidates if attach_candidates is not None else {},
        is_readonly=is_readonly,
    )


def _family_block(html, family):
    """Slice out one family column's own markup, from its opening tag up to the next
    family's opening tag (or the end of the html for the last family). Marker-relative
    slicing keeps the assertion insensitive to prettier's exact indentation/wrapping."""
    marker = f'resource-family" data-family="{family}"'
    start = html.index(marker) + len(marker)
    rest = html[start:]
    end = len(rest)
    for other in _FAMILIES:
        if other == family:
            continue
        other_idx = rest.find(f'resource-family" data-family="{other}"')
        if other_idx != -1:
            end = min(end, other_idx)
    return rest[:end]


def test_band_renders_families_and_chip_for_attached_resource():
    attachments = _empty_attachments()
    # Real shape from db_methods/upstreams.py's _upstream_dict: the per-service paths are
    # nested under "services", never a top-level "match_path" (see the two-path test below).
    attachments["upstream"]["items"] = [{"id": "u1", "name": "pool-a", "services": [{"service_id": "app.example.com", "match_path": "/"}]}]

    html = _render_band("app.example.com", attachments)

    assert 'id="service-resources-band"' in html
    for family in _FAMILIES:
        assert f'class="col-12 col-md-6 col-xl-3 resource-family" data-family="{family}"' in html

    # the attached row's chip carries both data-family and data-resource-id, in the
    # template's own attribute order (class, then data-family, then data-resource-id).
    assert re.search(r'class="resource-chip[^"]*"\s+data-family="upstream"\s+data-resource-id="u1"', html)

    # the detach button's accessible name comes from aria-label (i18n.js redirects
    # data-i18n into an existing [aria-label] rather than overwriting textContent),
    # not from the bare "x" glyph -- which stays out of the accessible name behind
    # aria-hidden. No stale title/data-i18n-title pair left behind either.
    detach_button = re.search(r"<button[^>]*\bdetach-resource\b[^>]*>", html).group(0)
    assert 'aria-label="Detach"' in detach_button
    assert 'data-i18n="service.resources.detach"' in detach_button
    assert "title=" not in detach_button
    assert "data-i18n-title" not in detach_button
    assert '<span aria-hidden="true">&times;</span>' in html


def test_band_absent_entirely_on_new_service_page():
    html = _render_band("", _empty_attachments())

    assert html.strip() == ""
    assert "service-resources-band" not in html


def test_band_shows_unavailable_state_for_a_failed_family_not_the_empty_state():
    attachments = _empty_attachments()
    attachments["redirect"]["error"] = "boom"

    html = _render_band("app.example.com", attachments)

    redirect_block = _family_block(html, "redirect")
    assert 'data-i18n="service.resources.unavailable"' in redirect_block
    assert 'data-i18n="service.resources.none"' not in redirect_block

    # the other, unaffected families still show the plain empty state.
    for family in ("upstream", "certificate", "workflow"):
        block = _family_block(html, family)
        assert 'data-i18n="service.resources.none"' in block
        assert 'data-i18n="service.resources.unavailable"' not in block


def test_upstream_attached_at_two_paths_renders_two_chips_with_distinct_match_paths():
    """I2: an upstream row nests its paths under "services" -- one chip per attachment
    is what makes per-path detach possible. Feeding a top-level match_path (the old
    fixture shape) is a value the real API never produces and would certify a dead wire."""
    attachments = _empty_attachments()
    attachments["upstream"]["items"] = [
        {
            "id": "u1",
            "name": "pool-a",
            "services": [
                {"service_id": "app.example.com", "match_path": "/api"},
                {"service_id": "app.example.com", "match_path": "/admin"},
                # A different service's attachment on the same pool must not leak a
                # third chip into app.example.com's column.
                {"service_id": "other.example.com", "match_path": "/"},
            ],
        }
    ]

    html = _render_band("app.example.com", attachments)
    upstream_block = _family_block(html, "upstream")

    match_paths = re.findall(r'data-match-path="([^"]*)"', upstream_block)
    assert sorted(match_paths) == ["/admin", "/api"]
    # two chips, both for the same pool -- detach must be scoped by match_path, not id.
    assert upstream_block.count('class="resource-chip') == 2


def test_band_hides_attach_and_detach_controls_when_readonly():
    """I3: is_readonly must hide both the per-family Attach button and every chip's
    detach "x", matching upstreams.html's own readonly gating."""
    attachments = _empty_attachments()
    attachments["upstream"]["items"] = [{"id": "u1", "name": "pool-a", "services": [{"service_id": "app.example.com", "match_path": "/"}]}]

    html = _render_band("app.example.com", attachments, is_readonly=True)

    # the Attach button's own class list ends in "attach-resource" -- the modal's
    # unrelated ids ("attach-resource-modal", "attach-resource-id") don't match this
    # exact suffix, so this stays a precise check for the button itself.
    assert 'attach-resource"' not in html
    assert 'detach-resource"' not in html
    # the chip itself, and the resource's name, must still render -- readonly hides
    # the controls, not the data.
    assert 'data-resource-id="u1"' in html
    assert "pool-a" in html

    # and the same content rendered non-readonly does have both controls, so this test
    # is actually exercising the gate rather than a template that never renders them.
    live_html = _render_band("app.example.com", attachments, is_readonly=False)
    assert 'attach-resource"' in live_html
    assert 'detach-resource"' in live_html


# --------------------------------------------------------------------------------------
# services_resource_detach / detach_service_resource -- Task 4.
# --------------------------------------------------------------------------------------

DETACH_METHODS = {
    "upstream": "detach_upstream",
    "certificate": "detach_certificate",
    "redirect": "detach_redirect",
    "workflow": "detach_workflow",
}


@pytest.mark.parametrize("family,method_name", sorted(DETACH_METHODS.items()))
def test_detach_calls_the_right_client_method(services_route, family, method_name):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.detach_service_resource("app.example.com", family, "r1", "")
    mock_method = getattr(client, method_name)
    if family == "upstream":
        # upstream also threads match_path through as a keyword arg.
        mock_method.assert_called_once_with("r1", "app.example.com", match_path="")
    else:
        mock_method.assert_called_once_with("r1", "app.example.com")


def test_detach_passes_match_path_for_upstreams(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.detach_service_resource("app.example.com", "upstream", "u1", "/api")
    client.detach_upstream.assert_called_once_with("u1", "app.example.com", match_path="/api")


def test_detach_rejects_an_unknown_family(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    with pytest.raises(ValueError):
        module.detach_service_resource("app.example.com", "not-a-family", "x1", "")
    client.detach_upstream.assert_not_called()


def test_detach_refuses_in_readonly_mode(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = True
    with pytest.raises(PermissionError):
        module.detach_service_resource("app.example.com", "redirect", "r1", "")
    client.detach_redirect.assert_not_called()


# --------------------------------------------------------------------------------------
# services_resource_attach / attach_service_resource -- Task 5.
# --------------------------------------------------------------------------------------

ATTACH_METHODS = {
    "upstream": "attach_upstream",
    "certificate": "attach_certificate",
    "redirect": "attach_redirect",
    "workflow": "attach_workflow",
}


@pytest.mark.parametrize("family,method_name", sorted(ATTACH_METHODS.items()))
def test_attach_calls_the_right_client_method(services_route, family, method_name):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.attach_service_resource("app.example.com", family, "r1", match_path="/api", primary=True)
    mock_method = getattr(client, method_name)
    # Assert the actual arguments threaded through, not just that some call happened:
    # only upstream gets match_path, only certificate gets primary, the rest get neither.
    if family == "upstream":
        mock_method.assert_called_once_with("r1", "app.example.com", match_path="/api")
    elif family == "certificate":
        mock_method.assert_called_once_with("r1", "app.example.com", primary=True)
    else:
        mock_method.assert_called_once_with("r1", "app.example.com")


def test_attach_upstream_sends_match_path(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.attach_service_resource("app.example.com", "upstream", "u1", match_path="/api", primary=False)
    assert client.attach_upstream.call_args.kwargs["match_path"] == "/api"


def test_attach_upstream_defaults_empty_match_path_to_root(services_route):
    # The API's attach schema requires a non-empty match_path (min_length=1, unlike
    # detach where empty means "every path"), so an empty form value must be coerced
    # to "/" here rather than forwarded as-is and rejected with a 422.
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.attach_service_resource("app.example.com", "upstream", "u1", match_path="", primary=False)
    assert client.attach_upstream.call_args.kwargs["match_path"] == "/"


def test_attach_certificate_sends_primary(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    module.attach_service_resource("app.example.com", "certificate", "c1", match_path="", primary=True)
    assert client.attach_certificate.call_args.kwargs["primary"] is True


def test_attach_rejects_unknown_family_and_readonly(services_route):
    module, client = services_route
    client.reset_mock(side_effect=True)
    client.readonly = False
    with pytest.raises(ValueError):
        module.attach_service_resource("app.example.com", "nope", "x", match_path="", primary=False)
    # An unknown family must never reach any client method -- not just "raised".
    client.attach_upstream.assert_not_called()
    client.attach_certificate.assert_not_called()
    client.attach_redirect.assert_not_called()
    client.attach_workflow.assert_not_called()

    client.readonly = True
    with pytest.raises(PermissionError):
        module.attach_service_resource("app.example.com", "redirect", "r1", match_path="", primary=False)
    # Readonly must raise before any client call, not merely surface an error after one.
    client.attach_redirect.assert_not_called()


def test_band_failure_does_not_break_the_page_context(services_route):
    """A dead resource API must not stop the settings page from rendering."""
    module, client = services_route
    client.reset_mock(side_effect=True)
    from app.api_client import ApiUnavailableError

    for getter in ("get_upstreams", "get_certificates", "get_redirects", "get_workflows"):
        getattr(client, getter).side_effect = ApiUnavailableError("api down")

    result = module.build_service_attachments("app.example.com")
    assert set(result) == {"upstream", "certificate", "redirect", "workflow"}
    assert all(entry["items"] == [] for entry in result.values())
    assert all(entry["error"] for entry in result.values())
