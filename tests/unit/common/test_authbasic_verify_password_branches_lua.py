"""UB1-2: legacy passwords must match; corrupt and unsupported stored credentials must fail closed.

Run the real request path with the shared deterministic KDF stand-in. The local decoder
adds OpenResty's invalid-base64 result, which the shared permissive decoder cannot produce.
"""

import pytest
import _lua_request_helpers as lua

pytestmark = lua.requires_lua


@pytest.fixture
def rejecting_decoder(monkeypatch):
    stub = r"""
local decode = ngx.decode_base64
ngx.decode_base64 = function(value)
    if value:find("[^A-Za-z0-9+/=]") then return nil end
    return decode(value)
end
"""
    anchor = 'PLUGIN = dofile("__MODULE__")'
    assert lua.HARNESS.count(anchor) == 1
    monkeypatch.setattr(lua, "HARNESS", lua.HARNESS.replace(anchor, stub + anchor))


def request(stored, candidate="secret"):
    return lua.run(
        "authbasic",
        f"""
VARIABLES = {{ USE_AUTH_BASIC = "yes" }}
STORE["plugin_authbasic_configs"] = {{ global = {{
    realm = "Private", matcher = {{ kind = "sitewide" }}, credentials = {{ alice = {stored} }}
}} }}
HEADERS = {{ authorization = "Basic " .. ngx.encode_base64("alice:{candidate}") }}
local result = PLUGIN:new(ctx()):access()
emit("ret", result.ret) emit("status", result.status) emit("msg", result.msg)
emit("challenge", ngx.header["WWW-Authenticate"]) emit("metrics", metric_keys())
emit("log", LOGS[1])
""",
    )


@pytest.mark.parametrize("candidate", ["secret", "wrong", "secreX", ""])
def test_legacy_plaintext_accepts_only_the_matching_password(candidate):
    out = request('"secret"', candidate)
    assert out["ret"] == "true"
    if candidate == "secret":
        assert out["status"] == "nil"
        assert out["msg"] == "authenticated user alice"
        assert out["challenge"] == "nil"
        assert out["metrics"] == "counters:passed_authbasic,counters:passed_user_alice,tables:authentications"
    else:
        assert out["status"] == "401"
        assert out["msg"] == "invalid password for user alice"
        assert out["challenge"] == 'Basic realm="Private", charset="UTF-8"'
        assert out["metrics"] == "counters:failed_authbasic,tables:authentications"


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param('{ salt = "!invalid!", hash = ngx.encode_base64("D:secret:salt") }', id="corrupt-salt"),
        pytest.param('{ salt = ngx.encode_base64("salt"), hash = "!invalid!" }', id="corrupt-hash"),
        pytest.param('{ salt = "!invalid!", hash = "!invalid!" }', id="both-corrupt"),
    ],
)
def test_corrupt_hash_or_salt_is_an_internal_error_and_challenges(rejecting_decoder, stored):
    out = request(stored)
    assert_internal_error(out, "corrupted credential data")


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("42", id="number"),
        pytest.param("true", id="boolean"),
        pytest.param("{}", id="empty-table"),
        pytest.param('{ hash = ngx.encode_base64("D:secret:salt") }', id="missing-salt"),
        pytest.param('{ salt = ngx.encode_base64("salt") }', id="missing-hash"),
    ],
)
def test_unsupported_credential_format_is_an_internal_error_and_challenges(stored):
    out = request(stored)
    assert_internal_error(out, "unsupported credential format")


def assert_internal_error(out, reason):
    assert out["ret"] == "true"
    assert out["status"] == "401"
    assert out["msg"] == "internal authentication error"
    assert out["challenge"] == 'Basic realm="Private", charset="UTF-8"'
    assert out["metrics"] == "counters:failed_authbasic,tables:authentications"
    assert out["log"] == f"ERR: unable to verify password for user alice: {reason}"
