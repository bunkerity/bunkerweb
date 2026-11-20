"""Every route that is not meant to be public refuses a request without a login (QAR Q9).

The blueprints are walked from the URL map instead of listed by hand, so a route added later without
``@login_required`` shows up here as a failure rather than as a gap nobody noticed.
"""

import pytest
from werkzeug.routing import IntegerConverter

SKIPPED_METHODS = {"HEAD", "OPTIONS"}
# Blueprints that are reachable before an account exists or that sign the session out.
PUBLIC_BLUEPRINTS = {"login", "logout", "setup"}


def _rules(app):
    for rule in app.url_map.iter_rules():
        blueprint = rule.endpoint.split(".")[0]
        if rule.endpoint in ("static", "loading") or blueprint in PUBLIC_BLUEPRINTS:
            continue
        for method in sorted(rule.methods - SKIPPED_METHODS):
            yield rule, method


def _url(rule):
    """Fill every converter with a dummy value; the login check runs before any view argument is read."""
    values = {name: 1 if isinstance(rule._converters[name], IntegerConverter) else "x" for name in rule.arguments}
    return rule.build(values)[1]


def test_every_private_route_refuses_an_anonymous_request(h):
    seen = []
    failures = []
    client = h.client(None)
    for rule, method in _rules(h.app):
        response = client.open(_url(rule), method=method)
        seen.append(rule.endpoint)
        refused = response.status_code == 401 or (response.status_code == 302 and "/login" in response.headers.get("Location", ""))
        if not refused:
            failures.append((rule.endpoint, method, response.status_code))

    assert len(set(seen)) > 60, f"the walk found only {len(set(seen))} endpoints, the harness is not registering the blueprints"
    assert not failures, f"routes answering an anonymous request: {failures}"
    h.db.checked_changes.assert_not_called()


def test_a_signed_in_user_is_not_bounced_to_the_login_page(h):
    response = h.client("alice").get("/about")

    assert response.status_code == 200
    assert h.renders[-1][0] == "about.html"


@pytest.mark.parametrize("path", ["/about", "/jobs", "/cache"])
def test_anonymous_get_never_reaches_the_view(h, path):
    h.client(None).get(path)

    assert h.renders == []
