"""bwcli sends a ban or an unban target to the instances under the canonical spelling of its address."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/common/cli"))

import CLI as cli_module  # noqa: E402


@pytest.fixture
def cli():
    instance = object.__new__(cli_module.CLI)
    instance._CLI__db = Mock(database_uri="sqlite:///fixture")
    instance._CLI__logger = Mock()
    instance._CLI__terminal_width = 80
    instance._CLI__variables = {"SERVER_NAME": "example.com"}
    instance._CLI__redis = None
    instance.apis = [Mock(endpoint="http://instance/")]
    instance.send_to_apis = Mock(return_value=(True, {}))
    return instance


@pytest.mark.parametrize(
    ("given", "sent"),
    [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1"), ("192.0.2.1", "192.0.2.1")],
)
def test_ban_sends_the_canonical_address(cli, given, sent):
    assert cli.ban(given, 60, "manual")[0]
    assert cli.send_to_apis.call_args.kwargs["data"]["ip"] == sent


@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64", "example.com"])
def test_ban_and_unban_refuse_what_is_not_an_address_without_calling_an_instance(cli, bad):
    for ok, message in (cli.ban(bad, 60, "manual"), cli.unban(bad)):
        assert not ok and "not a valid IP address" in message
    cli.send_to_apis.assert_not_called()


@pytest.mark.parametrize(("given", "sent"), [("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"), ("::ffff:192.0.2.1", "192.0.2.1")])
def test_unban_sends_the_canonical_address(cli, given, sent, monkeypatch):
    monkeypatch.setattr(cli, "_CLI__lookup_lease", lambda *args: (None, []))
    cli.unban(given)
    assert [call.kwargs["data"]["ip"] for call in cli.send_to_apis.call_args_list if call.args[1] == "/unban"] == [sent]
