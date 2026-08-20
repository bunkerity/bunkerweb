"""A Gateway API `RegularExpression` path must reach the template ANCHORED, or it renders as a prefix.

`reverse-proxy.conf` decides between a prefix location and a regex location from the value itself:

    {% set url_is_regex = url.split(" ")[0] not in ("~", "~*", "=", "^~")
                          and (url.startswith("^") or url.endswith("$")) %}

Nothing in that template knows what a k8s HTTPRoute `path.type` was. So a rule written as

    matches: [{path: {type: RegularExpression, value: "/api/v[0-9]+"}}]

used to arrive as the bare string `/api/v[0-9]+`, which is neither anchored nor suffixed -- nginx
takes it as a PREFIX location and matches the literal characters `[0-9]+`, i.e. never. That is the
silent half of this defect: the config loads, nginx starts, and the route simply never fires.
`GatewayController` therefore anchors the value at the point it builds `REVERSE_PROXY_URL_*`.

WHY THIS FILE EXISTS (RULE 14a / changed-line coverage)
-------------------------------------------------------
Measured at 16:07 CEST: of the lines my rows changed, `GatewayController.py:525,527,528` were
executed by ZERO tests -- an entire row shipped without one. `tests/unit/gen/
test_reverse_proxy_regex_location.py` proves the template renders `^...` as a regex location; it
cannot prove anything ever produces the `^`. Two halves of one behaviour, and only one was covered.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse @integration's controller loader rather than a second copy of the kubernetes stub. A plain
# import on purpose: if it is renamed this file goes RED, which is the correct kind of loud.
from test_lb_address_call_sites import _K8S_ENTRY, _load  # noqa: E402

_GATEWAY = _load("GatewayController", {"controllers.KubernetesController": _K8S_ENTRY})

# (path type, written value, what must reach REVERSE_PROXY_URL_1)
# RULE 13: a floor -- widening this table is collaboration.
PATH_CASES = [
    ("RegularExpression", "/api/v[0-9]+", "^/api/v[0-9]+"),
    ("RegularExpression", "/files/.*\\.pdf$", "^/files/.*\\.pdf$"),
    ("RegularExpression", "^/already/anchored", "^/already/anchored"),
    ("PathPrefix", "/api", "/api"),
    ("Exact", "/healthz", "/healthz"),
]
MINIMUM_PATH_CASES = 5


def _controller():
    """Build the controller without its constructor: no kubernetes client, no cluster.

    Only the attributes `_to_services` actually reads are set, so a new dependency shows up as an
    AttributeError here rather than being silently satisfied by a Mock that returns a Mock.
    """
    controller = object.__new__(_GATEWAY.GatewayController)
    controller._logger = Mock()
    controller._domain_name = "cluster.local"
    controller._reverse_proxy_suffix_start = 1
    controller._get_gateway_annotations = lambda svc: {}
    controller._get_listener_hostnames = lambda svc, protocols=None: []
    controller._get_listener_protocol = lambda svc, hostname, allowed_protocols=None: "HTTP"
    controller._get_listener_port = lambda *a, **kw: None
    return controller


def _route(path_type, value):
    match = {"path": {"type": path_type, "value": value}} if path_type else {}
    return {
        "kind": "HTTPRoute",
        "metadata": {"name": "api", "namespace": "default", "annotations": {}},
        "spec": {
            "hostnames": ["app.example.com"],
            "rules": [{"matches": [match], "backendRefs": [{"name": "backend", "port": 8080}]}],
        },
    }


def _url(path_type, value):
    """RULE 18: an `or` fallback between the two key spellings would answer a MISSING key with the
    other key's value -- a plausible sentence in place of an error. The suffix is deterministic
    here (`_reverse_proxy_suffix_start = 1` is set by this file), so demand that exact key."""
    services = _controller()._to_services(_route(path_type, value))
    assert services, f"{path_type} {value!r} produced no service at all"
    service = services[0]
    assert "REVERSE_PROXY_URL_1" in service, f"expected REVERSE_PROXY_URL_1, got keys: {sorted(service)}"
    return service["REVERSE_PROXY_URL_1"]


@pytest.mark.parametrize("path_type,written,expected", PATH_CASES)
def test_the_path_reaches_the_template_in_the_form_the_template_can_classify(path_type, written, expected):
    assert _url(path_type, written) == expected, f"{path_type} {written!r} must reach REVERSE_PROXY_URL as {expected!r}"


def test_an_anchored_value_is_not_anchored_twice():
    """`^^/x` is a valid regex that matches nothing. The guard is `not startswith("^")`."""
    assert not _url("RegularExpression", "^/api").startswith("^^")


def test_a_prefix_path_is_never_anchored():
    """Anti-vacuity in the other direction: anchoring everything would turn every plain
    `PathPrefix` route into a regex location and change matching precedence fleet-wide."""
    assert _url("PathPrefix", "/api") == "/api", "a PathPrefix route must stay a prefix location"


def test_the_case_table_is_populated_and_still_covers_both_directions():
    """RULE 13 floor. A parametrised guard does not fail when its source list empties -- it
    reports success over zero cases, which is indistinguishable from a clean run."""
    assert len(PATH_CASES) >= MINIMUM_PATH_CASES, "PATH_CASES shrank; the parametrised guard collects nothing"
    assert any(t == "RegularExpression" for t, _, _ in PATH_CASES), "no regex case left: the anchoring is untested"
    assert any(t != "RegularExpression" for t, _, _ in PATH_CASES), "no non-regex case left: over-anchoring is untested"
