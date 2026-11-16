"""The antibot allow rule matches the Host header, which carries an IPv6 literal bracketed."""

from importlib import import_module
from os import environ
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# ANTIBOT_TEMPLATE_DIR lets a reviewer point the test at a copy of the template from another revision.
TEMPLATES = Path(environ.get("ANTIBOT_TEMPLATE_DIR", Path(__file__).resolve().parents[3] / "src/common/core/antibot/confs/http"))


def render(**variables):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    return env.get_template("antibot.modsec-crs").render(**{"import": import_module}, **variables)


def host_rule(rendered):
    return [line for line in rendered.splitlines() if line.startswith("SecRule REQUEST_HEADERS:Host")]


def test_single_site_names_are_matched_the_way_the_host_header_carries_them():
    out = render(SERVER_NAME="www.example.com 192.0.2.10 2001:db8::1", MULTISITE="no", ANTIBOT_URI="/challenge", all={})
    assert r"^(?:www\.example\.com|192\.0\.2\.10|\[2001:db8::1\])(?::\d+)?$" in host_rule(out)[0]


def test_multisite_names_are_matched_the_way_the_host_header_carries_them():
    all_vars = {
        "2001:db8::1_USE_ANTIBOT": "captcha",
        "2001:db8::1_SERVER_NAME": "2001:db8::1",
        "a.example.com_USE_ANTIBOT": "no",
        "a.example.com_SERVER_NAME": "a.example.com",
    }
    out = render(SERVER_NAME="2001:db8::1 a.example.com", MULTISITE="yes", ANTIBOT_URI="/challenge", all=all_vars)
    assert r"^(?:\[2001:db8::1\])(?::\d+)?$" in host_rule(out)[0]
