"""The reverse proxy template side of dev 9ed8ea52e: ``$bw_reverse_proxy_host``.

``letsencrypt.lua`` replaces the upstream ``Host`` of a passed-through ACME challenge by the requested
name (``tests/unit/letsencrypt/test_acme_passthrough.py``). It can only do that through an nginx
variable, and the variable has to exist exactly when the Lua side touches it:

  * ``LETS_ENCRYPT_PASSTHROUGH=yes`` and a LITERAL ``REVERSE_PROXY_CUSTOM_HOST``: the template declares
    ``set $bw_reverse_proxy_host "<custom host>"`` once in the server block and the ``Host`` header of
    every location reads it;
  * anything else renders exactly what it rendered before: a fixed host, or ``$host``, or a host built
    from nginx variables (a server-scope ``set`` would evaluate those before ``auth_request_set`` ran).
"""

from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/reverseproxy"
LE_PLUGIN = ROOT / "src/common/core/letsencrypt"


def render(**settings):
    # Templator's whitespace flags, verbatim: a harness with other flags proves nothing about the output.
    defaults = {key: value["default"] for key, value in json.loads((PLUGIN / "plugin.json").read_text())["settings"].items()}
    defaults["LETS_ENCRYPT_PASSTHROUGH"] = json.loads((LE_PLUGIN / "plugin.json").read_text())["settings"]["LETS_ENCRYPT_PASSTHROUGH"]["default"]
    defaults.update(USE_REVERSE_PROXY="yes", SERVER_NAME="example.com", REVERSE_PROXY_HOST="http://backend:8080")
    defaults.update(settings)
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    fake_pathlib = SimpleNamespace(Path=lambda _path: SimpleNamespace(is_file=lambda: False))
    environment.globals["import"] = lambda name: fake_pathlib if name == "pathlib" else import_module(name)
    return environment.from_string((PLUGIN / "confs/server-http/reverse-proxy.conf").read_text()).render(all=defaults, **defaults)


def host_lines(output):
    return [line.strip() for line in output.splitlines() if line.strip().startswith("proxy_set_header Host ")]


def test_a_literal_custom_host_with_passthrough_reads_the_variable():
    output = render(LETS_ENCRYPT_PASSTHROUGH="yes", REVERSE_PROXY_CUSTOM_HOST="backend.local")
    assert output.count('set $bw_reverse_proxy_host "backend.local";') == 1
    assert host_lines(output) == ["proxy_set_header Host $bw_reverse_proxy_host;"]


def test_the_variable_is_declared_once_for_every_location():
    output = render(
        LETS_ENCRYPT_PASSTHROUGH="yes",
        REVERSE_PROXY_CUSTOM_HOST="backend.local",
        REVERSE_PROXY_URL="/",
        REVERSE_PROXY_HOST_1="http://other:8080",
        REVERSE_PROXY_URL_1="/api",
    )
    assert output.count("set $bw_reverse_proxy_host ") == 1
    assert host_lines(output) == ["proxy_set_header Host $bw_reverse_proxy_host;"] * 2


@pytest.mark.parametrize(
    "case, settings, host_header",
    [
        ("pass-through off", {"LETS_ENCRYPT_PASSTHROUGH": "no", "REVERSE_PROXY_CUSTOM_HOST": "backend.local"}, 'proxy_set_header Host "backend.local";'),
        ("pass-through unset", {"REVERSE_PROXY_CUSTOM_HOST": "backend.local"}, 'proxy_set_header Host "backend.local";'),
        (
            "a host built from nginx variables",
            {"LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "$http_host"},
            'proxy_set_header Host "$http_host";',
        ),
        ("a variable inside a literal", {"LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": "api-$host"}, 'proxy_set_header Host "api-$host";'),
        ("no custom host", {"LETS_ENCRYPT_PASSTHROUGH": "yes", "REVERSE_PROXY_CUSTOM_HOST": ""}, "proxy_set_header Host $host;"),
    ],
)
def test_everything_else_renders_what_it_rendered_before(case, settings, host_header):
    output = render(**settings)
    assert "bw_reverse_proxy_host" not in output, case
    assert host_lines(output) == [host_header], case


def test_without_the_reverse_proxy_nothing_is_declared():
    output = render(USE_REVERSE_PROXY="no", LETS_ENCRYPT_PASSTHROUGH="yes", REVERSE_PROXY_CUSTOM_HOST="backend.local")
    assert "bw_reverse_proxy_host" not in output


def test_a_custom_host_header_still_wins():
    """``REVERSE_PROXY_HEADERS`` naming ``Host`` replaces the generated header, variable or not: only the user's line remains."""
    output = render(LETS_ENCRYPT_PASSTHROUGH="yes", REVERSE_PROXY_CUSTOM_HOST="backend.local", REVERSE_PROXY_HEADERS="Host fixed.example")
    assert host_lines(output) == ["proxy_set_header Host fixed.example;"]


def test_the_directive_is_alone_on_its_line():
    output = render(LETS_ENCRYPT_PASSTHROUGH="yes", REVERSE_PROXY_CUSTOM_HOST="backend.local")
    line = next(line for line in output.splitlines() if "set $bw_reverse_proxy_host" in line)
    assert line == 'set $bw_reverse_proxy_host "backend.local";'
