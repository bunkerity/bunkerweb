"""IPv6 setting boundaries use the shipped manifests, not copied validation patterns."""

import ipaddress
import json
import logging
import re
from pathlib import Path

import pytest

from Configurator import Configurator

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / "src/common/settings.json"
CORE = ROOT / "src/common/core"


def _shipped():
    found = {}
    for path in [SETTINGS, *sorted(CORE.glob("*/plugin.json"))]:
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, setting in (data if path == SETTINGS else data.get("settings", {})).items():
            if isinstance(setting, dict) and setting.get("regex"):
                found[name] = setting
    return found


SHIPPED = _shipped()
URL_LISTS = sorted(name for name in SHIPPED if name.endswith("_URLS"))
IP_LISTS = sorted(name for name, setting in SHIPPED.items() if setting["type"] == "multivalue" and (name.endswith("_IP") or name == "REAL_IP_FROM"))
ORIGINS = ("ANTIBOT_CAPJS_FRONTEND_URL", "ANTIBOT_CAPJS_BACKEND_URL")
SIGNINS = ("GRPC_AUTH_REQUEST_SIGNIN_URL", "REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL")
ADDRESSES = (
    "::",
    "::1",
    "2001:db8::1",
    "2001:0DB8:0000:0000:0000:0000:0000:0001",
    "::ffff:192.0.2.1",
    "::FFFF:192.0.2.1",
    "0:0:0:0:0:FFFF:192.0.2.1",
    "2001:db8:0:0:0:0:192.0.2.1",
    "2001:db8::FFFF:192.0.2.1",
)


def _accepts(name, value):
    # Configurator and Database.is_valid_setting use search, not fullmatch.
    return re.search(SHIPPED[name]["regex"], value) is not None


@pytest.mark.parametrize("name", URL_LISTS)
def test_url_lists_accept_ipv6_authorities(name):
    for address in ADDRESSES:
        for scheme in ("http", "https"):
            for auth in ("", "user:pass@"):
                value = f"{scheme}://{auth}[{address}]:8080/list.csv?format=json#key=value"
                assert _accepts(name, value), (name, value)
    assert _accepts(name, "http://[::1]/list https://example.com/list file:///tmp/list.txt")


@pytest.mark.parametrize("name", URL_LISTS)
def test_url_lists_keep_existing_formats_and_restrictions(name):
    for value in ("", "http://example.com/list", "https://user:pass@192.0.2.1:8080/list?q=a%20b#key=value", "file:///tmp/list.txt"):
        assert _accepts(name, value), (name, value)
    for value in ("ftp://example.com/list", "http://[::1", "http://::1]", "http://[::g]/list", "http://[]/list", "http://[::ffff:1١3.80.255.247]/list"):
        assert not _accepts(name, value), (name, value)
    for character in (";", "{", "}", '"', "'", "\\", "\t", "\r", "\n"):
        value = f"http://[::1]/bad{character}path"
        assert not _accepts(name, value), (name, value)
    assert not _accepts(name, "http://[::1]/bad path")


@pytest.mark.parametrize("name", ORIGINS)
def test_capjs_origins_accept_ipv6_without_allowing_paths(name):
    for address in ADDRESSES:
        for value in (f"http://[{address}]", f"https://[{address}]:3000"):
            assert _accepts(name, value), (name, value)
    for value in ("", "https://cap.example.com", "http://cap-server:3000", "http://192.0.2.1:3000"):
        assert _accepts(name, value), (name, value)
    for suffix in ("/siteverify", "/", "?q=1", "#fragment", ";", "{", "}", '"', "'", "\\", " path", "\tpath", "\npath"):
        assert not _accepts(name, f"http://[::1]:3000{suffix}"), (name, suffix)
    for value in ("ftp://[::1]", "http://user:pass@[::1]", "http://[::g]", "http://::1", "http://[::1", "http://[::ffff:1١3.80.255.247]"):
        assert not _accepts(name, value), (name, value)


@pytest.mark.parametrize("name", SIGNINS)
def test_signin_urls_accept_ipv6_and_keep_nginx_variables(name):
    for address in ADDRESSES:
        for scheme in ("http", "https", "$scheme"):
            value = f"{scheme}://[{address}]:8080/signin?rd=$request_uri"
            assert _accepts(name, value), (name, value)
    for value in ("", "https://$host/signin?rd=$request_uri", "$scheme://user:pass@example.com/signin"):
        assert _accepts(name, value), (name, value)
    for character in (";", "{", "}", '"', "'", "\\", "#", " ", "\t", "\r", "\n"):
        value = f"http://[::1]/bad{character}path"
        assert not _accepts(name, value), (name, value)
    for value in ("ftp://[::1]/signin", "http://[::g]/signin", "http://[::1/signin", "$G://rb@[9:3:8bd:9:2:AFb:1١3.80.255.247]:5/"):
        assert not _accepts(name, value), (name, value)


@pytest.mark.parametrize("name,scheme", [("REVERSE_PROXY_HOST", "http"), ("GRPC_HOST", "grpc"), ("GRPC_HOST", "grpcs")])
def test_upstream_urls_keep_ipv6_and_injection_guards(name, scheme):
    assert _accepts(name, f"{scheme}://[2001:db8::1]:8080")
    for character in (";", "{", "}", '"', "'", " ", "\t", "\r", "\n", "#"):
        value = f"{scheme}://[::1]:8080{character}bad"
        assert not _accepts(name, value), (name, value)
    if name == "GRPC_HOST":
        assert not _accepts(name, "http://[::1]:8080")


@pytest.mark.parametrize("name", IP_LISTS)
def test_ip_lists_keep_ipv6_spellings_mapped_addresses_and_cidrs(name):
    for value in (*ADDRESSES, "2001:db8::/32", "2001:DB8::1/128", "::/0", "::FFFF:192.0.2.0/120", "192.0.2.1", "192.0.2.0/24", "0.0.0.0/0"):
        assert _accepts(name, value), (name, value)
        assert _accepts(name, f"198.51.100.1 {value} 2001:db8:1::/48"), (name, value)


@pytest.mark.parametrize("name", IP_LISTS)
def test_ip_lists_reject_zone_ids_in_every_list_position(name):
    for scoped in ("fe80::1%eth0", "fe80::1%1", "fe80::1%eth0/64", "FE80::1%eth0", "2001:db8::1%eth0", "fe80::1%25eth0"):
        for value in (scoped, f"{scoped} 2001:db8::/32", f"2001:db8::/32 {scoped}", f"192.0.2.1 {scoped} 2001:db8::/32"):
            assert not _accepts(name, value), (name, value)


@pytest.mark.parametrize("name", IP_LISTS)
def test_ip_lists_validate_the_group_count_with_an_ipv4_tail(name):
    for left in range(7):
        for right in range(7):
            value = ":".join(["2001"] * left) + "::" + ":".join(["db8"] * right) + (":" if right else "") + "192.0.2.1"
            try:
                ipaddress.IPv6Address(value)
                valid = True
            except ipaddress.AddressValueError:
                valid = False
            assert _accepts(name, value) is valid, (name, value)


@pytest.mark.parametrize("name", IP_LISTS)
def test_ip_lists_keep_invalid_address_and_cidr_guards(name):
    for value in (
        "2001:db8::/129",
        "192.0.2.0/33",
        "256.0.0.1",
        "2001::db8::1",
        "[::1]",
        "2001:db8::1;",
        "fe80::1%",
        "2001:db8::1\t192.0.2.1",
        "::FFFF:1١3.80.255.247",
        "0:0:0:0:0:ffff:1١3.80.255.247",
        "2001:db8::ffff:1١3.80.255.247",
    ):
        assert not _accepts(name, value), (name, value)


@pytest.mark.parametrize("multisite", [False, True])
@pytest.mark.parametrize(
    "name,value,accepted",
    [
        ("BLACKLIST_IP_URLS", "http://[2001:db8::1]:8080/list", True),
        ("BLACKLIST_IP_URLS", "http://[::1]/list;bad", False),
        ("BLACKLIST_IP", "2001:0DB8:0000:0000:0000:0000:0000:0001 ::FFFF:192.0.2.0/120", True),
        ("BLACKLIST_IP", "2001:db8::/32 fe80::1%eth0", False),
    ],
)
def test_configurator_enforces_real_ipv6_setting_boundaries(monkeypatch, multisite, name, value, accepted):
    monkeypatch.delenv("IGNORE_REGEX_CHECK", raising=False)
    key = f"www.example.com_{name}" if multisite else name
    variables = {"MULTISITE": "yes" if multisite else "no", "SERVER_NAME": "www.example.com", key: value}
    configurator = Configurator(str(SETTINGS), str(CORE), [], [], variables, logging.getLogger(__name__))
    config = configurator.get_config()
    assert (key in configurator.explicit_keys) is accepted
    assert config[key] == (value if accepted else SHIPPED[name]["default"])
