"""The HTTPS -> HTTP retry must dial the same host it failed to reach.

``API.request`` retries over plaintext when an ``https`` endpoint raises ``ConnectionError`` (and
the instance is not certificate-pinned). Building that retry URL with ``lstrip("https://")`` looked
right and was not: ``str.lstrip`` takes a character SET, so it removed EVERY leading character in
{h, t, p, s, :, /}. An IP endpoint survived untouched, which is why this went unnoticed -- but
``https://scheduler:5000/`` retried against a host missing its leading "s", and ``https://phpsite:5000/``
against ``http://ite:5000/``. The retry then failed to resolve, so the fallback that exists to keep
a mis-TLS'd instance reachable did nothing at all.

Port of dev ``adaa0f3de``.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

ROOT = Path(__file__).resolve().parents[3]
for _p in (ROOT / "src" / "common" / "api", ROOT / "src" / "common" / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from API import API  # noqa: E402


class _Resp:
    status_code = 200
    reason = "OK"
    text = "{}"

    @staticmethod
    def json():
        return {}


def _retry_url(endpoint: str, url: str = "/ping") -> str:
    """Drive one request whose HTTPS attempt fails, and return the URL the retry dialled."""
    api = API(endpoint, token="t")
    calls = []

    def _fake(method, full_url, **kwargs):
        calls.append(full_url)
        if len(calls) == 1:
            raise RequestsConnectionError("TLS handshake failed")
        return _Resp()

    with patch("API.request", side_effect=_fake):
        api.request("GET", url)
    assert len(calls) == 2, "the HTTPS failure should have produced exactly one plaintext retry"
    return calls[1]


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        # Every one of these hostnames starts with a character lstrip's set would have eaten.
        ("https://scheduler:5000", "http://scheduler:5000/ping"),
        ("https://phpsite:5000", "http://phpsite:5000/ping"),
        ("https://sthttp-host:5000", "http://sthttp-host:5000/ping"),
        ("https://h.example.com:5000", "http://h.example.com:5000/ping"),
        # ... and these did survive the old code, which is exactly why the bug hid for so long.
        ("https://10.0.0.5:5000", "http://10.0.0.5:5000/ping"),
        ("https://bw-api:8888", "http://bw-api:8888/ping"),
    ],
)
def test_the_plaintext_retry_keeps_the_whole_hostname(endpoint, expected):
    assert _retry_url(endpoint) == expected


def test_only_the_scheme_changes_on_the_retry():
    """The retry differs from the first attempt by the scheme and nothing else."""
    api = API("https://scheduler:5000", token="t")
    calls = []

    def _fake(method, full_url, **kwargs):
        calls.append(full_url)
        if len(calls) == 1:
            raise RequestsConnectionError("TLS handshake failed")
        return _Resp()

    with patch("API.request", side_effect=_fake):
        api.request("GET", "/ping")
    first, retry = calls
    assert first.startswith("https://")
    assert retry.startswith("http://")
    assert retry[len("http://") :] == first[len("https://") :]  # noqa: E203


def test_a_plain_http_endpoint_is_never_retried():
    """The fallback is HTTPS-only: a plaintext endpoint that refuses gets the error, not a loop."""
    api = API("http://scheduler:5000", token="t")
    with patch("API.request", side_effect=RequestsConnectionError("refused")) as network:
        sent, err, status, _ = api.request("GET", "/ping")
    assert network.call_count == 1
    assert sent is False
    assert status is None
    assert "Connection error" in err
