"""The Web UI's own pages must not be blocked by the CRS for what they legitimately send.

A complex password posted to ``/login`` tripped the SQLi / RCE / XSS rules and the login answered
403 (the password argument is now removed from those rule tags' targets, on that argument only),
and the ``/logs`` page, which displays attack payloads by design, tripped the attack-disclosure
rules (that tag is now removed for that one path). Both exclusions are rendered twice, once in the
``http`` context scoped to the UI hosts and once per UI service.

Refs: #2452, #2250.
"""

import pytest

from _t4_helpers import full_renderer, modsec_chains

PASSWORD_TAGS = ("attack-sqli", "attack-rce", "attack-rfi", "attack-lfi", "attack-protocol", "attack-ssrf", "attack-xss")
HTTP_RULES = "http/ui.modsec-crs"
SERVICE_RULES = "modsec-crs/ui.conf"


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


@pytest.fixture(scope="module")
def http_rules(render):
    tree = render(MULTISITE="yes", SERVER_NAME="ui.example.com", **{"ui.example.com_USE_UI": "yes", "ui.example.com_SERVER_NAME": "ui.example.com"})
    return tree[HTTP_RULES]


@pytest.fixture(scope="module")
def service_rules(render):
    return render(MULTISITE="no", SERVER_NAME="ui.example.com", USE_UI="yes")[SERVICE_RULES]


def rule_with(text, path_operator):
    """The chain whose first link matches the request path with ``path_operator`` (e.g. ``@endsWith /login``)."""
    matches = [chain for chain in modsec_chains(text) if chain[0][0] == f"REQUEST_FILENAME {path_operator}"]
    assert len(matches) == 1, f"expected one rule on {path_operator!r}, got {len(matches)}"
    return matches[0]


def actions_of(chain):
    return chain[0][1].replace(" ", "").split(",")


@pytest.mark.parametrize("rules", ["http_rules", "service_rules"])
class TestLoginPasswordExclusion:
    def test_every_attack_family_is_lifted_from_the_password_argument(self, rules, request):
        actions = actions_of(rule_with(request.getfixturevalue(rules), "@endsWith /login"))
        for tag in PASSWORD_TAGS:
            assert f"ctl:ruleRemoveTargetByTag={tag};ARGS:password" in actions, f"{tag} still inspects the login password"

    def test_the_exclusion_is_scoped_to_the_password_argument_only(self, rules, request):
        """A whole-tag removal on /login would blind the CRS to every other argument of the form."""
        actions = actions_of(rule_with(request.getfixturevalue(rules), "@endsWith /login"))
        assert not [action for action in actions if action.startswith("ctl:ruleRemoveByTag=")]
        assert not [action for action in actions if action.startswith("ctl:ruleRemoveById=")]
        targeted = [action for action in actions if action.startswith("ctl:ruleRemoveTargetByTag=")]
        assert targeted and all(action.endswith(";ARGS:password") for action in targeted)


@pytest.mark.parametrize("rules", ["http_rules", "service_rules"])
def test_logs_page_is_exempt_from_attack_disclosure_rules(rules, request):
    actions = actions_of(rule_with(request.getfixturevalue(rules), "@endsWith /logs"))
    assert "ctl:ruleRemoveByTag=attack-disclosure" in actions
    assert "ctl:ruleRemoveById=953100" in actions


def test_login_exclusion_applies_to_the_ui_host_only(http_rules):
    chain = rule_with(http_rules, "@endsWith /login")
    assert len(chain) == 2
    assert chain[1][0].startswith("REQUEST_HEADERS:Host @rx ^(?:")
    assert r"ui\.example\.com" in chain[1][0]
