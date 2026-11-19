"""IPv6 service prefixes survive physical env files and the custom-config saver."""

import logging
from pathlib import Path

import pytest

from Configurator import Configurator
from env_file import KEY_RX, parse_env_file
from save_config import CUSTOM_CONF_RX
from test_save_config_cli_outcomes import saver  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("service", ["2001:db8::1", "::1", "fe80::", "2001:db8:0:0:0:0:0:1"])
def test_ipv6_file_settings_match_dictionary_input(tmp_path, service):
    certificate = "-----BEGIN CERTIFICATE-----\nQUJDRA==\n-----END CERTIFICATE-----"
    variables = {
        "MULTISITE": "yes",
        "SERVER_NAME": service,
        f"{service}_CUSTOM_SSL_CERT_DATA": certificate,
        f"{service}_CUSTOM_SSL_KEY_DATA": "QUJD\nRA==",
        f"{service}_USE_ANTIBOT": "captcha",
        f"{service}_REVERSE_PROXY_HOST_2": "http://backend:8080",
    }
    path = tmp_path / "variables.env"
    path.write_text("".join(f"{key}={value}\n" for key, value in variables.items()))
    args = (str(ROOT / "src/common/settings.json"), str(ROOT / "src/common/core"), str(tmp_path / "external"), str(tmp_path / "pro"))
    expected = Configurator(*args, variables, logging.getLogger("ipv6-env")).get_config()
    actual = Configurator(*args, str(path), logging.getLogger("ipv6-env")).get_config()
    assert actual == expected
    assert actual[f"{service}_USE_ANTIBOT"] == "captcha"
    assert actual[f"{service}_CUSTOM_SSL_CERT_DATA"] == certificate
    assert parse_env_file(path)[f"{service}_USE_ANTIBOT"] == "captcha"


@pytest.mark.parametrize("service", ["2001:db8::1", "::1", "fe80::", "2001:db8:0:0:0:0:0:1", "192.0.2.10", "app.example.com"])
def test_saver_preserves_service_custom_configs(saver, monkeypatch, service):  # noqa: F811 - reused pytest fixture
    monkeypatch.setenv(f"{service}_CUSTOM_CONF_SERVER_HTTP_lockdown", "deny all;")
    assert saver.run() == 0
    configs = saver.db.save_custom_configs.call_args.args[0]
    assert configs == [{"value": "# CREATED BY ENV\ndeny all;", "exploded": (service, "SERVER_HTTP", "lockdown"), "is_draft": False}]


@pytest.mark.parametrize(
    "key",
    [
        "USE_ANTIBOT:bad",
        "example.com:80_USE_ANTIBOT",
        "prefix_2001:db8::1_USE_ANTIBOT",
        "2001:db8::1_USE:ANTIBOT",
        "[::1]_USE_ANTIBOT",
        "fe80::1%eth0_USE_ANTIBOT",
        "2001:DB8::1_USE_ANTIBOT",
        "1:2_USE_ANTIBOT",
    ],
)
def test_colons_are_only_accepted_in_bare_ipv6_service_prefixes(key):
    assert KEY_RX.fullmatch(key) is None


@pytest.mark.parametrize("service", ["example.com:80", "[::1]", "fe80::1%eth0", "2001:DB8::1", "1:2"])
def test_saver_does_not_accept_other_colon_prefixes(service):
    assert CUSTOM_CONF_RX.fullmatch(f"{service}_CUSTOM_CONF_SERVER_HTTP_lockdown") is None
