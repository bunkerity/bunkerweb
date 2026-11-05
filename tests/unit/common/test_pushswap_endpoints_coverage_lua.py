"""Real pushswap filesystem operations and Redis endpoint parsing at failure boundaries."""

import hashlib

import pytest
from _lua_core_helpers import BW_MODULES, LUA, run_core, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PUSH_PREAMBLE = r"""
package.loaded["resty.sha256"] = { new = function()
    local parts = {}
    return {update=function(_, chunk) parts[#parts+1]=chunk end,
            final=function() return SHA256(table.concat(parts)) end}
end }
package.loaded["resty.string"] = {to_hex=function(value)
    return (value:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
end}
local real_open, real_execute, real_rename, real_popen = io.open, os.execute, os.rename, io.popen
io.open = function(path, mode)
    if path == OPEN_FAIL and (not OPEN_MODE or mode == OPEN_MODE) then return nil, "open denied" end
    return real_open(path, mode)
end
io.popen = function(command)
    if LIST_FAIL then return nil end
    return real_popen(command)
end
os.execute = function(command)
    if EXEC_FAIL and command:find(EXEC_FAIL, 1, true) then return false end
    local ok = real_execute(command)
    if NUMERIC_EXEC then return ok and 0 or 1 end
    return ok
end
os.rename = function(from, to)
    if RENAME_FAIL and from:find(RENAME_FAIL, 1, true) then return nil, "EXDEV" end
    return real_rename(from, to)
end
local push = dofile(MODULE)
push.STATE_ROOT = ROOT .. "/state"
"""


def run_push(tmp_path, body, setup=""):
    return run_core(BW_MODULES / "pushswap.lua", setup + PUSH_PREAMBLE + body, ROOT=str(tmp_path))


@pytest.mark.parametrize("data", [b"", b"hello", b"x" * 131073], ids=["empty", "small", "multi-chunk"])
def test_digest_streams_complete_file(tmp_path, data):
    (tmp_path / "archive").write_bytes(data)
    out = run_push(tmp_path, 'emit({digest=push.digest_file(ROOT .. "/archive")})')
    assert out["digest"] == hashlib.sha256(data).hexdigest()


def test_missing_digest_file_has_diagnostic(tmp_path):
    out = run_push(tmp_path, 'local digest, err=push.digest_file(ROOT .. "/missing"); emit({digest=digest, err=err})')
    assert "digest" not in out
    assert out["err"] == f"cannot open {tmp_path}/missing"


@pytest.mark.parametrize("numeric", [False, True])
def test_applied_digest_roundtrip_uses_destination_specific_state(tmp_path, numeric):
    out = run_push(
        tmp_path,
        """
assert(push.write_applied("/etc/nginx", "abc123"))
local saved = push.read_applied("/etc/nginx")
local other = push.read_applied("/etc/bunkerweb")
local file=assert(io.open(push.applied_path("/etc/nginx"), "w")); file:close()
local empty = push.read_applied("/etc/nginx")
emit({saved=saved, other=other, empty=empty, path=push.applied_path("/etc/nginx")})
""",
        f"NUMERIC_EXEC={to_lua(numeric)}\n",
    )
    assert out == {"saved": "abc123", "path": f"{tmp_path}/state/_etc_nginx.applied"}


@pytest.mark.parametrize("failure", ["mkdir", "open"])
def test_applied_digest_write_failure_reports_error(tmp_path, failure):
    setup = 'EXEC_FAIL="mkdir -p"\n' if failure == "mkdir" else f'OPEN_FAIL={to_lua(str(tmp_path / "state/_etc_nginx.applied"))}\n'
    out = run_push(tmp_path, 'local ok, err=push.write_applied("/etc/nginx", "hash"); emit({ok=ok, err=err})', setup)
    assert out["ok"] is False
    assert ("cannot create" if failure == "mkdir" else "open denied") in out["err"]
    assert not (tmp_path / "state/_etc_nginx.applied").exists()


def setup_tree(tmp_path):
    destination = tmp_path / "destination"
    staging = destination / ".bw-staging"
    staging.mkdir(parents=True)
    (destination / "active").write_text("old")
    (destination / "stale").write_text("stale")
    (destination / ".bw-kept").write_text("reserved")
    (staging / "active").write_text("new")
    (staging / ".bw-injected").write_text("reserved incoming")
    return destination, staging


@pytest.mark.parametrize("fallback", [False, True])
def test_swap_replaces_old_tree_and_discards_reserved_archive_entries(tmp_path, fallback):
    destination, staging = setup_tree(tmp_path)
    out = run_push(
        tmp_path,
        """
local destination=ROOT .. "/destination"
assert(push.write_applied(destination, "old-digest"))
local ok, err=push.swap(destination, destination .. "/.bw-staging")
emit({ok=ok, err=err, applied=push.read_applied(destination)})
""",
        'RENAME_FAIL="/active"\n' if fallback else "",
    )
    assert out == {"ok": True}
    assert (destination / "active").read_text() == "new"
    assert (destination / ".bw-kept").read_text() == "reserved"
    assert not (destination / "stale").exists()
    assert not (destination / ".bw-injected").exists()
    assert not staging.exists()


@pytest.mark.parametrize("failure", ["cp -a", "rm -rf"])
def test_failed_copy_fallback_reports_park_failure_and_keeps_old_file(tmp_path, failure):
    destination, _ = setup_tree(tmp_path)
    command = failure if failure == "cp -a" else f"rm -rf '{destination}/active'"
    out = run_push(
        tmp_path,
        'local ok, err=push.swap(ROOT .. "/destination", ROOT .. "/destination/.bw-staging"); emit({ok=ok, err=err})',
        f'RENAME_FAIL="/active"; EXEC_FAIL={to_lua(command)}\n',
    )
    assert out["ok"] is False
    assert "cannot park active" in out["err"]
    assert (destination / "active").read_text() == "old"


def test_sentinel_open_error_refuses_swap_before_touching_tree(tmp_path):
    destination, staging = setup_tree(tmp_path)
    out = run_push(
        tmp_path,
        'push.SENTINEL_DESTINATION=ROOT .. "/destination"; local ok, err=push.swap(push.SENTINEL_DESTINATION, ROOT .. "/destination/.bw-staging"); emit({ok=ok, err=err})',
        f'OPEN_FAIL={to_lua(str(destination / ".bw-install-incomplete"))}; OPEN_MODE="w"\n',
    )
    assert out["ok"] is False
    assert "cannot create" in out["err"]
    assert (destination / "active").read_text() == "old"
    assert (staging / "active").read_text() == "new"


@pytest.mark.parametrize(
    "value, port, host, expected_port",
    [
        ("redis:6380", 6379, "redis", 6380),
        ("[2001:db8::1]:6380", 6379, "[2001:db8::1]", 6380),
        ("2001:db8::1", 6379, "[2001:db8::1]", 6379),
        ("[::1]", 6379, "[::1]", 6379),
        ("redis", 6381, "redis", 6381),
        ("127.0.0.1:6379", 6380, "127.0.0.1", 6379),
    ],
)
def test_endpoint_preserves_ipv6_and_explicit_or_default_port(value, port, host, expected_port):
    out = run_core(
        BW_MODULES / "redisendpoints.lua",
        "local endpoints=dofile(MODULE); local host, port=endpoints.parse_endpoint(VALUE, PORT); emit({host=host, port=port})",
        VALUE=value,
        PORT=port,
    )
    assert out == {"host": host, "port": expected_port}


def test_absent_socket_host_remains_absent():
    out = run_core(BW_MODULES / "redisendpoints.lua", "local endpoints=dofile(MODULE); emit({absent=endpoints.socket_host(nil)==nil})")
    assert out == {"absent": True}
