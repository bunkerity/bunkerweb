"""The UI ban, unban and duration-update routes name an address by its canonical spelling.

``app.routes.bans`` pulls in the whole UI, so the shipped ``_identity`` is sliced out of the source and run; the four
form handlers are checked on the source: each passes the address through ``normalize_ip`` and keeps refusing what is not one.
"""

import os
from contextlib import suppress
import re
from pathlib import Path

import pytest
from ip_identity import normalize_ip

ROUTE = Path(os.environ.get("BW_TEST_BANS_ROUTE") or Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "bans.py")
SOURCE = ROUTE.read_text(encoding="utf-8")


def _identity():
    match = re.search(r"^def _identity\(ban\):.*?^    return ip, scope, [^\n]*$", SOURCE, re.S | re.M)
    assert match, "_identity not found in routes/bans.py -- renamed or restructured, or it does not name the canonical address?"
    scope = {"normalize_ip": normalize_ip, "suppress": suppress}
    exec(match.group(0), scope)  # noqa: S102 - the shipped function, run against its one collaborator
    return scope["_identity"]


@pytest.mark.parametrize(
    ("given", "canonical"),
    [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("192.0.2.1", "192.0.2.1"), ("not an ip", "not an ip")],
)
def test_a_listed_ban_is_keyed_by_the_canonical_address(given, canonical):
    assert _identity()({"ip": given, "ban_scope": "global"}) == (canonical, "global", "")
    assert _identity()({"ip": given, "ban_scope": "service", "service": "www"}) == (canonical, "service", "www")


def test_the_ban_unban_and_duration_handlers_normalize_before_they_forward():
    assert "validate_ip_address" not in SOURCE, "a handler still only validates the address and forwards its spelling unchanged"
    assert len(re.findall(r"ip = normalize_ip\(ip\)  # one address", SOURCE)) == 4
