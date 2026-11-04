"""One HTTP/3 connection must be counted in the HTTP/3 zone only, never in the HTTP/1 one.

``limitconn.conf`` keyed the HTTP/1 zone on ``$http2`` alone (``map $http2 $v1ip``), and ``$http2``
is empty for HTTP/3 as well as for HTTP/1.x. Every QUIC connection therefore also landed in the
HTTP/1 zone, whose cap is the low one, and a browser multiplexing a handful of HTTP/3 streams got
429. The key is now the concatenation of ``$http2`` and ``$http3``, empty only for HTTP/1.x.

The test evaluates the rendered ``map`` blocks the way NGINX does (exact match, else ``default``)
for each protocol and reads which ``limit_conn_zone`` each connection ends up counted in.
"""

import re

import pytest

from _t4_helpers import full_renderer

# ($http2, $http3) as NGINX sets them: "h2" on HTTP/2, "h3" on HTTP/3, empty otherwise.
PROTOCOLS = {"HTTP/1.1": ("", ""), "HTTP/2": ("h2", ""), "HTTP/3": ("", "h3")}
ZONE_OF = {"HTTP/1.1": "v1ips", "HTTP/2": "v2ips", "HTTP/3": "v3ips"}


@pytest.fixture(scope="module")
def limitconn():
    with full_renderer() as render:
        return render(MULTISITE="no", SERVER_NAME="app.example.com", USE_LIMIT_CONN="yes", HTTP3="yes")["http/limitconn.conf"]


def parse_maps(text):
    """``{variable: (source expression, {key: value}, default)}`` of every ``map`` block."""
    maps = {}
    for source, variable, body in re.findall(r'^map\s+("?[^\s{]+"?)\s+(\$\w+)\s*\{(.*?)^\}', text, re.S | re.M):
        entries, default = {}, None
        for line in body.splitlines():
            line = line.split("#", 1)[0].strip().rstrip(";")
            if not line:
                continue
            key, value = line.split(None, 1)
            if key == "default":
                default = value.strip('"')
            else:
                entries[key.strip('"')] = value.strip('"')
        maps[variable] = (source.strip('"'), entries, default)
    return maps


def evaluate(maps, variable, nginx_variables):
    source, entries, default = maps[variable]
    key = re.sub(r"\$(\w+)", lambda match: nginx_variables.get(match.group(1), ""), source)
    return entries.get(key, default)


def counted_zones(text, http2, http3):
    """The ``limit_conn_zone`` names whose key is non-empty for a connection with these protocol variables."""
    maps = parse_maps(text)
    nginx_variables = {"http2": http2, "http3": http3, "binary_remote_addr": "<addr>"}
    zones = re.findall(r"^limit_conn_zone\s+(\$\w+)\s+zone=(\w+):", text, re.M)
    assert {zone for _, zone in zones} == {"v1ips", "v2ips", "v3ips"}
    counted = []
    for variable, zone in zones:
        value = evaluate(maps, variable, nginx_variables)
        value = nginx_variables.get(value[1:], "") if value.startswith("$") else value
        if value:
            counted.append(zone)
    return counted


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_each_connection_is_counted_in_exactly_its_own_zone(limitconn, protocol):
    assert counted_zones(limitconn, *PROTOCOLS[protocol]) == [ZONE_OF[protocol]]


def test_an_http3_connection_does_not_reach_the_http1_zone(limitconn):
    assert "v1ips" not in counted_zones(limitconn, *PROTOCOLS["HTTP/3"])
