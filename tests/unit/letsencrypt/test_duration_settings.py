"""LETS_ENCRYPT_DNS_PROPAGATION and the three ZeroSSL API times accept the 1.6.16 time suffixes.

``build_service_config`` lowercased the propagation value, which turns ``2M`` (two months) into
``2m`` (two minutes): the unit is case sensitive, only the literal ``default`` is case folded.
"""

import pytest
from test_certbot_new_readiness_gate import _load_definitions

import common_utils


@pytest.fixture
def module():
    mod = _load_definitions()
    # the loader replaces common_utils with a mock; the parser is the point of this file
    mod.parse_duration_int = common_utils.parse_duration_int
    mod.IS_MULTISITE = False
    return mod


def _config(module, monkeypatch, **env):
    base = {
        "SERVER_NAME": "example.com",
        "AUTO_LETS_ENCRYPT": "yes",
        "EMAIL_LETS_ENCRYPT": "admin@example.com",
        "LETS_ENCRYPT_CHALLENGE": "dns",
        "LETS_ENCRYPT_DNS_PROVIDER": "cloudflare",
        "LETS_ENCRYPT_SERVER": "zerossl",
    }
    for key, value in (base | env).items():
        monkeypatch.setenv(key, value)
    return module.build_service_config("example.com")[1]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("120", "120"),
        ("2m", "120"),
        ("2M", str(2 * 2592000)),
        ("1h", "3600"),
        ("default", "default"),
        ("DEFAULT", "default"),
        ("0", "default"),
        ("junk", "default"),
    ],
)
def test_dns_propagation_is_converted_to_seconds_and_keeps_the_unit_case(module, monkeypatch, value, expected):
    assert _config(module, monkeypatch, LETS_ENCRYPT_DNS_PROPAGATION=value)["dns_propagation"] == expected


@pytest.mark.parametrize(
    ("retry_delay", "connect_timeout", "max_time", "expected"),
    [
        ("2s", "5s", "20s", (2, 5, 20)),
        ("1m", "1m", "2m", (60, 60, 120)),
        ("3", "7", "30", (3, 7, 30)),
        ("0", "0", "0", (0, 5, 20)),
        ("abc", "x", "y", (2, 5, 20)),
    ],
)
def test_zerossl_api_times_accept_suffixes(module, monkeypatch, retry_delay, connect_timeout, max_time, expected):
    config = _config(
        module,
        monkeypatch,
        LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY=retry_delay,
        LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT=connect_timeout,
        LETS_ENCRYPT_ZEROSSL_API_MAX_TIME=max_time,
    )
    assert (config["zerossl_api_retry_delay"], config["zerossl_api_connect_timeout"], config["zerossl_api_max_time"]) == expected
