"""Service page resources band: route contract + the band partial's DOM contract."""

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from jinja2 import Environment, FileSystemLoader

from app.models.service_attachments import resource_conflict_context
from app.utils import is_editable_method

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
    # The real one is the image-only /usr/share/bunkerweb/core; point it at the repo so
    # `core_plugin_order()` reads the SHIPPED order.json instead of falling back to {}.
    dependencies.CORE_PLUGINS_PATH = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
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


def _render_band(
    service_id,
    attachments,
    attach_candidates=None,
    is_readonly=False,
    templates=None,
    config=None,
    resource_conflicts=None,
):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals["csrf_token"] = lambda: "test-csrf-token"
    # The attach modal's form action now goes through url_for (I1's fix) instead of a
    # hardcoded string, so the raw FileSystemLoader environment needs a stand-in --
    # Flask's app-bound url_for is not available outside a request/app context.
    env.globals["url_for"] = lambda endpoint, **kwargs: f"/services/{kwargs.get('service', '')}/resources/attach"
    # The REAL helper, not a stub: the template family's lock gate hangs off it, and
    # is_editable_method("default") is False unless allow_default is passed -- a stub that
    # returned True would certify a gate that is wrong on every templateless service.
    env.globals["is_editable_method"] = is_editable_method
    return env.get_template("models/service_resources_band.html").render(
        service_id=service_id,
        attachments=attachments,
        attach_candidates=attach_candidates if attach_candidates is not None else {},
        is_readonly=is_readonly,
        templates=templates if templates is not None else {},
        config=config if config is not None else {},
        resource_conflicts=resource_conflicts if resource_conflicts is not None else {},
    )


def _family_block(html, family):
    """Slice out one family column's own markup, from its opening tag up to the next
    family's opening tag (or the end of the html for the last family). Marker-relative
    slicing keeps the assertion insensitive to prettier's exact indentation/wrapping."""
    marker = f'resource-family" data-family="{family}"'
    start = html.index(marker) + len(marker)
    rest = html[start:]
    end = len(rest)
    for other in ("template",) + _FAMILIES:
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
        assert f'class="col-12 col-md-6 col-xl resource-family" data-family="{family}"' in html

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


# --------------------------------------------------------------------------------------
# Task 5 -- resource_conflict_context: the server-side rules, mirrored so the dialog can
# refuse BEFORE the API does. Each assertion below is anchored to the rule it mirrors;
# inventing a rule here would block an attach the API accepts, which is worse than the
# missed warning that omitting one costs.
# --------------------------------------------------------------------------------------


def _attachments(**families):
    entries = _empty_attachments()
    for family, items in families.items():
        entries[family]["items"] = items
    return entries


def test_location_claims_cover_redirects_and_this_services_own_upstream_paths():
    """db_methods/locations.py:53-85 -- a redirect claims its own from_path; an upstream
    claims the match_path of ITS attachment, so another service's attachment on the same
    pool must not leak in."""
    attachments = _attachments(
        redirect=[{"id": "r1", "name": "old-blog", "from_path": "/blog"}],
        upstream=[
            {
                "id": "u1",
                "name": "pool-a",
                "protocol": "http",
                "services": [
                    {"service_id": "app.example.com", "match_path": "/api"},
                    {"service_id": "other.example.com", "match_path": "/leaked"},
                ],
            }
        ],
    )

    paths = resource_conflict_context(attachments, "app.example.com")["paths"]

    assert set(paths) == {"/blog", "/api"}
    assert paths["/blog"] == {"kind": "redirect", "name": "old-blog", "resource_id": "r1"}
    assert paths["/api"] == {"kind": "upstream", "name": "pool-a", "resource_id": "u1"}


def test_a_stream_pool_claims_no_path_but_is_reported_as_the_services_single_backend():
    """locations.py:83 skips stream pools (a stream server has no location), and
    db_methods/upstreams.py:120-133 refuses a SECOND stream pool on the same service."""
    attachments = _attachments(
        upstream=[
            {
                "id": "s1",
                "name": "tcp-pool",
                "protocol": "stream",
                "services": [{"service_id": "app.example.com", "match_path": "/"}],
            }
        ]
    )

    context = resource_conflict_context(attachments, "app.example.com")

    assert context["paths"] == {}, "a stream pool has no location to collide with"
    assert context["stream_upstream"] == {"id": "s1", "name": "tcp-pool"}


def test_location_claims_include_the_services_own_inline_settings():
    """locations.py:102-108 -- the second half of location_conflict. An inline reverse
    proxy takes the path just as hard as an attached pool, and a blanked-out trigger frees
    it again (utils/location_claims.py:48-50)."""
    config = {
        "REVERSE_PROXY_HOST": {"value": "http://backend", "method": "ui"},
        "REVERSE_PROXY_URL": {"value": "/app", "method": "ui"},
        "REVERSE_PROXY_HOST_1": {"value": "", "method": "default"},
        "REVERSE_PROXY_URL_1": {"value": "/disabled", "method": "default"},
    }

    paths = resource_conflict_context(_empty_attachments(), "app.example.com", config)["paths"]

    assert paths["/app"] == {"kind": "inline", "name": "reverse proxy", "resource_id": ""}
    assert "/disabled" not in paths, "a blank trigger frees its path instead of blocking it"


def test_a_template_supplied_reverse_proxy_does_not_invent_a_conflict():
    """The dialog may only mirror refusals the API can actually make. `inline_family_paths`
    (db_methods/locations.py:24-41) reads Global_values + Services_settings, so a value with no
    stored row is invisible to it -- and a template overlay is exactly that: config_read.py:349-355
    injects template settings at method "default" with `template` set.

    Every shipped template (core/templates/templates/{low,medium,high,api}.json) sets
    REVERSE_PROXY_HOST and REVERSE_PROXY_URL=/, and `low` is the default (service_settings.html:16),
    so claiming these would grey out Attach for the commonest attach there is -- a pool at "/" -- on
    every templated service, for an operation the API accepts."""
    config = {
        "REVERSE_PROXY_HOST": {"value": "http://upstream-server:8080", "method": "default", "template": "low"},
        "REVERSE_PROXY_URL": {"value": "/", "method": "default", "template": "low"},
    }

    assert resource_conflict_context(_empty_attachments(), "app.example.com", config)["paths"] == {}


def test_omitting_the_config_reports_only_the_resource_half():
    """Degradation direction: unwired, the dialog warns about strictly LESS than the API
    refuses. The opposite would block a legal attach."""
    config = {"REVERSE_PROXY_HOST": {"value": "http://backend"}, "REVERSE_PROXY_URL": {"value": "/app"}}
    attachments = _attachments(redirect=[{"id": "r1", "name": "r", "from_path": "/blog"}])

    without = resource_conflict_context(attachments, "app.example.com")["paths"]
    with_config = resource_conflict_context(attachments, "app.example.com", config)["paths"]

    assert set(without) == {"/blog"}
    assert set(with_config) == {"/blog", "/app"}


def test_primary_certificate_is_reported_only_for_this_service():
    """db_methods/certificates.py:588-591 -- attaching a primary certificate clears
    is_primary on the service's other attachments without saying so."""
    attachments = _attachments(
        certificate=[
            {
                "id": "c1",
                "name": "wildcard",
                "attachments": [
                    {"service_id": "app.example.com", "is_primary": True},
                    {"service_id": "other.example.com", "is_primary": False},
                ],
            },
            {"id": "c2", "name": "secondary", "attachments": [{"service_id": "app.example.com", "is_primary": False}]},
        ]
    )

    assert resource_conflict_context(attachments, "app.example.com")["primary_certificate"] == {"id": "c1", "name": "wildcard"}
    # the same rows, read from a service that only holds the NON-primary attachment.
    assert resource_conflict_context(attachments, "other.example.com")["primary_certificate"] is None


def test_a_claim_names_its_owning_resource_so_a_reattach_is_not_a_conflict():
    """location_conflict passes the incoming resource as exclude_resource_id
    (locations.py:96), so re-attaching a pool onto the path it already holds is legal. The
    JS needs the owner id to reproduce that exclusion."""
    attachments = _attachments(upstream=[{"id": "u1", "name": "pool-a", "protocol": "http", "services": [{"service_id": "svc", "match_path": "/api"}]}])

    assert resource_conflict_context(attachments, "svc")["paths"]["/api"]["resource_id"] == "u1"


# --------------------------------------------------------------------------------------
# Task 5 -- the template column. Template is the fifth family and the only one that is not
# an API resource.
# --------------------------------------------------------------------------------------

_TEMPLATES = {"low": {"name": "Low"}, "medium": {"name": "Medium"}, "ui": {"name": "UI"}}


def test_template_column_leads_the_band_and_is_not_a_resource_family():
    html = _render_band(
        "app.example.com",
        _empty_attachments(),
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "low", "method": "ui"}},
    )

    # leading: its column opens before every resource family's.
    template_at = html.index('resource-family" data-family="template"')
    for family in _FAMILIES:
        assert template_at < html.index(f'resource-family" data-family="{family}"')

    # ... and it is NOT wired to the attach/detach routes, whose _ATTACH_METHODS map would
    # reject family=template with "Unknown resource type".
    block = _family_block(html, "template")
    assert "attach-resource" not in block
    assert "detach-resource" not in block


def test_the_template_picker_posts_nothing_itself():
    """USE_TEMPLATE is in the service restore_skip (models/save_scope.py:57) and is never
    restored, so the form must carry EXACTLY one value for it. The compose shelf already
    emits that one input; a second named control here would make "exactly one" depend on
    DOM order between two partials. The picker therefore carries no name at all."""
    html = _render_band(
        "app.example.com",
        _empty_attachments(),
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "low", "method": "ui"}},
    )

    assert 'id="service-template-picker"' in html
    assert "USE_TEMPLATE" not in html
    assert 'name="USE_TEMPLATE"' not in html
    picker = re.search(r"<select[^>]*service-template-picker[^>]*>", html).group(0)
    assert "name=" not in picker
    # the stored value drives the selection and is exposed for the "did it change?" test.
    assert 'data-current="low"' in picker
    assert re.search(r'<option value="low" selected>', html)


def test_the_template_picker_carries_a_stored_template_missing_from_the_list():
    """`ui` is filtered out of the list (as plugins_settings_easy.html:27 does) and an
    externally-set template may not be installed at all. Either way a select with no
    matching option shows its FIRST option, which would misreport the service as
    templateless."""
    html = _render_band(
        "app.example.com",
        _empty_attachments(),
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "ui", "method": "ui"}},
    )

    assert '<option value="ui" selected>ui</option>' in html
    assert html.count('value="ui"') == 1, "the filtered-out entry must not also appear in the list"
    # a template that is not installed at all gets the same treatment.
    gone = _render_band(
        "app.example.com",
        _empty_attachments(),
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "vanished", "method": "ui"}},
    )
    assert '<option value="vanished" selected>vanished</option>' in gone


@pytest.mark.parametrize(
    "config,readonly",
    [
        ({"USE_TEMPLATE": {"value": "low", "method": "scheduler"}}, False),
        ({"USE_TEMPLATE": {"value": "low", "method": "ui"}}, True),
    ],
)
def test_the_template_picker_is_a_readonly_chip_when_it_cannot_be_written(config, readonly):
    html = _render_band("app.example.com", _empty_attachments(), templates=_TEMPLATES, config=config, is_readonly=readonly)

    assert 'id="service-template-picker"' not in html
    assert "Low" in _family_block(html, "template")


def test_a_service_with_no_template_row_still_gets_a_picker():
    """get_service(full=True) returns USE_TEMPLATE at method "default" for a templateless
    service, and is_editable_method rejects "default" unless asked (app/utils.py:235-237).
    Locking exactly the services that have no template yet would be backwards."""
    html = _render_band(
        "app.example.com",
        _empty_attachments(),
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "", "method": "default"}},
    )

    assert 'id="service-template-picker"' in html
    assert re.search(r'<option value="" selected\s+data-i18n="service.resources.template.none"', html)


def test_the_band_hands_the_conflict_context_to_the_dialog():
    conflicts = {
        "paths": {"/api": {"kind": "upstream", "name": "pool-a", "resource_id": "u1"}},
        "stream_upstream": None,
        "primary_certificate": {"id": "c1", "name": "wildcard"},
    }

    html = _render_band("app.example.com", _empty_attachments(), resource_conflicts=conflicts)

    blob = re.search(r'<script type="application/json" id="attach-conflicts">(.*?)</script>', html, re.S).group(1)
    assert json.loads(blob) == conflicts
    # the two slots the JS writes into, and the submit button it disables.
    assert 'id="attach-conflict"' in html
    assert 'id="attach-primary-warning"' in html
    assert 'id="attach-submit"' in html


def test_an_unwired_conflict_context_still_renders_the_dialog():
    """Absence must degrade to "no pre-flight warning", never to a broken page: the failure
    it guards against is a round trip and an error flash, not a bad write."""
    html = _render_band("app.example.com", _empty_attachments())

    blob = re.search(r'<script type="application/json" id="attach-conflicts">(.*?)</script>', html, re.S).group(1)
    assert json.loads(blob) == {}
    assert 'id="attach-resource-modal"' in html


def test_a_dead_resource_family_leaves_the_template_column_alone():
    """Per-family degradation, restated against the fifth column: the workflows API ships
    inside the workflows plugin and is simply absent when it is not loaded."""
    attachments = _empty_attachments()
    attachments["workflow"]["error"] = "not found"

    html = _render_band(
        "app.example.com",
        attachments,
        templates=_TEMPLATES,
        config={"USE_TEMPLATE": {"value": "low", "method": "ui"}},
    )

    assert 'data-i18n="service.resources.unavailable"' in _family_block(html, "workflow")
    assert 'id="service-template-picker"' in _family_block(html, "template")
    for family in ("upstream", "certificate", "redirect"):
        assert 'data-i18n="service.resources.none"' in _family_block(html, family)


# --------------------------------------------------------------------------------------
# service-resources.js -- source-level guards. There is no JS test runner in this suite
# (test_logs.py / test_compose_shelf.py pin their JS the same way); these four assertions
# each name a mutation that would be destructive or silently wrong on the real page.
# --------------------------------------------------------------------------------------


def test_the_template_picker_js_cannot_write_use_template_unguarded():
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "service-resources.js").read_text(encoding="utf-8")

    # The wire itself: the picker drives the compose shelf's own control-key input.
    assert "$('[name=\"USE_TEMPLATE\"]')" in source

    # Twice: once at load (grey the picker) and once at change time (refuse to write). One
    # value must reach request.form -- USE_TEMPLATE is in restore_skip and is never restored,
    # so writing into two inputs, or into none while the user thinks it took, loses the row.
    assert source.count("length !== 1") == 2

    # attr, not .data(): jQuery coerces a numeric-looking data-* value to a Number, which is
    # the cloned-<select> defect the chantier already chased through settings-widgets.js.
    assert 'picker.attr("data-current")' in source
    assert 'picker.data("current")' not in source

    # The primary-certificate demotion succeeds -- it is a warning, never a refusal, so it
    # must not gate the submit button the way a real conflict does.
    assert '$("#attach-submit").prop("disabled", Boolean(blocking));' in source
    assert "Boolean(warning)" not in source

    # All four server-side refusals reach the dialog, each keyed to the rule it mirrors:
    # location_conflict's two halves, and _upstream_conflict's two stream sub-rules.
    for key in ("conflict.inline", "conflict.resource", "conflict.stream", "conflict.stream_inline"):
        assert f'"service.resources.{key}"' in source

    # The stream branch's inline check is reverse-proxy-only: upstreams.py:137 passes
    # LOCATION_SETTINGS["reverse proxy"], so widening it to every inline family would refuse
    # an attach the API accepts.
    assert 'claim.kind === "inline" && claim.name === "reverse proxy"' in source

    # A path typed by hand must not resolve off Object.prototype.
    assert "Object.prototype.hasOwnProperty.call(claimedPaths, path)" in source

    # The one line the whole column exists for. Without it the picker still shows the pending
    # badge and the "switches this service from X to Y" warning while the posted USE_TEMPLATE
    # stays at the stored value -- the silent no-op the greying exists to avoid.
    assert "target.val(chosen);" in source
