"""bwcli names the target of a ban or an unban by the canonical spelling of its address, in the database and to the instances."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_unban_crowdsec_lease import FakeClient, _cli, _db  # noqa: E402


@pytest.mark.parametrize(("given", "sent"), [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("192.0.2.1", "192.0.2.1")])
def test_ban_persists_and_sends_the_canonical_address(monkeypatch, given, sent):
    db = _db([])
    db.upsert_ban.return_value = ""
    cli = _cli(monkeypatch, FakeClient([], bans={}), db=db)
    assert cli.ban(given, 60, "manual")[0]
    assert db.upsert_ban.call_args.args[0] == sent
    assert cli.send_to_apis.call_args.kwargs["data"]["ip"] == sent


@pytest.mark.parametrize(("given", "sent"), [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1")])
def test_unban_revokes_and_sends_the_canonical_address(monkeypatch, given, sent):
    log = []
    db = _db(log)
    cli = _cli(monkeypatch, FakeClient(log, bans={}), db=db)
    cli.unban(given)
    assert db.revoke_ban.call_args.args[0] == sent
    assert [call.kwargs["data"]["ip"] for call in cli.send_to_apis.call_args_list if call.args[1] == "/unban"] == [sent]


@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64", "example.com"])
def test_what_is_not_a_bare_address_is_refused_without_touching_anything(monkeypatch, bad):
    db = _db([])
    cli = _cli(monkeypatch, FakeClient([], bans={}), db=db)
    for ok, message in (cli.ban(bad, 60, "manual"), cli.unban(bad)):
        assert not ok and "not a valid IP address" in message
    cli.send_to_apis.assert_not_called()
    db.upsert_ban.assert_not_called()
    db.revoke_ban.assert_not_called()
