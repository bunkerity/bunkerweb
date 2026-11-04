"""The API guard bound the request path into authorizer Datalog with f-strings, so a crafted path could add facts.

Pins that an attacker-controlled path segment is only ever a string term: a token scoped to one service never
reaches another by smuggling a ``resource_id`` fact through the URL, and a quote or backslash in a segment is
matched as plain text instead of breaking the authorizer source. Ref: GHSA-254j-92cv-m443.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from biscuit_auth import BiscuitBuilder
from fastapi import HTTPException
from starlette.requests import Request

import pytest

from _api_http_helpers import VERSION, _KEYPAIR

import app.auth.biscuit as biscuit


def scoped_token(service="example"):
    facts = 'time({issued}); client_ip({ip}); version({version}); api_perm("services", {service}, "service_read");'
    values = {"issued": datetime.now(timezone.utc), "ip": "127.0.0.1", "version": VERSION, "service": service}
    return BiscuitBuilder(facts, values).build(_KEYPAIR.private_key).to_base64()


def request(path, token):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 1000),
            "scheme": "http",
            "server": ("localhost", 80),
        }
    )


@pytest.fixture(autouse=True)
def biscuit_config(monkeypatch):
    config = SimpleNamespace(API_ROOT_PATH=None, docs_url=None, openapi_url=None, redoc_url=None, biscuit_ttl_seconds=60, check_private_ip=True)
    monkeypatch.setattr(biscuit, "api_config", config)


def test_the_scoped_token_reaches_only_its_own_service():
    token = scoped_token()
    assert biscuit.guard(request("/services/example", token)) is None
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request("/services/other", token))
    assert caught.value.status_code == 403


@pytest.mark.parametrize(
    "segment",
    [
        'other"); resource_id("example',
        'other"), resource_id("example',
        'other") ; admin(true); resource_id("example',
        'other\\"); resource_id("example',
    ],
)
def test_path_segment_cannot_inject_a_resource_fact(segment):
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request(f"/services/{segment}", scoped_token()))
    assert caught.value.status_code == 403


@pytest.mark.parametrize("service", ['we"ird', "back\\slash", 'a"); b("c'])
def test_quotes_and_backslashes_in_a_segment_match_as_literal_text(service):
    token = scoped_token(service)
    assert biscuit.guard(request(f"/services/{service}", token)) is None
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(request("/services/example", token))
    assert caught.value.status_code == 403
