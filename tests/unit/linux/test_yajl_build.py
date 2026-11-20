"""RHEL 10 must build YAJL before ModSecurity and fail closed on build errors."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("os_name,version", [("rhel", "10"), ("rhel", "9"), ("debian", "13"), ("", "")])
@pytest.mark.parametrize("fail_cmake", [False, True])
def test_yajl_build_is_scoped_and_required(tmp_path, os_name, version, fail_cmake):
    text = (ROOT / "src/deps/install.sh").read_text()
    # Exercise the production shell flow, replacing only costly build commands.
    prefix = text.split("# Compiling and installing lua\n", 1)[0]
    body = text.split("# Compiling and installing zlib\n", 1)[1].split("# Compiling and installing luajit\n", 1)[0]
    calls = tmp_path / "calls"
    script = prefix + f"""
        export CHANGE_DIR=''
        cmake() {{ echo "cmake $*" >> '{calls}'; return {9 if fail_cmake else 0}; }}
        make() {{ echo "make $*" >> '{calls}'; }}
        cp() {{ :; }}
        mv() {{ :; }}
        mkdir() {{ :; }}
        chmod() {{ :; }}
        configure() {{ case "$*" in *--disable-dependency-tracking*) echo "configure $*" >> '{calls}';; esac; }}
        build() {{ :; }}
        sh() {{ :; }}
    """
    # Do not change real directories or execute vendored configure in this unit check.
    body = body.replace("export CHANGE_DIR=", "# export CHANGE_DIR=").replace("./configure", "configure").replace("./build.sh", "build")
    result = subprocess.run(["bash", "-c", script + body], env={**os.environ, "OS": os_name, "OS_VERSION": version}, text=True, capture_output=True)
    log = calls.read_text() if calls.exists() else ""
    required = os_name == "rhel" and version == "10"
    assert result.returncode == (9 if required and fail_cmake else 0), result.stdout + result.stderr
    if required:
        assert "cmake " in log, "RHEL 10 compiled without vendored YAJL"
        if fail_cmake:
            assert "configure " not in log, "ModSecurity configured after YAJL build failure"
        else:
            assert "--with-yajl=/tmp/bunkerweb/yajl" in log
            assert "CMAKE_POSITION_INDEPENDENT_CODE=ON" in log
            assert log.index("cmake ") < log.index("configure ")
    else:
        assert "cmake " not in log
        assert "--with-yajl=/tmp/bunkerweb/yajl" not in log
