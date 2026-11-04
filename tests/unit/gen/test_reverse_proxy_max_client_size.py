"""`REVERSE_PROXY_MAX_CLIENT_SIZE` caps the body for one location, and the ModSecurity limit with it.

Port of dev 2bbdda9b4. Two things the template must get right, both regression-worthy:

* Empty (the default) renders neither directive -- the service-wide `MAX_CLIENT_SIZE` and
  `MODSECURITY_SEC_REQUEST_BODY_LIMIT` keep applying, unchanged.
* A value converts `k`/`m`/`g` suffixes to the byte count `SecRequestBodyLimit` needs (it takes no
  suffix), and only emits `modsecurity_rules` when ModSecurity is actually enabled for this
  location -- `REVERSE_PROXY_MODSECURITY=no` (which emits `modsecurity off;`) must not also emit a
  now-meaningless SecRequestBodyLimit override.
"""

from importlib import import_module
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "src" / "common" / "core" / "reverseproxy" / "confs" / "server-http" / "reverse-proxy.conf"


def _render(max_client_size: str = "", use_modsecurity: str = "no", location_modsecurity: str = "yes") -> str:
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, keep_trailing_newline=True)
    environment.globals["import"] = import_module  # Templator exposes this; the mTLS block uses it
    config = {"REVERSE_PROXY_HOST": "http://backend:8080"}
    if max_client_size:
        config["REVERSE_PROXY_MAX_CLIENT_SIZE"] = max_client_size
    if location_modsecurity != "yes":
        config["REVERSE_PROXY_MODSECURITY"] = location_modsecurity
    return environment.from_string(TEMPLATE.read_text(encoding="utf-8")).render(
        USE_REVERSE_PROXY="yes",
        SERVER_NAME="www.example.com",
        REVERSE_PROXY_CUSTOM_HOST="",
        USE_MODSECURITY=use_modsecurity,
        USE_MTLS="no",
        USE_PROXY_CACHE="no",
        USE_UI="no",
        all=config,
    )


def test_empty_renders_neither_directive():
    out = _render(max_client_size="", use_modsecurity="yes")
    assert "client_max_body_size" not in out
    assert "SecRequestBodyLimit" not in out


@pytest.mark.parametrize(
    "value,expected_bytes",
    [
        ("10m", 10 * 1024 * 1024),
        ("10M", 10 * 1024 * 1024),
        ("512k", 512 * 1024),
        ("1g", 1024 * 1024 * 1024),
        ("2048", 2048),
        ("0", 0),
    ],
)
def test_value_sets_body_size_and_converts_modsecurity_limit_to_bytes(value, expected_bytes):
    out = _render(max_client_size=value, use_modsecurity="yes")
    assert f"client_max_body_size {value};" in out
    assert f"modsecurity_rules 'SecRequestBodyLimit {expected_bytes}';" in out


def test_modsecurity_disabled_globally_still_sets_body_size_but_no_modsecurity_rule():
    out = _render(max_client_size="10m", use_modsecurity="no")
    assert "client_max_body_size 10m;" in out
    assert "SecRequestBodyLimit" not in out


def test_modsecurity_off_for_this_location_still_sets_body_size_but_no_modsecurity_rule():
    """REVERSE_PROXY_MODSECURITY=no already emits `modsecurity off;` for this location -- a
    SecRequestBodyLimit override here would be dead configuration for a disabled module."""
    out = _render(max_client_size="10m", use_modsecurity="yes", location_modsecurity="no")
    assert "modsecurity off;" in out
    assert "client_max_body_size 10m;" in out
    assert "SecRequestBodyLimit" not in out
