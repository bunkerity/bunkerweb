"""The UI ban, unban and duration-update routes store and forward the canonical spelling of an address.

``app.routes.bans`` pulls in the whole UI (database, Flask-Login, instances), so the shipped ``_normalize_target``
is sliced out of the source and run; the three form handlers are checked on the source: each must pass the address
through ``normalize_ip`` and keep refusing what is not an address.
"""

import re
from pathlib import Path

import pytest

from ip_identity import normalize_ip

ROUTE = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "bans.py"
SOURCE = ROUTE.read_text(encoding="utf-8")


def _target_normalizer():
    match = re.search(r"^def _normalize_target\(.*?^    return ip, ban_scope, service if ban_scope == \"service\" else None$", SOURCE, re.S | re.M)
    assert match, "_normalize_target not found in routes/bans.py -- renamed or restructured?"
    scope = {"normalize_ip": normalize_ip, "RESERVED_SERVICE_NAMES": frozenset({"unknown", "Web UI", "bwcli", "default server", ""})}
    exec(match.group(0), scope)  # noqa: S102 - the shipped function, run against its two collaborators
    return scope["_normalize_target"]


@pytest.mark.parametrize(
    ("given", "canonical"),
    [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("192.0.2.1", "192.0.2.1")],
)
def test_a_crowdsec_target_is_normalized_to_the_canonical_address(given, canonical):
    assert _target_normalizer()(given, "global", None) == (canonical, "global", None)


@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64", None])
def test_a_crowdsec_target_that_is_not_an_address_is_refused(bad):
    with pytest.raises(ValueError):
        _target_normalizer()(bad, "global", None)


def test_the_ban_unban_and_duration_handlers_normalize_before_they_forward():
    assert "validate_ip_address" not in SOURCE, "a handler still only validates the address and forwards its spelling unchanged"
    assert len(re.findall(r"ip = normalize_ip\(ip\)", SOURCE)) == 4
