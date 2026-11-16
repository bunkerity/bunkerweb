"""BunkerWeb's nonce-CSP error pages must not inherit the site's HTML injection."""

from hashlib import sha256
import json
from pathlib import Path
import re

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src/common/core"
CODES = json.loads((CORE / "errors/plugin.json").read_text())["settings"]["INTERCEPTED_ERROR_CODES"]["default"]


def _render(plugin, **variables):
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    template = (CORE / plugin / "confs/server-http" / f"{plugin}.conf").read_text()
    return environment.from_string(template).render(
        ERRORS=variables.pop("ERRORS", ""), INTERCEPTED_ERROR_CODES=CODES, ROOT_FOLDER="", MULTISITE="yes", SERVER_NAME="www.example.com", **variables
    )


@pytest.mark.parametrize("head,body", [("<style>head</style>", ""), ("", "<script>body</script>"), ("head", "body")])
def test_every_bunkerweb_error_location_overrides_injection(head, body):
    rendered = _render("errors", INJECT_HEAD=head, INJECT_BODY=body)
    for code in CODES.split():
        selector = "= /bwerror400" if code == "400" else f"@bwerror{code}"
        location = re.search(r"location\s+" + re.escape(selector) + r" \{(.*?)\n\}", rendered, re.S)
        assert location is not None, selector
        assert "\n\tsub_filter '</head>' '</head>';\n\tcontent_by_lua_block {" in location[1], selector
        assert "<style>head</style>" not in location[1] and "<script>body</script>" not in location[1]


@pytest.mark.parametrize(
    "errors,digest",
    [
        ("", "580cea977d3cb8b9bbbc941b63a90d8706576336aa68ce57b01fef9dd23db1cc"),
        ("400=/errors/400.html 403=/errors/403.html", "fc14f0fdded62aa919fc2168e6b447b14c2726260cbf08a35a692c7ba795defe"),
    ],
)
def test_no_injection_keeps_base_render_byte_identical(errors, digest):
    # Digests from 56a6b089e with Templator's lstrip_blocks/trim_blocks/keep_trailing_newline.
    rendered = _render("errors", ERRORS=errors, INJECT_HEAD="", INJECT_BODY="")
    assert sha256(rendered.encode()).hexdigest() == digest


@pytest.mark.parametrize("head,body", [("head", ""), ("", "body"), ("head", "body")])
def test_site_owned_error_pages_keep_server_injection(head, body):
    rendered = _render("errors", ERRORS="400=/errors/400.html 403=/errors/403.html", INJECT_HEAD=head, INJECT_BODY=body)
    for selector in ("@bwcustomerror403", "= /errors/400.html", "= /errors/403.html"):
        location = re.search(r"location\s+" + re.escape(selector) + r" \{(.*?)\n\}", rendered, re.S)
        assert location is not None, selector
        assert "sub_filter" not in location[1], selector
    assert "bwerror400" not in rendered and "@bwerror403" not in rendered
    server = _render("inject", INJECT_HEAD=head, INJECT_BODY=body)
    assert ("sub_filter '</head>' 'head</head>';" in server) is bool(head)
    assert ("sub_filter '</body>' 'body</body>';" in server) is bool(body)
