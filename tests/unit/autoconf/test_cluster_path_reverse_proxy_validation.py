"""A cluster-supplied path that REVERSE_PROXY_URL's own regex rejects is skipped, not rendered.

An Ingress path or a Gateway API HTTPRoute match value is written by whoever owns the namespace,
not by the BunkerWeb operator. `Configurator` drops a `REVERSE_PROXY_URL_N` whose value fails the
plugin's regex, and `reverse-proxy.conf` then falls back to `/` — so an invalid path silently
proxies the WHOLE site instead of the narrow path the rule was scoping. Refusing the rule with a
warning is the only safe reading. Port of dev `dbd98e87a`.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gateway_regex_path_anchoring import _controller, _route  # noqa: E402

# The shape the three location settings carry; asserted against the shipped plugin.json below so
# this file tests the product's regex, not a copy of it.
LOCATION_RX = r"^(?!(?:~\*|~|\^~|=)$)(?:(?:~\*|~|\^~|=) )?[^\s;{}]+$"


def test_the_regex_under_test_is_the_one_reverseproxy_ships():
    import json

    plugin = json.loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "reverseproxy" / "plugin.json").read_text(encoding="utf-8"))

    assert plugin["settings"]["REVERSE_PROXY_URL"]["regex"] == LOCATION_RX


def _controller_with(regex):
    controller = _controller()
    controller._settings = {"REVERSE_PROXY_URL": {"regex": regex}} if regex else {}
    return controller


@pytest.mark.parametrize("bad", ("/api;return 403", "/a b", "/x{}", "~", "="))
def test_a_path_the_regex_rejects_produces_no_reverse_proxy_rule(bad):
    services = _controller_with(LOCATION_RX)._to_services(_route("PathPrefix", bad))
    for service in services:
        assert not [key for key in service if key.startswith("REVERSE_PROXY_URL")], f"{bad!r} reached the template"


@pytest.mark.parametrize("good", ("/api", "^/api/v[0-9]+", "~ ^/api", "/a/very/long/path"))
def test_a_valid_path_still_renders(good):
    services = _controller_with(LOCATION_RX)._to_services(_route("PathPrefix", good))
    assert services[0]["REVERSE_PROXY_URL_1"] == good


def test_a_controller_without_a_loaded_settings_snapshot_does_not_drop_rules():
    """The settings snapshot is refreshed by a background worker. No regex means no opinion —
    dropping cluster rules because the snapshot has not arrived yet would be the worse failure."""
    services = _controller_with(None)._to_services(_route("PathPrefix", "/api"))
    assert services[0]["REVERSE_PROXY_URL_1"] == "/api"


def test_the_ingress_controller_gates_on_the_same_helper():
    """The Ingress path is the other half of the same defect; its call site is asserted in source
    because building an IngressController needs a live client object graph."""
    source = (Path(__file__).resolve().parents[3] / "src" / "autoconf" / "controllers" / "IngressController.py").read_text(encoding="utf-8")
    assert "self._is_valid_reverse_proxy_url(path.path)" in source
