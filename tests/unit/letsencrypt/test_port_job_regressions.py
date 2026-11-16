"""Public suffix checks, ZeroSSL zero values, and RFC 8555 stale accounts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from letsencrypt_utils import is_stale_account_line, stale_account_uri
from test_certbot_new_readiness_gate import _load_definitions


@pytest.mark.parametrize(
    ("domain", "blocked"),
    [("foo.bar.baz", True), ("*.foo.bar.baz", True), ("sub.foo.bar.baz", False), ("foo.baz", False), ("foo.ck", True), ("*.foo.ck", True)],
)
def test_psl_wildcard_depth(domain, blocked):
    module = _load_definitions()
    assert module.is_domain_blacklisted(domain, {"rules": {"*.bar.baz", "*.ck"}, "exceptions": set()}) is blocked


@pytest.mark.parametrize(("value", "expected"), [(0, "0"), (None, "3"), ("", "3"), (5, "5")])
def test_zerossl_order_preserves_retry_zero(tmp_path, value, expected):
    module = _load_definitions()
    module.resolve_certbot_entrypoint = Mock(return_value=["zerossl-bot.sh"])
    module.select_account_id = Mock(return_value="")
    module.stream_certbot = Mock(return_value=True)
    module.Popen = Mock(return_value=SimpleNamespace(returncode=0))
    config = {
        "acme_server": "zerossl",
        "server_names": "example.com",
        "profile": "classic",
        "challenge": "http",
        "staging": False,
        "force_renew": False,
        "zerossl_api_retry": value,
        "zerossl_api_retry_delay": value,
    }
    paths = SimpleNamespace(config_dir=tmp_path, work_dir=tmp_path, logs_dir=tmp_path)
    env = {}
    assert module.certbot_new("example.com", config, env, paths) == 0
    assert env["LETS_ENCRYPT_ZEROSSL_API_RETRY"] == expected
    assert env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"] == ("2" if value in (None, "") else expected)
    assert env["ZEROSSL_API_RETRY"] == expected


@pytest.mark.parametrize("quoted", [False, True])
def test_any_ca_account_url_is_recognized(quoted):
    uri = "https://pebble.example:14000/my-account/1"
    account = f'"{uri}"' if quoted else uri
    line = f"Account {account} not found. Order https://pebble.example/my-order/9 pending"
    assert is_stale_account_line(line)
    assert stale_account_uri(line) == uri


def test_rfc_error_type_without_uri_is_recognized():
    line = "acme.messages.Error: urn:ietf:params:acme:error:accountDoesNotExist :: unknown account"
    assert is_stale_account_line(line)
    assert stale_account_uri(line) == ""


@pytest.mark.parametrize(
    "line",
    [
        "Account at /var/cache/accounts/123 does not exist",
        "Order https://ca.example/my-order/1 not found.",
        "urn:ietf:params:acme:error:rateLimited :: too many orders",
        "urn:ietf:params:acme:error:unauthorized :: forbidden",
        "urn:ietf:params:acme:error:badNonce :: invalid nonce",
    ],
)
def test_other_errors_do_not_retire_accounts(line):
    assert not is_stale_account_line(line)
    assert stale_account_uri(line) == ""
