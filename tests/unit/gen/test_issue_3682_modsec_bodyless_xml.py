"""A request that declares an XML body and sends none must not be denied with a 400.

ModSecurity arms its XML body processor from the ``Content-Type`` alone, and the parser then reports
"XML: Failed to parse document." for an empty body. The "can't process the body" rules (id 200002, or
200005 in ``ProcessPartial`` mode) denied on that error, which broke WebDAV and SOAP clients (an
``OPTIONS`` or ``PROPFIND`` with ``Content-Type: application/xml`` and no body). The deny rules are
now chained to ``REQUEST_BODY_LENGTH`` being non-zero. Rendered for both the per-service rules and the
global-CRS rules.

Refs: #3682.
"""

import pytest

from _t4_helpers import full_renderer, modsec_chain

BODYLESS_GUARD = ("REQUEST_BODY_LENGTH !@eq 0", "")
RULE_ID = {"Reject": "200002", "ProcessPartial": "200005"}


@pytest.fixture(scope="module")
def render():
    with full_renderer() as render:
        yield render


def rules_text(render, scope, action):
    """``scope`` picks the template under test: the per-service rules or the global-CRS body rules rendered in each server block."""
    variables = {"MULTISITE": "no", "SERVER_NAME": "app.example.com", "MODSECURITY_SEC_REQUEST_BODY_LIMIT_ACTION": action}
    if scope == "service":
        return render(USE_MODSECURITY_GLOBAL_CRS="no", **variables)["server-http/modsecurity-rules.conf.modsec"]
    return render(USE_MODSECURITY_GLOBAL_CRS="yes", **variables)["server-http/modsecurity-rules-global-crs.conf.modsec"]


def link_actions(link):
    return link[1].replace(" ", "").split(",")


@pytest.mark.parametrize("scope", ["service", "global"])
@pytest.mark.parametrize("action", RULE_ID)
def test_the_body_parse_deny_only_fires_when_there_is_a_body(render, scope, action):
    chain = modsec_chain(rules_text(render, scope, action), RULE_ID[action])
    assert chain[0][0] == "REQBODY_ERROR !@eq 0"
    assert "deny" in link_actions(chain[0]) and "status:400" in link_actions(chain[0])
    assert chain[-1] == BODYLESS_GUARD, f"rule {RULE_ID[action]} is not chained to a non-empty body: {chain}"


@pytest.mark.parametrize("scope", ["service", "global"])
def test_the_partial_mode_keeps_its_inbound_data_condition(render, scope):
    """200005 still requires that the failure is not the truncation of an oversized body (INBOUND_DATA_ERROR)."""
    chain = modsec_chain(rules_text(render, scope, "ProcessPartial"), "200005")
    assert [link[0] for link in chain] == ["REQBODY_ERROR !@eq 0", "INBOUND_DATA_ERROR !@eq 1", "REQUEST_BODY_LENGTH !@eq 0"]


@pytest.mark.parametrize("scope", ["service", "global"])
@pytest.mark.parametrize("action", RULE_ID)
def test_every_link_but_the_last_declares_chain(render, scope, action):
    """A link missing ``chain`` would leave the guard a stand-alone rule, and the deny unconditional again."""
    chain = modsec_chain(rules_text(render, scope, action), RULE_ID[action])
    assert all("chain" in link_actions(link) for link in chain[:-1])
    assert "chain" not in link_actions(chain[-1])
