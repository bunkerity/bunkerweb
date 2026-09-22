"""Upstream TLS settings render independently of the optional client identity."""

from importlib import import_module
import json
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/reverseproxy"


def render(context, files=(), **settings):
    defaults = {key: value["default"] for key, value in json.loads((PLUGIN / "plugin.json").read_text())["settings"].items()}
    defaults.update(REVERSE_PROXY_SSL_PROTOCOLS="", REVERSE_PROXY_SSL_CIPHERS="", REVERSE_PROXY_SSL_CRL="", REVERSE_PROXY_SSL_CRL_DATA="")
    defaults.update(USE_REVERSE_PROXY="yes", SERVER_NAME="example.com alias.example.com", REVERSE_PROXY_HOST="http://backend:8080")
    defaults.update(settings)
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    fake_pathlib = SimpleNamespace(Path=lambda path: SimpleNamespace(is_file=lambda: Path(path).name in files))
    environment.globals["import"] = lambda name: fake_pathlib if name == "pathlib" else import_module(name)
    return environment.from_string((PLUGIN / f"confs/server-{context}/reverse-proxy.conf").read_text()).render(all=defaults, **defaults)


@pytest.mark.parametrize("context", ["http", "stream"])
@pytest.mark.parametrize(
    "verify,files,emitted",
    [
        ("no", ("trusted-ca.pem", "crl.pem"), False),
        ("yes", ("trusted-ca.pem",), False),
        ("yes", ("crl.pem",), False),
        ("yes", ("trusted-ca.pem", "crl.pem"), True),
    ],
)
def test_crl_requires_verification_and_cached_ca(context, verify, files, emitted):
    output = render(context, files, REVERSE_PROXY_SSL_VERIFY=verify)
    assert ("proxy_ssl_crl /var/cache/bunkerweb/reverseproxy/example.com/crl.pem;" in output) == emitted


@pytest.mark.parametrize("context", ["http", "stream"])
@pytest.mark.parametrize("suffix,value", [("PROTOCOLS", "TLSv1.2 TLSv1.3"), ("CIPHERS", "HIGH:!MD5")])
def test_protocols_and_ciphers(context, suffix, value):
    directive = f"proxy_ssl_{suffix.lower()}"
    assert directive not in render(context)
    assert f"{directive} {value};" in render(context, **{f"REVERSE_PROXY_SSL_{suffix}": value})


def test_stream_client_pair_still_enables_tls():
    output = render("stream", ("client-cert.pem", "client-key.pem"))
    assert "proxy_ssl on;" in output
    assert "proxy_ssl_certificate_key /var/cache/bunkerweb/reverseproxy/example.com/client-key.pem;" in output


def test_stream_verification_without_client_pair_enables_tls():
    output = render("stream", ("trusted-ca.pem",), REVERSE_PROXY_SSL_VERIFY="yes")
    assert "proxy_ssl on;" in output
    assert "proxy_ssl_verify on;" in output
    assert "proxy_ssl_certificate_key" not in output


@pytest.mark.parametrize("setting,value", [("PROTOCOLS", "TLSv1.3"), ("CIPHERS", "HIGH")])
def test_stream_other_tls_settings_enable_tls(setting, value):
    assert "proxy_ssl on;" in render("stream", **{f"REVERSE_PROXY_SSL_{setting}": value})


def test_stream_default_and_incomplete_pair_do_not_enable_tls():
    for files in ((), ("client-cert.pem",), ("client-key.pem",)):
        assert "proxy_ssl on;" not in render("stream", files)


@pytest.mark.parametrize("context", ["http", "stream"])
def test_tls_directives_each_have_their_own_line(context):
    output = render(
        context,
        ("trusted-ca.pem", "crl.pem", "client-cert.pem", "client-key.pem"),
        REVERSE_PROXY_SSL_VERIFY="yes",
        REVERSE_PROXY_SSL_PROTOCOLS="TLSv1.3",
        REVERSE_PROXY_SSL_CIPHERS="HIGH",
    )
    assert ";proxy_" not in output and ";grpc_" not in output
    lines = [line for line in output.splitlines() if line.startswith("proxy_ssl_")]
    assert len(lines) == 9
    assert all(line.count(";") == 1 and line.endswith(";") for line in lines)


@pytest.mark.parametrize("setting,value", [("CRL", "/tmp/crl.pem"), ("CRL_DATA", "PEM data")])
def test_stream_crl_without_verification_does_not_enable_tls(setting, value):
    output = render("stream", **{f"REVERSE_PROXY_SSL_{setting}": value})
    assert "proxy_ssl on;" not in output
    assert "proxy_ssl_crl " not in output
