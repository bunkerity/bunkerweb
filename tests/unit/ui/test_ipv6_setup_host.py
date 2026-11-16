"""The wizard proposes the bare IPv6 literal (the service name form) and never a truncated authority as the server name.

``app.routes.setup`` pulls in the whole UI, so the shipped ``_default_server_name`` is sliced out of the source and run.
"""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROUTE = Path(os.environ.get("BW_TEST_SETUP_ROUTE") or Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "setup.py")
SOURCE = ROUTE.read_text(encoding="utf-8")


def _server_name(host):
    match = re.search(r"^def _default_server_name\(.*?^    return [^\n]*$", SOURCE, re.S | re.M)
    if match is None:
        # the unfixed route computed it inline: replay that expression
        name = host.split(":")[0]
        return name or "www.example.com"
    scope = {"urlsplit": urlsplit}
    exec(match.group(0), scope)  # noqa: S102 - the shipped function, run against its one collaborator
    return scope["_default_server_name"](host)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("[2001:db8::1]:7000", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("[::1]:7000", "::1"),
        ("[2001:DB8::1]:7000", "2001:db8::1"),
        ("192.0.2.1:7000", "192.0.2.1"),
        ("ui.example.com:7000", "ui.example.com"),
        ("ui.example.com", "ui.example.com"),
        ("", "www.example.com"),
    ],
)
def test_setup_host_default(host, expected):
    assert _server_name(host) == expected


def test_the_route_uses_the_helper():
    assert "_default_server_name(request.headers" in SOURCE
