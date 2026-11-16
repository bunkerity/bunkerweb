"""A feed line carrying a zone id (``fe80::1%eth0``) is dropped by every IP feed download job.

``ipaddress.ip_address`` accepts a scope id since Python 3.9, so the validators of the download jobs let it through. A zone
id names an interface of the host that downloaded the feed, not an address the matcher or NGINX can load, and one such line
makes the whole list unusable. The job scripts run on import, so the validator is cut out of each shipped file by name.
"""

import ast
from contextlib import suppress
from ipaddress import ip_address, ip_network
from pathlib import Path
from re import compile as re_compile
from typing import Tuple

import pytest

CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"

# (plugin, function, call shape, kinds that take IPs)
JOBS = [
    ("blacklist", "check_line", "kind", ("IP", "IGNORE_IP")),
    ("greylist", "check_line", "kind", ("IP",)),
    ("whitelist", "check_line", "kind", ("IP",)),
    ("dnsbl", "check_ip_line", "plain", ()),
    ("realip", "check_line", "plain", ()),
]


def load(plugin: str, name: str):
    path = CORE / plugin / "jobs" / f"{plugin}-download.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = {
        "suppress": suppress,
        "ip_address": ip_address,
        "ip_network": ip_network,
        "re_compile": re_compile,
        "Tuple": Tuple,
        "rdns_rx": re_compile(rb"^[^ ]+$"),
        "asn_rx": re_compile(rb"^\d+$"),
        "uri_rx": re_compile(rb"^/"),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def accepts(plugin: str, name: str, shape: str, kinds, line: bytes) -> bool:
    check = load(plugin, name)
    if shape == "kind":
        return check(kinds[0], line)[0]
    result = check(line)
    # dnsbl returns the line or None, realip a (bool, line) pair
    return bool(result) if not isinstance(result, tuple) else result[0]


@pytest.mark.parametrize("plugin,name,shape,kinds", JOBS)
@pytest.mark.parametrize("line", [b"fe80::1%eth0", b"fe80::1%25", b"2001:db8::1%1"])
def test_a_zone_id_line_is_dropped(plugin, name, shape, kinds, line):
    assert accepts(plugin, name, shape, kinds, line) is False


@pytest.mark.parametrize("plugin,name,shape,kinds", JOBS)
@pytest.mark.parametrize("line", [b"192.0.2.1", b"198.51.100.0/24", b"2001:db8::1", b"2001:db8::/32"])
def test_a_plain_address_or_network_is_still_kept(plugin, name, shape, kinds, line):
    assert accepts(plugin, name, shape, kinds, line) is True


def test_blacklist_ignore_ip_drops_a_zone_id_too():
    check = load("blacklist", "check_line")
    assert check("IGNORE_IP", b"fe80::1%eth0") == (False, b"")
    assert check("IGNORE_IP", b"192.0.2.1") == (True, b"192.0.2.1")


def test_a_zone_id_does_not_disturb_the_non_ip_kinds():
    for plugin in ("blacklist", "greylist", "whitelist"):
        check = load(plugin, "check_line")
        assert check("RDNS", b"host%1.example.com")[0] is True
        assert check("URI", b"/a%20b")[0] is True
