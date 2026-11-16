"""The UI's Biscuit authorizer raises the fact ceiling along with the clock (dev a292b8d3d).

A session token that carries many grants derives more than biscuit-rust's default 1000 facts and
aborted as a run-limit error, which `BiscuitMiddleware` answers with a 500 for a perfectly valid
session. The UI mints its own token server-side, so a higher ceiling is safe here; the API guard
keeps the default because its tokens can be attenuated by their holder.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

biscuit_auth = pytest.importorskip("biscuit_auth")
from biscuit_auth import AuthorizerBuilder, Biscuit, BiscuitBuilder, KeyPair, Policy  # noqa: E402

from test_session_plumbing import BISCUIT, _shipped  # noqa: E402

# `app.models.biscuit` pulls in the whole UI (BW_CONFIG reads /usr/share/bunkerweb/settings.json at
# import), so the shipped constants and helper are spliced out of the source by name.
_NAMES = ("AUTHORIZE_MAX_TIME", "AUTHORIZE_MAX_FACTS", "RUN_LIMIT_ERROR", "_raise_limits")
_ns = _shipped(BISCUIT, _NAMES, {"timedelta": timedelta, "AuthorizerBuilder": AuthorizerBuilder})
ui_biscuit = SimpleNamespace(**{name: _ns[name] for name in _NAMES})

KEYPAIR = KeyPair()


def _token(grants: int) -> Biscuit:
    """`grants` base facts and a rule pairing them: grants**2 derived facts for the authorizer to hold."""
    facts = "".join(f"grant({index});" for index in range(grants))
    return BiscuitBuilder(facts + "pair($a, $b) <- grant($a), grant($b); time({now});", {"now": datetime.now(timezone.utc)}).build(KEYPAIR.private_key)


def _authorize(token: Biscuit, raise_limits: bool):
    authorizer = AuthorizerBuilder()
    authorizer.add_policy(Policy("allow if grant(0)"))
    if raise_limits:
        ui_biscuit._raise_limits(authorizer)
    authorizer.build(token).authorize()


def test_the_default_ceiling_is_what_a_grant_heavy_token_trips():
    with pytest.raises(biscuit_auth.AuthorizationError) as raised:
        _authorize(_token(40), raise_limits=False)

    assert str(raised.value) == ui_biscuit.RUN_LIMIT_ERROR


def test_a_token_with_many_grants_authorizes_under_the_raised_limits():
    _authorize(_token(40), raise_limits=True)


def test_the_limits_set_on_the_authorizer_are_the_documented_ones():
    authorizer = AuthorizerBuilder()

    ui_biscuit._raise_limits(authorizer)

    limits = authorizer.limits()
    assert limits.max_facts == ui_biscuit.AUTHORIZE_MAX_FACTS == 10000
    assert limits.max_time == ui_biscuit.AUTHORIZE_MAX_TIME


def test_a_denial_is_still_a_denial_with_the_raised_limits():
    authorizer = AuthorizerBuilder()
    authorizer.add_policy(Policy("allow if grant(99999)"))
    ui_biscuit._raise_limits(authorizer)

    with pytest.raises(biscuit_auth.AuthorizationError) as raised:
        authorizer.build(_token(3)).authorize()

    assert str(raised.value) != ui_biscuit.RUN_LIMIT_ERROR
