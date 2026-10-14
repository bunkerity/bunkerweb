"""Public IPv4 issuance without contacting an ACME server."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_certbot_new_readiness_gate import _load_definitions


@pytest.fixture
def module():
    return _load_definitions()


def test_public_ipv4_is_issuable(module):
    assert module.unissuable_names(["8.8.8.8", "example.com"]) == []


@pytest.mark.parametrize(
    "name", ["10.0.0.1", "127.0.0.1", "192.0.2.1", "100.64.0.1", "224.0.0.1", "240.0.0.1", "::1", "2001:4860:4860::8888", "*.8.8.8.8", "localhost"]
)
def test_invalid_identifiers(module, name):
    assert module.unissuable_names([name]) == [name]


@pytest.mark.parametrize(
    ("profile", "challenge", "server", "expected"),
    [
        ("shortlived", "http", "letsencrypt", True),
        ("classic", "http", "letsencrypt", False),
        ("shortlived", "dns", "letsencrypt", False),
        ("shortlived", "http", "zerossl", False),
    ],
)
def test_ip_configuration(module, monkeypatch, profile, challenge, server, expected):
    module.IS_MULTISITE = False
    for key, value in {
        "SERVER_NAME": "8.8.8.8",
        "AUTO_LETS_ENCRYPT": "yes",
        "LETS_ENCRYPT_PROFILE": profile,
        "LETS_ENCRYPT_CHALLENGE": challenge,
        "LETS_ENCRYPT_SERVER": server,
        "EMAIL_LETS_ENCRYPT": "admin@example.com",
    }.items():
        monkeypatch.setenv(key, value)
    _, config = module.build_service_config("8.8.8.8")
    assert config["activated"] is expected
    if not expected:
        assert any("8.8.8.8 needs" in str(call) for call in module.LOGGER.warning.call_args_list)


def test_actual_issuance_command(module, tmp_path):
    module.resolve_certbot_entrypoint = Mock(return_value=["certbot"])
    module.certbot_log_backup_flags = Mock(return_value=[])
    module.select_account_id = Mock(return_value="existing-account")
    module.stream_certbot = Mock(return_value=True)
    module.Popen = Mock(return_value=SimpleNamespace(returncode=0))
    module.JOBS_PATH = tmp_path
    config = {
        "server_names": "example.com,8.8.8.8",
        "profile": "shortlived",
        "email": "admin@example.com",
        "challenge": "http",
        "staging": False,
        "force_renew": False,
        "acme_server": "letsencrypt",
        "acme_server_url": "https://acme.invalid/directory",
    }
    paths = SimpleNamespace(config_dir=tmp_path, work_dir=tmp_path, logs_dir=tmp_path)
    assert module.certbot_new("example.com", config, {}, paths) == 0
    command = module.Popen.call_args.args[0]
    assert command[command.index("--ip-address") + 1] == "8.8.8.8"
    assert command[command.index("-d") + 1] == "example.com"
    assert command[command.index("--preferred-profile") + 1] == "shortlived"
    assert command[command.index("--account") + 1] == "existing-account"
    assert "--preferred-challenges=http" in command


@pytest.mark.parametrize(
    ("configured", "existing", "expected"),
    [
        ({"example.com", "8.8.8.8"}, {"example.com"}, True),
        ({"example.com", "other.example"}, {"example.com"}, False),
        ({"8.8.8.8"}, set(), False),
        ({"8.8.8.8"}, {"example.com"}, False),
    ],
)
def test_only_ip_additions_expand_in_place(module, configured, existing, expected):
    assert module.ips_only_added(configured, existing) is expected


def test_incompatible_ip_does_not_block_dns_names(module, monkeypatch):
    module.IS_MULTISITE = False
    for key, value in {
        "SERVER_NAME": "example.com 8.8.8.8",
        "AUTO_LETS_ENCRYPT": "yes",
        "LETS_ENCRYPT_PROFILE": "classic",
        "LETS_ENCRYPT_CHALLENGE": "http",
        "LETS_ENCRYPT_SERVER": "letsencrypt",
    }.items():
        monkeypatch.setenv(key, value)
    names, config = module.build_service_config("example.com")
    assert names == ["example.com"]
    assert config["activated"] is True
