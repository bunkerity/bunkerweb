"""IPv4 and IPv6 literals as SERVER_NAME (GitHub #4120).

The service id is the first SERVER_NAME token and ends up in include paths, setting prefixes and the Lua
variable lookup. IPv6 is stored bare, lowercase and compressed: a bracketed id would turn every ``include``
below the service directory into a glob and silently load nothing.
"""

import json
import logging
import re
from importlib import import_module
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from Configurator import Configurator

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / "src/common/settings.json"
MODSEC_CONFS = ROOT / "src/common/core/modsecurity/confs"

REGEX = json.loads(SETTINGS.read_text())["SERVER_NAME"]["regex"]

VALID = [
    "",
    "www.example.com",
    "192.0.2.10",
    "2001:db8::1",
    "::1",
    "fe80::",
    "2001:db8:0:0:0:0:0:1",
    "192.0.2.10 2001:db8::1 www.example.com",
    "2001:db8::1 www.example.com",
]
INVALID = [
    "[2001:db8::1]",
    "2001:DB8::1",
    "fe80::1%eth0",
    "::ffff:192.0.2.1",
    "2001:db8::1/64",
    "1:2",
    "www.example.com:80",
    "a..b",
    "2001:db8::1 [2001:db8::2]",
    "2001:db8::g",
    "1:2:3:4:5:6:7:8:9:a",
]


@pytest.mark.parametrize("value", VALID)
def test_regex_matches(value):
    assert re.search(REGEX, value) is not None


@pytest.mark.parametrize("value", INVALID)
def test_regex_does_not_match(value):
    assert re.search(REGEX, value) is None


@pytest.fixture
def configure(monkeypatch, caplog):
    monkeypatch.delenv("IGNORE_REGEX_CHECK", raising=False)
    caplog.set_level(logging.DEBUG, logger="sn-ip")

    def build(variables):
        core = ROOT / "src/common/core"
        return Configurator(str(SETTINGS), str(core), "/nonexistent-ext", "/nonexistent-pro", variables, logging.getLogger("sn-ip"))

    return build


def test_an_ipv6_service_keeps_its_per_service_settings(configure):
    config = configure({"MULTISITE": "yes", "SERVER_NAME": "2001:db8::1", "2001:db8::1_USE_ANTIBOT": "captcha"}).get_config()
    assert config["SERVER_NAME"] == "2001:db8::1"
    assert config["2001:db8::1_USE_ANTIBOT"] == "captcha"
    assert config["2001:db8::1_SERVER_NAME"] == "2001:db8::1"


def test_a_non_canonical_ipv6_name_warns_and_is_kept(configure, caplog):
    config = configure({"MULTISITE": "yes", "SERVER_NAME": "2001:0db8:0:0:0:0:0:1"}).get_config()
    # never dropped: ignoring the global SERVER_NAME would remove every service
    assert config["SERVER_NAME"] == "2001:0db8:0:0:0:0:0:1"
    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING and "2001:db8::1" in r.message]
    assert len(warnings) == 1 and "2001:0db8:0:0:0:0:0:1" in warnings[0]


def test_a_canonical_ipv6_name_does_not_warn(configure, caplog):
    configure({"MULTISITE": "yes", "SERVER_NAME": "2001:db8::1 www.example.com"}).get_config()
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.fixture(scope="module")
def render(render_tree):
    return render_tree


MULTISITE = {"MULTISITE": "yes", "SERVER_NAME": "2001:db8::1 192.0.2.10 www.example.com"}


def test_server_name_carries_the_bracketed_twin_of_an_ipv6_name(render):
    tree = render(**MULTISITE, **{"2001:db8::1_SERVER_NAME": "2001:db8::1 www.example.org"})
    assert "server_name 2001:db8::1 [2001:db8::1] www.example.org;" in tree["2001:db8::1/server.conf"]


def test_ipv4_and_hostname_server_name_lines_are_unchanged(render):
    tree = render(MULTISITE="yes", SERVER_NAME="192.0.2.10 www.example.com")
    assert "\tserver_name 192.0.2.10;\n" in tree["192.0.2.10/server.conf"]
    assert "\tserver_name www.example.com;\n" in tree["www.example.com/server.conf"]


def test_an_ipv6_service_paths_hold_no_glob_character(render):
    tree = render(**MULTISITE)
    server = tree["2001:db8::1/server.conf"]
    includes = [line.split()[1].rstrip(";") for line in server.splitlines() if line.strip().startswith("include ")]
    assert "/etc/nginx/2001:db8::1/set-lua.conf" in includes
    assert "/etc/bunkerweb/configs/server-http/2001:db8::1/*.conf" in includes
    # the only wildcard is the final *.conf
    assert not [path for path in includes if re.search(r"[\[\]?*]", path.rsplit("/", 1)[0])]
    assert "include /etc/nginx/2001:db8::1/server.conf;" in tree["http.conf"]


def test_the_ipv6_service_rule_files_are_rendered_under_its_own_directory(render):
    tree = render(**MULTISITE)
    assert any(path.startswith("2001:db8::1/") for path in tree)
    assert not any("[" in path for path in tree)


def test_per_service_settings_reach_the_ipv6_service_render_only(render):
    tree = render(MULTISITE="yes", SERVER_NAME="2001:db8::1 192.0.2.10", **{"2001:db8::1_LISTEN_HTTP": "no"})
    assert "listen 0.0.0.0" not in tree["2001:db8::1/server.conf"]
    assert "listen 0.0.0.0" in tree["192.0.2.10/server.conf"]


def modsec_env():
    return Environment(loader=FileSystemLoader(str(MODSEC_CONFS)), lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)


def ip_host(template, **variables):
    base = {"USE_MODSECURITY": "yes", "USE_MODSECURITY_CRS": "yes", "USE_MODSECURITY_GLOBAL_CRS": "no", "MULTISITE": "yes"}
    return modsec_env().get_template(template).render(**{"import": import_module}, **(base | variables))


def rules(rendered):
    return [line for line in rendered.splitlines() if line.startswith("SecRule ")]


@pytest.mark.parametrize(
    "names,expected",
    [
        ("192.0.2.10", r"^(?:192\.0\.2\.10)(?::\d+)?$"),
        ("2001:db8::1", r"^(?:\[2001:db8::1\])(?::\d+)?$"),
        ("192.0.2.10 2001:db8::1 www.example.com", r"^(?:192\.0\.2\.10|\[2001:db8::1\])(?::\d+)?$"),
    ],
)
def test_per_service_rule_matches_only_the_services_own_literals(names, expected):
    out = ip_host("modsec-crs/ip-host.conf", SERVER_NAME=names)
    assert len(rules(out)) == 1
    assert f'"@rx {expected}"' in out
    assert "id:1007783" in out and "ctl:ruleRemoveById=920350" in out and "phase:1" in out


@pytest.mark.parametrize("names", ["www.example.com", ""])
def test_per_service_rule_is_absent_without_a_literal(names):
    assert ip_host("modsec-crs/ip-host.conf", SERVER_NAME=names).strip() == ""


@pytest.mark.parametrize(
    "overrides",
    [{"USE_MODSECURITY": "no"}, {"USE_MODSECURITY_CRS": "no"}, {"USE_MODSECURITY_GLOBAL_CRS": "yes"}],
)
def test_per_service_rule_is_gated(overrides):
    assert ip_host("modsec-crs/ip-host.conf", SERVER_NAME="192.0.2.10", **overrides).strip() == ""


def global_rule(services, **variables):
    all_vars = {
        "MULTISITE": "yes",
        "SERVER_NAME": " ".join(services),
        "USE_MODSECURITY": "yes",
        "USE_MODSECURITY_CRS": "yes",
        "USE_MODSECURITY_GLOBAL_CRS": "yes",
    }
    for service, names in services.items():
        all_vars[f"{service}_SERVER_NAME"] = names
    all_vars |= variables
    return ip_host(
        "http/ip-host.modsec-crs",
        all=all_vars,
        SERVER_NAME=all_vars["SERVER_NAME"],
        **{k: v for k, v in all_vars.items() if k in ("USE_MODSECURITY", "USE_MODSECURITY_CRS", "USE_MODSECURITY_GLOBAL_CRS", "MULTISITE")},
    )


def test_global_mode_emits_one_rule_with_the_union_of_every_literal():
    out = global_rule({"192.0.2.10": "192.0.2.10", "2001:db8::1": "2001:db8::1", "www.example.com": "www.example.com 198.51.100.7"})
    assert len(rules(out)) == 1
    assert out.count("id:1007783") == 1
    assert r"^(?:192\.0\.2\.10|\[2001:db8::1\]|198\.51\.100\.7)(?::\d+)?$" in out


def test_global_mode_is_absent_without_literal_and_in_per_service_mode():
    assert global_rule({"www.example.com": "www.example.com"}).strip() == ""
    assert global_rule({"192.0.2.10": "192.0.2.10"}, USE_MODSECURITY_GLOBAL_CRS="no").strip() == ""


STREAM = {
    "MULTISITE": "yes",
    "SERVER_NAME": "2001:db8::1 www.example.com",
    "2001:db8::1_SERVER_TYPE": "stream",
    "www.example.com_SERVER_TYPE": "stream",
    "2001:db8::1_USE_REVERSE_PROXY": "yes",
    "2001:db8::1_REVERSE_PROXY_HOST": "192.0.2.5:9000",
    "www.example.com_USE_REVERSE_PROXY": "yes",
    "www.example.com_REVERSE_PROXY_HOST": "192.0.2.6:9000",
}


def test_a_stream_ipv6_service_names_its_upstream_with_brackets(render):
    # NGINX reads a variable proxy_pass value as host:port before it looks for an upstream of that name, so the bare
    # id "2001:db8::1" fails at request time with "invalid port in upstream" (probe P3, docker run of stock nginx)
    tree = render(**STREAM)
    assert "upstream [2001:db8::1] {" in tree["stream.conf"]
    assert 'set $backend "[2001:db8::1]";' in tree["2001:db8::1/server-stream/reverse-proxy.conf"]
    assert "server_name '2001:db8::1';" in tree["2001:db8::1/server-stream.conf"]


def test_a_stream_ipv6_upstream_name_matches_the_proxy_pass_variable(render):
    tree = render(**STREAM)
    names = re.findall(r"^upstream (\S+) \{", tree["stream.conf"], re.M)
    backend = re.search(r'set \$backend "([^"]+)";', tree["2001:db8::1/server-stream/reverse-proxy.conf"]).group(1)
    assert backend in names


def test_a_stream_hostname_service_renders_the_same_upstream_as_before(render):
    tree = render(**STREAM)
    assert "upstream www.example.com {" in tree["stream.conf"]
    assert 'set $backend "www.example.com";' in tree["www.example.com/server-stream/reverse-proxy.conf"]


def test_a_single_site_stream_ipv6_service_names_its_upstream_with_brackets(render):
    tree = render(MULTISITE="no", SERVER_NAME="2001:db8::1", SERVER_TYPE="stream", USE_REVERSE_PROXY="yes", REVERSE_PROXY_HOST="192.0.2.5:9000")
    assert "upstream [2001:db8::1] {" in tree["stream.conf"]
    assert 'set $backend "[2001:db8::1]";' in tree["server-stream/reverse-proxy.conf"]
