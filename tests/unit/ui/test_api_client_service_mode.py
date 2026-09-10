"""`ApiClient`'s two additions for the explicit redirect-only declaration.

Both are ADDITIVE, and that is the property worth a test rather than the happy paths: `mode` is a
new optional argument on a method the services page has been calling with two positional arguments
since 1.6, so the old call shape has to produce byte-identical request parameters. A `mode=None`
that leaked into `params` would send `mode=None` as a query string and the API would answer 422 on
every draft/online conversion.

Requests are intercepted at `BaseApiClient.session.request`, so everything above it -- the
`RetryError` handling that must not escape as a raw requests exception (see the comment in
`base_api_client._request`), the per-request GET memo, the JSON unwrapping -- is the real code.
"""

from unittest.mock import Mock

import pytest
from requests.exceptions import RetryError

from app.api_client import ApiClient, ApiUnavailableError


@pytest.fixture
def client():
    api_client = ApiClient("http://api.test", "token")
    try:
        yield api_client
    finally:
        api_client.session.close()


def _respond(client, payload, *, status_code=200):
    response = Mock(status_code=status_code, content=b"{}")
    response.json.return_value = payload
    client.session.request = Mock(return_value=response)
    return client.session.request


class TestConvertServiceStaysBackwardCompatible:
    def test_the_pre_existing_call_shape_sends_exactly_what_it_used_to(self, client):
        """The regression guard: two arguments in, one query parameter out, no `mode` anywhere."""
        request = _respond(client, {"status": "success"})

        client.convert_service("app.example.com", "draft")

        assert request.call_args.args[:2] == ("POST", "http://api.test/services/app.example.com/convert")
        assert request.call_args.kwargs["params"] == {"convert_to": "draft"}

    def test_the_mode_axis_travels_on_its_own(self, client):
        request = _respond(client, {"status": "success"})

        client.convert_service("app.example.com", mode="redirect_only")

        assert request.call_args.kwargs["params"] == {"mode": "redirect_only"}

    def test_both_axes_travel_together(self, client):
        request = _respond(client, {"status": "success"})

        client.convert_service("app.example.com", convert_to="online", mode="standard")

        assert request.call_args.kwargs["params"] == {"convert_to": "online", "mode": "standard"}


class TestRedirectCandidates:
    def test_it_returns_the_candidate_rows(self, client):
        _respond(client, {"status": "success", "candidates": [{"service": "old.example.com", "would_qualify": True, "blocking_reasons": []}]})

        assert client.get_redirect_candidates() == [{"service": "old.example.com", "would_qualify": True, "blocking_reasons": []}]

    def test_a_payload_without_candidates_is_an_empty_list_not_a_crash(self, client):
        """The callers iterate it directly, and the badge is advisory: a shape surprise must cost
        the badges, never the services table."""
        _respond(client, {"status": "success"})

        assert client.get_redirect_candidates() == []

    def test_a_spent_retry_surfaces_as_ApiUnavailableError(self, client):
        """`RetryError` subclasses `RequestException`, not `ConnectionError`. Letting it escape is
        what turned a degraded API into a 500 on every UI page once before -- the new getter must
        not reintroduce that by living outside the shared `_request`."""
        client.session.request = Mock(side_effect=RetryError("spent"))

        with pytest.raises(ApiUnavailableError):
            client.get_redirect_candidates()
