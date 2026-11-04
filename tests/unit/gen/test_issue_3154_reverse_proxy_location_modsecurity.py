"""A per-location ``REVERSE_PROXY_MODSECURITY=no`` switches ModSecurity off in that location only.

#3154: operators needed to keep ModSecurity on for the service but drop it for one heavy upload path. The
reverse proxy template reads ``REVERSE_PROXY_MODSECURITY[_N]`` for each location and emits ``modsecurity off;``
inside that ``location`` block, and only when the service itself runs ModSecurity (``USE_MODSECURITY=yes``).
The test renders the real template with two locations and reads each block back.

Refs: #3154.
"""

from importlib import import_module
from pathlib import Path
import re

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "src" / "common" / "core" / "reverseproxy" / "confs" / "server-http" / "reverse-proxy.conf"


def _locations(use_modsecurity: str, **overrides: str) -> dict:
    """Render the template and return {url: location block body}."""
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module
    config = {
        "REVERSE_PROXY_HOST": "http://backend:8080",
        "REVERSE_PROXY_URL": "/",
        "REVERSE_PROXY_HOST_1": "http://uploads:8080",
        "REVERSE_PROXY_URL_1": "/upload",
        "REVERSE_PROXY_HOST_2": "http://api:8080",
        "REVERSE_PROXY_URL_2": "/api",
        **overrides,
    }
    out = environment.from_string(TEMPLATE.read_text(encoding="utf-8")).render(
        USE_REVERSE_PROXY="yes",
        SERVER_NAME="www.example.com",
        REVERSE_PROXY_CUSTOM_HOST="",
        USE_MODSECURITY=use_modsecurity,
        USE_MTLS="no",
        USE_PROXY_CACHE="no",
        USE_UI="no",
        all=config,
    )
    blocks = re.findall(r'^location (?:\S+ )?"([^"]+)" \{\n(.*?)^\}', out, re.M | re.S)
    return dict(blocks)


def test_location_set_to_no_gets_modsecurity_off_and_its_siblings_do_not():
    blocks = _locations("yes", REVERSE_PROXY_MODSECURITY_1="no")

    assert set(blocks) == {"/", "/upload", "/api"}
    assert "modsecurity off;" in blocks["/upload"]
    assert "modsecurity off;" not in blocks["/"]
    assert "modsecurity off;" not in blocks["/api"]


def test_unsuffixed_first_location_toggle_applies_to_that_location_only():
    blocks = _locations("yes", REVERSE_PROXY_MODSECURITY="no")

    assert "modsecurity off;" in blocks["/"]
    assert "modsecurity off;" not in blocks["/upload"]
    assert "modsecurity off;" not in blocks["/api"]


@pytest.mark.parametrize("value", ["yes", ""])
def test_default_and_explicit_yes_render_no_modsecurity_directive(value):
    overrides = {"REVERSE_PROXY_MODSECURITY_1": value} if value else {}
    blocks = _locations("yes", **overrides)

    assert all("modsecurity off;" not in body for body in blocks.values())


def test_toggle_is_silent_when_the_service_does_not_run_modsecurity():
    blocks = _locations("no", REVERSE_PROXY_MODSECURITY_1="no")

    assert all("modsecurity off;" not in body for body in blocks.values())
