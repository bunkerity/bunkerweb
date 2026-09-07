"""An error response has to reach the caller with the reason it states.

`base_api_client` kept the body of a 4xx and threw away the body of a 5xx, raising the bare
``API returned 500``. That is not something an operator can act on, and it is what made dev
`abb60b1ea`'s refused-write fix unportable: ``PUT /configs/bulk`` answered 500 with the message
the database returned, and the message was gone by the time the scheduler read it. The route now
answers 4xx for a refusal (see `tests/unit/api/test_configs_bulk_save_classification.py`); this
half makes the 5xx that remain -- an unhandled server fault -- say what happened too.
"""

from unittest.mock import Mock

import pytest

from base_api_client import ApiClientError, ApiUnavailableError, BaseApiClient, _error_detail


def _response(status, payload=None, text=""):
    resp = Mock()
    resp.status_code = status
    resp.text = text if text else ("" if payload is None else "raw body")
    resp.content = b"x"
    resp.json = Mock(return_value=payload) if payload is not None else Mock(side_effect=ValueError("not json"))
    return resp


# --------------------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"status": "error", "message": "the database is read-only"}, "the database is read-only"),
        ({"msg": "legacy shape"}, "legacy shape"),
        ({"detail": "Not authenticated"}, "Not authenticated"),  # FastAPI's own shape
        ({"status": "error"}, ""),
        ({"message": ""}, ""),
        ({"message": {"nested": "dict"}}, ""),  # a non-string is not a reason
        (["not", "a", "dict"], ""),
        (None, ""),  # body is not JSON at all
    ],
)
def test_the_reason_is_read_from_whichever_shape_the_body_uses(payload, expected):
    assert _error_detail(_response(500, payload)) == expected


# --------------------------------------------------------------------------------------
# What the caller ends up holding
# --------------------------------------------------------------------------------------
def _raise(status, payload=None, text=""):
    client = BaseApiClient("http://bw-api:5000", "token")
    client.session = Mock()
    client.session.request.return_value = _response(status, payload, text)
    with pytest.raises((ApiClientError, ApiUnavailableError)) as excinfo:
        client._request("PUT", "/configs/bulk", json={})
    return excinfo.value


def test_a_5xx_carries_the_reason_the_body_states():
    error = _raise(500, {"status": "error", "message": "database is locked"})

    assert isinstance(error, ApiUnavailableError)
    assert "database is locked" in str(error)
    assert "500" in str(error), "the status is still there -- the reason is added, not swapped"


def test_a_5xx_with_no_readable_reason_still_says_what_it_used_to():
    error = _raise(503, None, text="<html>bad gateway</html>")

    assert str(error) == "API returned 503"


def test_a_4xx_still_carries_its_message_and_status():
    error = _raise(400, {"status": "error", "message": "the database is read-only"})

    assert isinstance(error, ApiClientError)
    assert error.message == "the database is read-only"
    assert error.status_code == 400


def test_a_4xx_with_an_unreadable_body_falls_back_to_the_raw_text():
    error = _raise(409, None, text="conflict")

    assert error.message == "conflict"


# --------------------------------------------------------------------------------------
# The binary-download path (`_raw_request`): plugin tarballs, log/config/service exports
# --------------------------------------------------------------------------------------
def _raise_raw(status, payload=None, text=""):
    client = BaseApiClient("http://bw-api:5000", "token")
    client.session = Mock()
    client.session.request.return_value = _response(status, payload, text)
    with pytest.raises((ApiClientError, ApiUnavailableError)) as excinfo:
        client._raw_request("GET", "/plugins/myplugin/export")
    return excinfo.value


def test_a_5xx_on_the_download_path_carries_the_reason_too():
    """It hand-rolled its own copy of the pre-fix handling right next to `_error_detail`, so an
    operator whose plugin export failed still got the bare status and nothing else."""
    error = _raise_raw(500, {"status": "error", "message": "cache directory is not writable"})

    assert isinstance(error, ApiUnavailableError)
    assert "cache directory is not writable" in str(error)
    assert "500" in str(error)


def test_a_5xx_on_the_download_path_with_no_reason_says_what_it_used_to():
    assert str(_raise_raw(502, None, text="<html>bad gateway</html>")) == "API returned 502"


def test_a_4xx_on_the_download_path_reads_fastapis_own_shape():
    """`detail` is what FastAPI's auth and validation failures answer with; reading only `message`
    handed the operator the raw JSON body instead."""
    error = _raise_raw(401, {"detail": "Not authenticated"})

    assert isinstance(error, ApiClientError)
    assert error.message == "Not authenticated"
    assert error.status_code == 401


def test_a_4xx_on_the_download_path_still_reads_the_api_shape():
    assert _raise_raw(404, {"status": "error", "message": "plugin not found"}).message == "plugin not found"


def test_a_4xx_on_the_download_path_falls_back_to_the_raw_text():
    assert _raise_raw(409, None, text="conflict").message == "conflict"


def test_a_4xx_on_the_download_path_with_an_empty_body_still_says_something():
    """`ApiClientError("")` is what a caller used to flash at the operator."""
    assert _raise_raw(404, None, text="").message == "HTTP 404"


def test_a_successful_download_still_returns_the_raw_response():
    client = BaseApiClient("http://bw-api:5000", "token")
    client.session = Mock()
    resp = _response(200, {"status": "success"})
    client.session.request.return_value = resp

    assert client._raw_request("GET", "/plugins/myplugin/export") is resp
