"""Legacy nginx operand quotes preserve routing; every location stays one quoted token."""

import re

import pytest

from _t4_helpers import CONFS, CORE, full_renderer
from _t5_helpers import configured

PLUGINS = {
    "reverseproxy": ("REVERSE_PROXY_URL", "reverse-proxy.conf", "proxy_set_header"),
    "grpc": ("GRPC_URL", "grpc.conf", "grpc_set_header"),
    "redirect": ("REDIRECT_FROM", "redirect.conf", None),
}
BASE = {
    "SERVER_NAME": "example.com",
    "USE_REVERSE_PROXY": "yes",
    "REVERSE_PROXY_HOST_1": "http://backend:8080",
    "USE_GRPC": "yes",
    "GRPC_HOST_1": "grpc://backend:50051",
    "REDIRECT_TO_1": "https://new.example.com",
}


@pytest.fixture(scope="module")
def render_locations():
    with full_renderer() as render:

        def locations(value):
            settings = {f"{name}_1": value for name, _, _ in PLUGINS.values()}
            return render(**(BASE | settings))

        yield locations


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize(
    "value,modifier,operand",
    [
        ("/plain/", "", "/plain/"),
        ("''/once/''", "", "'/once/'"),
        ('""/once/""', "", '"/once/"'),
        ("'/mismatch/\"", "", "'/mismatch/\""),
        ('"', "", '"'),
        ('"/quoted/"', "", "/quoted/"),
        ("'/quoted/'", "", "/quoted/"),
        ('"/brace{2}/"', "", "/brace{2}/"),
        ('~ "^/api/[a-z]{2}/"', "~", "^/api/[a-z]{2}/"),
        ("~ '^/api/[a-z]{2}/'", "~", "^/api/[a-z]{2}/"),
        ("~ ^/api/[a-z]{2}/", "~", "^/api/[a-z]{2}/"),
        ('~* "^/Api/"', "~*", "^/Api/"),
        ('= "/exact/"', "=", "/exact/"),
        ("^~ '/prefix/'", "^~", "/prefix/"),
        ("~ ^/api/", "~", "^/api/"),
        ("^/implicit/$", "~", "^/implicit/$"),
    ],
)
def test_legacy_operands_keep_location_and_prefix_header(render_locations, plugin, value, modifier, operand):
    name, filename, header = PLUGINS[plugin]
    config = configured(**(BASE | {f"{name}_1": value}))
    assert config.get(f"{name}_1") == value, "legacy value must survive Configurator validation"
    output = render_locations(value)[f"server-http/{filename}"]
    encoded = operand.replace("\\", "\\\\").replace('"', '\\"')
    expected = f'location {modifier + " " if modifier else ""}"{encoded}" {{'
    assert expected in output
    if header and not modifier and operand.startswith("/"):
        assert f'{header} X-Forwarded-Prefix "{encoded}";' in output


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize("prefix", ["", "~ "])
@pytest.mark.parametrize("payload", ['"', "\\", ";", "{", "}", "\n", "$var", "tail\\", '";return 200;#'])
def test_injection_payload_stays_inside_one_location_token(render_locations, plugin, prefix, payload):
    name, filename, _ = PLUGINS[plugin]
    value = prefix + "/probe/" + payload
    config = configured(**(BASE | {f"{name}_1": value}))
    accepted = config.get(f"{name}_1") == value
    # Semicolon and embedded whitespace stay rejected; ConfigMap trailing newline stays valid.
    assert accepted == (";" not in value and not any(c.isspace() for c in value.removeprefix(prefix).rstrip("\n")))
    output = render_locations(value)[f"server-http/{filename}"]
    # A lexer-level bound: only escaped quotes/backslashes can occur inside this token.
    matches = list(re.finditer(r'^location (?:(~\*|~|\^~|=) )?"((?:[^"\\]|\\.)*)" \{\n', output, re.M | re.S))
    assert len(matches) == output.count("location ") == 1
    operand = "/probe/" + payload if accepted else "/"
    encoded = operand.replace("\\", "\\\\").replace('"', '\\"')
    assert matches[0].group(2) == encoded
    assert (matches[0].group(1) or "") == (prefix.strip() if accepted else "")
    assert "\nreturn 200;" not in output


@pytest.fixture(scope="module")
def raw_templator(tmp_path_factory):
    """Exercise the DB-to-Templator boundary without Configurator filtering payloads."""
    import Templator as T

    sandbox = tmp_path_factory.mktemp("raw-location-render")
    plugins = sandbox / "plugins"
    pro_plugins = sandbox / "pro-plugins"
    plugins.mkdir()
    pro_plugins.mkdir()
    original_sep = T.sep
    T.sep = str(sandbox)
    try:
        config = configured(**BASE)
        yield T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(sandbox / "out"), "/etc/nginx", config, config, config)
    finally:
        T.sep = original_sep


@pytest.mark.parametrize("plugin", PLUGINS)
@pytest.mark.parametrize("modifier", ["", "~"])
@pytest.mark.parametrize("quote", ["", '"', "'"])
@pytest.mark.parametrize("payload", ['"', "\\", ";", "{", "}", "\n", "$var", "tail\\", '";return 200;#'])
def test_raw_template_keeps_payload_inside_quoted_operand(raw_templator, plugin, modifier, quote, payload):
    name, filename, _ = PLUGINS[plugin]
    operand = "/probe/" + payload
    value = (modifier + " " if modifier else "") + quote + operand + quote
    config = raw_templator._config | {f"{name}_1": value}
    template_vars = raw_templator._base_template_vars | config | {"all": config}
    template = f"server-http/{filename}"
    assert raw_templator._render_template(template, template_vars)
    output = (raw_templator._output / template).read_text()
    match = re.search(r'^location (?:(~\*|~|\^~|=) )?"((?:[^"\\]|\\.)*)" \{\n', output, re.M | re.S)
    assert match is not None, output
    assert match.group(2) == operand.replace("\\", "\\\\").replace('"', '\\"')
    assert (match.group(1) or "") == modifier
    # Everything after the location opening brace must be byte-for-byte unchanged.
    clean_config = raw_templator._config | {f"{name}_1": (modifier + " " if modifier else "") + "/probe/"}
    assert raw_templator._render_template(template, raw_templator._base_template_vars | clean_config | {"all": clean_config})
    clean = (raw_templator._output / template).read_text()
    remainder = output[match.end() :]  # noqa: E203
    clean_remainder = clean.split('" {\n', 1)[1]
    if plugin != "redirect" and not modifier:
        # Prefix header is the only other legitimate consumer of this operand.
        encoded = operand.replace("\\", "\\\\").replace('"', '\\"')
        remainder = remainder.replace(f'X-Forwarded-Prefix "{encoded}";', 'X-Forwarded-Prefix "/probe/";')
    assert remainder == clean_remainder
