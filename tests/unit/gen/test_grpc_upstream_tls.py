"""gRPC upstream TLS, per-location settings and shared header directive regressions."""

from importlib import import_module
import json
from pathlib import Path
import re
from types import SimpleNamespace

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src/common/core"


def render(plugin="grpc", files=(), **settings):
    defaults = {}
    for name in ("grpc", "reverseproxy"):
        defaults.update({key: value["default"] for key, value in json.loads((CORE / name / "plugin.json").read_text())["settings"].items()})
    defaults.update(
        USE_GRPC="yes",
        USE_REVERSE_PROXY="yes",
        SERVER_NAME="example.com alias.example.com",
        GRPC_HOST="grpc://backend:50051",
        REVERSE_PROXY_HOST="http://backend:8080",
    )
    defaults.update(settings)
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    fake_pathlib = SimpleNamespace(
        Path=lambda path: SimpleNamespace(is_file=lambda: path in {f"/var/cache/bunkerweb/reverseproxy/example.com/{name}" for name in files})
    )
    environment.globals["import"] = lambda name: fake_pathlib if name == "pathlib" else import_module(name)
    filename = {"grpc": "grpc", "reverseproxy": "reverse-proxy", "misc": "underscores-in-headers"}[plugin]
    return environment.from_string((CORE / plugin / f"confs/server-http/{filename}.conf").read_text()).render(all=defaults, **defaults)


@pytest.mark.parametrize(
    "verify,files,emitted",
    [
        ("no", ("grpc-trusted-ca.pem", "grpc-crl.pem"), False),
        ("yes", ("grpc-trusted-ca.pem",), False),
        ("yes", ("grpc-crl.pem",), False),
        ("yes", ("grpc-trusted-ca.pem", "grpc-crl.pem"), True),
    ],
)
def test_crl_requires_verification_and_cached_ca(verify, files, emitted):
    output = render(files=files, GRPC_SSL_VERIFY=verify, GRPC_SSL_VERIFY_DEPTH="3")
    assert ("grpc_ssl_crl /var/cache/bunkerweb/reverseproxy/example.com/grpc-crl.pem;" in output) == emitted
    enabled = verify == "yes" and "grpc-trusted-ca.pem" in files
    assert ("grpc_ssl_verify on;" in output) == enabled
    assert ("grpc_ssl_verify_depth 3;" in output) == enabled
    assert ("grpc_ssl_trusted_certificate /var/cache/bunkerweb/reverseproxy/example.com/grpc-trusted-ca.pem;" in output) == enabled
    if verify == "yes" and not enabled:
        assert "grpc_ssl_verify off;" in output


@pytest.mark.parametrize("suffix,value", [("PROTOCOLS", "TLSv1.2 TLSv1.3"), ("CIPHERS", "HIGH:!MD5")])
def test_protocols_and_ciphers(suffix, value):
    directive = f"grpc_ssl_{suffix.lower()}"
    assert directive not in render()
    assert f"{directive} {value};" in render(**{f"GRPC_SSL_{suffix}": value})


@pytest.mark.parametrize(
    "files,enabled",
    [
        ((), False),
        (("grpc-client.pem",), False),
        (("grpc-client.key",), False),
        (("client-cert.pem", "client-key.pem"), False),
        (("grpc-client.pem", "grpc-client.key"), True),
    ],
)
def test_own_client_pair(files, enabled):
    output = render(files=files)
    assert ("grpc_ssl_certificate /var/cache/bunkerweb/reverseproxy/example.com/grpc-client.pem;" in output) == enabled
    assert ("grpc_ssl_certificate_key /var/cache/bunkerweb/reverseproxy/example.com/grpc-client.key;" in output) == enabled
    assert "/client-cert.pem" not in output


@pytest.mark.parametrize(
    "suffix,value,directives",
    [
        ("HEADERS_CLIENT", "X-Result ready;X-Other yes always", ["add_header X-Result ready;", "add_header X-Other yes always;"]),
        ("PASS_HEADERS", "Server Date", ["grpc_pass_header Server;", "grpc_pass_header Date;"]),
        ("IGNORE_HEADERS", "Expires Cache-Control", ["grpc_ignore_headers Expires Cache-Control;"]),
        ("BUFFER_SIZE", "32k", ["grpc_buffer_size 32k;"]),
        ("MAX_CLIENT_SIZE", "10m", ["client_max_body_size 10m;"]),
        ("AUTH_REQUEST", "/auth", ["auth_request /auth;"]),
        ("AUTH_REQUEST_SIGNIN_URL", "https://login.example.com/#token", ["error_page 401 =302 https://login.example.com/#token;"]),
        (
            "AUTH_REQUEST_SET",
            "$user $upstream_http_user;$role $upstream_http_role",
            ["auth_request_set $user $upstream_http_user;", "auth_request_set $role $upstream_http_role;"],
        ),
    ],
)
def test_location_options_do_not_leak(suffix, value, directives):
    output = render(GRPC_HOST_2="grpc://other:50051", GRPC_URL_2="/second", **{f"GRPC_{suffix}_2": value})
    first, second = output.split('location "/second"')
    for directive in directives:
        assert directive not in first
        assert directive in second


@pytest.mark.parametrize("grpc,rp", [("no", "no"), ("yes", "no"), ("no", "yes"), ("yes", "yes")])
def test_underscores_single_owner(grpc, rp, render_tree):
    settings = dict(GRPC_UNDERSCORES_IN_HEADERS=grpc, REVERSE_PROXY_UNDERSCORES_IN_HEADERS=rp)
    assert "underscores_in_headers" not in render("grpc", **settings)
    assert "underscores_in_headers" not in render("reverseproxy", **settings)
    misc = render("misc", **settings)
    assert misc.count("underscores_in_headers on;") == int("yes" in (grpc, rp))
    assert "underscores_in_headers off;" not in misc
    tree = render_tree(
        SERVER_NAME="example.com",
        USE_GRPC="yes",
        USE_REVERSE_PROXY="yes",
        GRPC_HOST="grpc://backend:50051",
        GRPC_URL="/grpc",
        REVERSE_PROXY_HOST="http://backend:8080",
        **settings,
    )
    emitted = [name for name, content in tree.items() if "underscores_in_headers on;" in content]
    assert emitted == (["server-http/underscores-in-headers.conf"] if "yes" in (grpc, rp) else [])


def test_schema_new_settings_and_owned_identity():
    manifest = json.loads((CORE / "grpc/plugin.json").read_text())
    settings = manifest["settings"]
    assert "jobs" not in manifest
    for suffix in (
        "HEADERS_CLIENT",
        "PASS_HEADERS",
        "IGNORE_HEADERS",
        "BUFFER_SIZE",
        "MAX_CLIENT_SIZE",
        "AUTH_REQUEST",
        "AUTH_REQUEST_SIGNIN_URL",
        "AUTH_REQUEST_SET",
    ):
        assert settings[f"GRPC_{suffix}"]["multiple"] == "grpc"
        assert settings[f"GRPC_{suffix}"]["default"] == ""
    rp = json.loads((CORE / "reverseproxy/plugin.json").read_text())["settings"]
    for key in rp:
        if "SSL_CLIENT_" in key:
            other = settings[key.replace("REVERSE_PROXY", "GRPC")]
            for field in ("context", "default", "regex", "type"):
                assert other[field] == rp[key][field]
    for suffix, value in (("AUTH_REQUEST", "/auth#token"), ("AUTH_REQUEST_SIGNIN_URL", "https://login.example.com/#token")):
        assert re.fullmatch(settings[f"GRPC_{suffix}"]["regex"], value)
    assert all(len(value["help"]) <= 512 for value in settings.values())


@pytest.mark.parametrize(
    "suffix,valid,invalid",
    [
        ("HOST", "grpcs://backend:443", "grpcs://backend name"),
        ("CUSTOM_HOST", "backend.example.com", "backend name"),
        ("HEADERS", "X-Example value", "X-Example #value"),
        ("HIDE_HEADERS", "Server Date", "Server: Date"),
        ("SSL_SNI_NAME", "backend.example.com", "backend name"),
        ("NEXT_UPSTREAM", "error timeout", "unrecognized"),
        ("INCLUDES", "/etc/nginx/extra.conf", '"/etc/nginx/extra.conf"'),
    ],
)
def test_tightened_validation(suffix, valid, invalid):
    settings = json.loads((CORE / "grpc/plugin.json").read_text())["settings"]
    pattern = settings[f"GRPC_{suffix}"]["regex"]
    assert re.fullmatch(pattern, valid)
    assert not re.fullmatch(pattern, invalid)


def test_tls_directives_each_have_their_own_line():
    output = render(
        files=("grpc-trusted-ca.pem", "grpc-crl.pem", "grpc-client.pem", "grpc-client.key"),
        GRPC_SSL_VERIFY="yes",
        GRPC_SSL_PROTOCOLS="TLSv1.3",
        GRPC_SSL_CIPHERS="HIGH",
    )
    assert ";proxy_" not in output and ";grpc_" not in output
    lines = [line for line in output.splitlines() if line.startswith("grpc_ssl_")]
    assert len(lines) == 9
    assert all(line.count(";") == 1 and line.endswith(";") for line in lines)


def test_default_render_unchanged():
    assert render() == BASELINE_RENDER


BASELINE_RENDER = 'grpc_ssl_server_name off;\n\ngrpc_intercept_errors on;\n\nlocation "/" {\n\tset $grpc_backend0 "grpc://backend:50051";\n\tgrpc_pass $grpc_backend0;\n\tgrpc_set_header Host $host;\n\tgrpc_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\tgrpc_set_header X-Real-IP $remote_addr;\n\tgrpc_set_header X-Forwarded-Proto $scheme;\n\tgrpc_set_header X-Forwarded-Host $http_host;\n\tgrpc_set_header TE trailers;\n\tgrpc_set_header X-Forwarded-Prefix "/";\n\tgrpc_connect_timeout 60s;\n\tgrpc_read_timeout 60s;\n\tgrpc_send_timeout 60s;\n\tgrpc_socket_keepalive off;\n}\n\n'
