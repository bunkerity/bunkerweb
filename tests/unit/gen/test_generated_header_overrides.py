"""Custom upstream headers replace generated defaults, case-insensitively."""

import pytest

from test_grpc_upstream_tls import render


@pytest.mark.parametrize("plugin,prefix,directive", [("grpc", "GRPC", "grpc_set_header"), ("reverseproxy", "REVERSE_PROXY", "proxy_set_header")])
@pytest.mark.parametrize(
    "header",
    [
        "Host",
        "X-Forwarded-For",
        "X-Real-IP",
        "X-Forwarded-Proto",
        "X-Forwarded-Host",
        "X-Forwarded-Prefix",
        "X-SSL-Client-Verify",
        "X-SSL-Client-DN",
        "X-SSL-Issuer",
        "X-SSL-Client-Serial",
        "X-SSL-Client-Fingerprint",
        "X-SSL-Client-NotBefore",
        "X-SSL-Client-NotAfter",
    ],
)
def test_generated_header_is_replaced(plugin, prefix, directive, header):
    output = render(
        plugin,
        USE_MTLS="yes",
        MTLS_FORWARD_CLIENT_HEADERS="yes",
        **{
            f"{prefix}_HEADERS": f'{header.lower()} "custom";X-Extra value',
            f"{prefix}_HOST_2": "grpc://other:50051" if plugin == "grpc" else "http://other:8080",
            f"{prefix}_URL_2": "/second",
        },
    )
    first, second = output.split('location "/second"')
    lines = [line.strip() for line in first.splitlines() if line.strip().lower().startswith(f"{directive} {header.lower()} ")]
    assert lines == [f'{directive} {header.lower()} "custom";']
    assert f"{directive} X-Extra value;" in first
    assert f'{directive} {header.lower()} "custom";' not in second
    assert any(line.strip().lower().startswith(f"{directive} {header.lower()} ") for line in second.splitlines())


@pytest.mark.parametrize(
    "plugin,prefix,header",
    [
        ("grpc", "GRPC", "TE"),
        ("reverseproxy", "REVERSE_PROXY", "X-Forwarded-Protocol"),
        ("reverseproxy", "REVERSE_PROXY", "Upgrade"),
        ("reverseproxy", "REVERSE_PROXY", "Connection"),
    ],
)
@pytest.mark.parametrize("ws", ["yes", "no"])
def test_protocol_headers_can_be_overridden(plugin, prefix, header, ws):
    output = render(plugin, REVERSE_PROXY_WS=ws, **{f"{prefix}_HEADERS": f'{header.lower()} ""'})
    directive = "grpc_set_header" if plugin == "grpc" else "proxy_set_header"
    lines = [line.strip() for line in output.splitlines() if line.strip().lower().startswith(f"{directive} {header.lower()} ")]
    assert lines == [f'{directive} {header.lower()} "";']
