"""Run dependency hooks against isolated source copies and a network-free initializer."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
DEPS = ROOT / "src/deps"
C_FILE = Path("src/deps/src/lua-nginx-module/src/ngx_http_lua_ssl_certby.c")
LUA_FILE = Path("src/deps/src/lua-resty-core/lib/ngx/ssl.lua")
PATCHES = (
    (C_FILE, "lua-nginx-module-proxy-protocol-addr.patch"),
    (LUA_FILE, "lua-resty-core-proxy-protocol-addr.patch"),
)


def _run(command, cwd, **kwargs):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=30, **kwargs)


@pytest.fixture
def source_tree(tmp_path):
    shutil.copytree(DEPS / "misc", tmp_path / "src/deps/misc")
    for target, patch in PATCHES:
        source = tmp_path / target
        source.parent.mkdir(parents=True)
        shutil.copy2(ROOT / target, source)
        if "ngx_http_lua_ffi_ssl_proxy_protocol_addr" in source.read_text():
            result = _run(["patch", "--reverse", "--batch", str(target), f"src/deps/misc/{patch}"], tmp_path)
            assert result.returncode == 0, result.stdout + result.stderr
    socket_file = Path("src/deps/src/lua-nginx-module/src/ngx_http_lua_socket_tcp.c")
    shutil.copy2(ROOT / socket_file, tmp_path / socket_file)
    for dep in ("lua-nginx-module", "lua-resty-core"):
        (tmp_path / "src/deps/src" / dep / "t").mkdir()
    return tmp_path


def _hooks(work):
    manifest = json.loads((DEPS / "deps.json").read_text())
    for dep in manifest["git_repository"]:
        if dep["id"] in ("lua-nginx-module", "lua-resty-core"):
            result = _run(["bash", "-c", dep["post_install"]], work)
            if result.returncode:
                return result
    return result


@pytest.mark.parametrize("broken_patch", ["lua-nginx-module-proxy-protocol-addr.patch"])
def test_failed_patch_leaves_both_files_unchanged(source_tree, broken_patch):
    before = [(source_tree / path).read_bytes() for path, _ in PATCHES]
    (source_tree / "src/deps/misc" / broken_patch).write_text("invalid patch\n")
    result = _hooks(source_tree)
    assert result.returncode != 0, result.stdout + result.stderr
    assert before == [(source_tree / path).read_bytes() for path, _ in PATCHES]


def test_patches_reverse_apply_cleanly(source_tree):
    before = [(source_tree / path).read_bytes() for path, _ in PATCHES]
    result = _hooks(source_tree)
    assert result.returncode == 0, result.stdout + result.stderr
    for path, patch in PATCHES:
        result = _run(["patch", "--reverse", "--batch", str(path), f"src/deps/misc/{patch}"], source_tree)
        assert result.returncode == 0, result.stdout + result.stderr
    assert before == [(source_tree / path).read_bytes() for path, _ in PATCHES]


def _initializer_tree(tmp_path, entries):
    (tmp_path / "src/deps/src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src/deps/deps.json").write_text(json.dumps(entries))
    # Fetching is irrelevant to hook status propagation; do not contact upstream.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text("#!/bin/sh\nexit 0\n")
    git.chmod(0o755)
    return dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")


def test_initializer_accepts_successful_post_install(tmp_path):
    dep = {"id": "ok", "name": "Working dependency", "url": "unused", "commit": "unused", "post_install": "touch hook-ran"}
    env = _initializer_tree(tmp_path, {"download": [], "git_repository": [dep]})
    result = _run(["bash", str(DEPS / "init_deps.sh")], tmp_path, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "hook-ran").exists()


def test_hooks_patch_both_files_and_second_run_is_a_noop(source_tree):
    result = _hooks(source_tree)
    assert result.returncode == 0, result.stdout + result.stderr
    first = [(source_tree / path).read_bytes() for path, _ in PATCHES]
    assert first[0].count(b"ngx_http_lua_ffi_ssl_proxy_protocol_addr(") == 1
    assert first[1].count(b"function _M.proxy_protocol_addr()") == 1
    result = _hooks(source_tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert first == [(source_tree / path).read_bytes() for path, _ in PATCHES]
