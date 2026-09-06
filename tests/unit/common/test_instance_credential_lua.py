"""An enrolled instance answers to its own credential and refuses the shared API_TOKEN.

Two behaviours are pinned here because both fail open and neither is visible from the outside:

* ``is_allowed_token()`` -- once a credential file exists, the global ``API_TOKEN`` must stop
  being a key to this instance. That is the whole security gain of enrollment (PO ruling
  2026-09-02); an ``or`` written the other way round would leave the shared token working
  everywhere and every functional test would still pass.
* ``write_instance_credential()`` -- the rotation's second phase. It must be atomic (a torn file
  leaves the instance unable to authenticate anything at all) and it must keep the fingerprint of
  the code the credential was first minted from, or the entrypoint re-redeems an already-consumed
  code on the next restart and logs a failure forever.

Runs the shipped ``src/bw/lua/bunkerweb/api.lua`` sources through the ``lua`` binary with
OpenResty stubbed, splicing the real function bodies in the way ``test_api_reload_verdict_lua.py``
does -- so narrowing the check in api.lua fails the extraction here rather than passing on a copy.
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
API_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = API_LUA.read_text(encoding="utf-8")


def real_local(name: str) -> str:
    body = re.search(rf"^local function {name}\(.*?^end$", SOURCE, re.M | re.S)
    assert body, f"{name}() is gone from {API_LUA}"
    return body.group(0)


def real_method(name: str) -> str:
    body = re.search(rf"^function api:{name}\(\).*?^end$", SOURCE, re.M | re.S)
    assert body, f"api:{name}() is gone from {API_LUA}"
    return body.group(0)


# A flat-string JSON pair is all the credential file ever holds; the point of these tests is the
# file handling and the token comparison, not cjson.
JSON_STUB = """
local function json_encode(t)
    local parts = {}
    for k, v in pairs(t) do parts[#parts + 1] = '"' .. k .. '":"' .. v .. '"' end
    return "{" .. table.concat(parts, ",") .. "}"
end
local function json_decode(s)
    local t = {}
    for k, v in s:gmatch('"([^"]+)"%s*:%s*"([^"]*)"') do t[k] = v end
    if next(t) == nil then error("no json") end
    return t
end
"""

HARNESS = """
-- write_instance_credential names its temp file after the worker and the clock so two concurrent
-- rotations cannot interleave into one file; both come from ngx.
ngx = { NOTICE = 1, ERR = 2, now = function() return 1234.5 end, worker = { pid = function() return 4242 end } }
ENOENT = 2
local HEADERS = %s
ngx_req = { get_headers = function() return HEADERS end }
logger = { log = function() end }
INSTANCE_CREDENTIAL_PATH = %s
API_TOKEN_VALUE = %s

get_variable = function() return "100" end
open = io.open
remove = os.remove
rename = os.rename
execute = function() return true end

%s
decode = json_decode
encode = json_encode

-- constant-time compare, as shipped
%s

local api = {}

%s

%s

%s

%s
"""

SECURE_COMPARE = """
local function secure_compare(a, b)
    if #a ~= #b then return false end
    local diff = 0
    for i = 1, #a do
        if a:byte(i) ~= b:byte(i) then diff = 1 end
    end
    return diff == 0
end
"""


def _lua_string(value):
    return "nil" if value is None else "[==[" + value + "]==]"


def run(body: str, *, path: Path, headers: dict | None = None, api_token: str | None = None):
    headers_lua = "{" + ", ".join(f'["{k}"] = [==[{v}]==]' for k, v in (headers or {}).items()) + "}"
    script = HARNESS % (
        headers_lua,
        _lua_string(str(path)),
        _lua_string(api_token),
        JSON_STUB,
        SECURE_COMPARE,
        real_local("read_instance_credential"),
        real_local("write_instance_credential"),
        real_method("is_allowed_token"),
        body,
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


ALLOW = """
local self = { api_token = API_TOKEN_VALUE, instance_credential = read_instance_credential() }
local ok, msg = api.is_allowed_token(self)
print(tostring(ok) .. "|" .. msg)
"""


def _write(tmp_path, credential, fingerprint="fp-of-the-code"):
    path = tmp_path / "instance-credential.json"
    payload = {"credential": credential}
    if fingerprint is not None:
        payload["code_fingerprint"] = fingerprint
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


UNREADABLE = """
local credential, state = read_instance_credential()
local self = { api_token = API_TOKEN_VALUE, instance_credential = credential, instance_credential_state = state }
local ok, msg = api.is_allowed_token(self)
print(tostring(ok) .. "|" .. msg)
"""


class TestExclusiveCredential:
    def test_enrolled_instance_accepts_its_own_credential(self, tmp_path):
        path = _write(tmp_path, "mine")
        out = run(ALLOW, path=path, headers={"authorization": "Bearer mine"}, api_token="the-global-token")
        assert out == "true|ok"

    def test_enrolled_instance_refuses_the_global_token(self, tmp_path):
        """The regression this whole file exists for."""
        path = _write(tmp_path, "mine")
        out = run(ALLOW, path=path, headers={"authorization": "Bearer the-global-token"}, api_token="the-global-token")
        assert out == "false|invalid API token"

    def test_enrolled_instance_refuses_a_missing_header(self, tmp_path):
        path = _write(tmp_path, "mine")
        out = run(ALLOW, path=path, headers={}, api_token="the-global-token")
        assert out == "false|missing API token"

    def test_unenrolled_instance_keeps_the_global_token(self, tmp_path):
        out = run(ALLOW, path=tmp_path / "absent.json", headers={"authorization": "Bearer the-global-token"}, api_token="the-global-token")
        assert out == "true|ok"

    def test_no_token_at_all_still_allows(self, tmp_path):
        out = run(ALLOW, path=tmp_path / "absent.json", headers={}, api_token=None)
        assert out == "true|ok"

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads a 0000 file regardless of its mode")
    def test_a_credential_file_it_cannot_READ_also_fails_closed(self, tmp_path):
        """`io.open` answers nil for EVERY failure, not just "no such file".

        A valid credential the worker cannot open — a volume restored root-owned, an SELinux
        relabel, a Linux arm where run_as_nginx did not take — must NOT be read as "never
        enrolled": that is precisely the fail-open that hands the shared API_TOKEN back to the one
        instance enrollment took it away from. Only ENOENT may mean absent.
        """
        path = _write(tmp_path, "mine")
        path.chmod(0o000)
        try:
            out = run(UNREADABLE, path=path, headers={"authorization": "Bearer the-global-token"}, api_token="the-global-token")
        finally:
            path.chmod(0o600)
        assert out == "false|instance credential unreadable"

    @pytest.mark.parametrize("content", ("not json at all", '{"credential": ""}', ""))
    def test_a_present_but_unusable_credential_file_fails_CLOSED(self, tmp_path, content):
        """The trap: treating "unreadable" like "never enrolled" hands the shared API_TOKEN back to
        the one instance that had it taken away — permissions change, a half-restored volume, a
        truncated write, and the instance silently re-opens to the global key."""
        path = tmp_path / "instance-credential.json"
        path.write_text(content, encoding="utf-8")
        out = run(UNREADABLE, path=path, headers={"authorization": "Bearer the-global-token"}, api_token="the-global-token")
        assert out == "false|instance credential unreadable"

    def test_an_absent_file_is_not_an_unreadable_one(self, tmp_path):
        """ "Never enrolled" must still take the historical path, or every unenrolled instance
        stops answering the moment this ships."""
        out = run(UNREADABLE, path=tmp_path / "absent.json", headers={"authorization": "Bearer the-global-token"}, api_token="the-global-token")
        assert out == "true|ok"


WRITE = """
local err = write_instance_credential("rotated")
print(tostring(err))
"""


class TestWriteCredential:
    def test_rotation_replaces_the_credential(self, tmp_path):
        path = _write(tmp_path, "old")
        assert run(WRITE, path=path) == "nil"
        assert json.loads(path.read_text(encoding="utf-8"))["credential"] == "rotated"

    def test_rotation_keeps_the_code_fingerprint(self, tmp_path):
        """Otherwise the entrypoint re-redeems an already-consumed code on the next restart."""
        path = _write(tmp_path, "old", fingerprint="the-original-fingerprint")
        run(WRITE, path=path)
        assert json.loads(path.read_text(encoding="utf-8"))["code_fingerprint"] == "the-original-fingerprint"

    def test_no_temp_file_is_left_behind(self, tmp_path):
        path = _write(tmp_path, "old")
        run(WRITE, path=path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["instance-credential.json"]

    def test_the_temp_name_is_per_writer(self):
        """A single fixed ".tmp" would let two concurrent rotations interleave their writes and
        rename a spliced file into place."""
        body = real_local("write_instance_credential")
        assert "ngx.worker.pid()" in body and "ngx.now()" in body

    def test_write_into_a_missing_directory_reports_an_error(self, tmp_path):
        path = tmp_path / "nope" / "instance-credential.json"
        assert run(WRITE, path=path).startswith("can't open")


class TestShippedWiring:
    def test_initialize_loads_the_credential_and_its_state(self):
        initialize = re.search(r"^function api:initialize\(ctx\).*?^end$", SOURCE, re.M | re.S)
        assert initialize, "api:initialize is gone from api.lua"
        body = initialize.group(0)
        assert "read_instance_credential()" in body
        # Without the second return value the "unreadable" branch can never fire.
        assert "instance_credential_state" in body

    def test_the_credential_route_exists_and_writes_atomically(self):
        handler = re.search(r'^api\.global\.POST\["\^/credential\$"\] = function\(self\).*?^end$', SOURCE, re.M | re.S)
        assert handler, "POST /credential is gone from api.lua"
        assert "write_instance_credential(" in handler.group(0)

    def test_the_write_helper_renames_rather_than_truncating_in_place(self):
        body = real_local("write_instance_credential")
        assert "rename(" in body, "the credential write must be a rename, not an in-place truncate"
