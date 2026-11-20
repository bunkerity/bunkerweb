"""The ACME challenge API must never turn an attacker-controlled token into a path outside the challenge folder.

``letsencrypt:api`` concatenated ``data.token`` into the challenge path without a charset check, so a token holding ``../``
or a slash let an unauthenticated caller write and delete files elsewhere. This test lifts the real ``api`` method from
``letsencrypt.lua`` and records every ``io.open`` and ``os.remove`` it makes.
Refs: GHSA-79fm-4xj6-pp5g.
"""

import json
import re

import pytest
from _t2_helpers import CORE, LUA, run_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

SOURCE = (CORE / "letsencrypt" / "letsencrypt.lua").read_text()
API = re.search(r"^function letsencrypt:api\(\).*?^end$", SOURCE, re.M | re.S)
FOLDER = "/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/"


def call(method, body):
    assert API, "letsencrypt:api not found in letsencrypt.lua"
    script = f"""
local match = string.match
local HTTP_OK, HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND = 200, 400, 500, 404
local OPENED, REMOVED, WRITTEN = {{}}, {{}}, {{}}
local function open(path, mode) OPENED[#OPENED + 1] = path return {{ write = function(_, v) WRITTEN[#WRITTEN + 1] = v end, close = function() end }} end
local function remove(path) REMOVED[#REMOVED + 1] = path return true end
local function execute() return true end
local BODY = {_lua(body)}
local function decode(raw) if raw == "NOT JSON" then error("bad json") end return BODY end
local ngx = {{ req = {{ read_body = function() end, get_body_data = function() return BODY == "NOT JSON" and "NOT JSON" or "{{}}" end }} }}
local letsencrypt = {{}}
function letsencrypt:ret(ok, msg, status) return {{ ok = ok, msg = msg, status = status }} end
{API.group(0) if API else ""}
local self = setmetatable({{ ctx = {{ bw = {{ uri = "/lets-encrypt/challenge", request_method = {json.dumps(method)} }} }} }}, {{ __index = letsencrypt }})
local r = letsencrypt.api(self)
emit({{ msg = r.msg, status = r.status, opened = OPENED, removed = REMOVED, written = WRITTEN }})
"""
    return run_script(script)


def _lua(value):
    if isinstance(value, dict):
        return "{" + ",".join(f"[{json.dumps(k)}]={_lua(v)}" for k, v in value.items()) + "}"
    if isinstance(value, str):
        return '"' + "".join(c if c.isalnum() else f"\\{ord(c):03d}" for c in value) + '"'
    return json.dumps(value)


BAD_TOKENS = ["../../etc/cron.d/x", "a/b", "..", "tok\\en", "tok\x00en", "", ".hidden", "ok/../../x", "/abs"]


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("token", BAD_TOKENS)
def test_a_token_outside_the_base64url_alphabet_is_rejected_without_touching_the_filesystem(method, token):
    out = call(method, {"token": token, "validation": "v"})
    assert out["status"] == 400
    assert out["msg"] == "invalid challenge token"
    assert out["opened"] == [] and out["removed"] == [] and out["written"] == []


@pytest.mark.parametrize("body", [{"validation": "v"}, {"token": 7, "validation": "v"}, "NOT JSON"])
@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_a_missing_or_non_string_token_never_reaches_the_filesystem(method, body):
    out = call(method, body)
    assert out["status"] == 400
    assert out["opened"] == [] and out["removed"] == []


def test_a_base64url_token_is_written_inside_the_challenge_folder():
    out = call("POST", {"token": "Abc-123_xyz", "validation": "proof"})
    assert (out["status"], out["msg"]) == (200, "validation token written")
    assert out["opened"] == [FOLDER + "Abc-123_xyz"]
    assert out["written"] == ["proof"]


def test_a_base64url_token_is_removed_from_inside_the_challenge_folder():
    out = call("DELETE", {"token": "Abc-123_xyz"})
    assert (out["status"], out["msg"]) == (200, "validation token removed")
    assert out["removed"] == [FOLDER + "Abc-123_xyz"]
