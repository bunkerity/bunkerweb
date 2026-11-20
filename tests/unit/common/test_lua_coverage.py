"""Exercise coverage through stdin, standalone scripts, concurrent exits and unloaded files."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "lua_coverage.py"
pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="Lua interpreter required")


def _tool():
    assert TOOL.exists(), "Lua coverage runner missing"
    probe = subprocess.run(["lua", "-e", 'require("luacov.runner")'], capture_output=True, text=True)
    if probe.returncode:
        pytest.skip("LuaCov not installed; use the pinned install in unit-tests.yml")
    spec = importlib.util.spec_from_file_location("lua_coverage", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_combines_processes_and_counts_unloaded_sources(tmp_path):
    tool = _tool()
    source = tmp_path / "src/bw/lua/probe.lua"
    source.parent.mkdir(parents=True)
    source.write_text("local value = ...\nif value then\n    return 1\nelse\n    return 2\nend\n")
    unloaded = tmp_path / "src/common/core/example/unloaded.lua"
    unloaded.parent.mkdir(parents=True)
    unloaded.write_text("-- never required\nlocal value = 1\nreturn value\n")
    # Bundled libraries outside src/deps must remain in the denominator.
    bundled = tmp_path / "src/common/core/crowdsec/lib/unloaded.lua"
    bundled.parent.mkdir(parents=True)
    bundled.write_text("return 1\n")
    vendored = tmp_path / "src/deps/ignored.lua"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("return 1\n")
    output = tmp_path / "coverage"
    env = tool.coverage_env(output)
    script = tmp_path / "standalone.lua"
    script.write_text(f"assert(loadfile({json.dumps(str(source))}))(true)\nos.exit(0)\n")
    # Run both processes together: sharing one stats file loses updates.
    standalone = subprocess.Popen(["lua", str(script)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdin = subprocess.Popen(["lua", "-"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _, err = stdin.communicate(f"assert(loadfile({json.dumps(str(source))}))(false)\n", timeout=30)
    assert stdin.returncode == 0, err
    _, err = standalone.communicate(timeout=30)
    assert standalone.returncode == 0, err
    assert len(list(output.glob("*.stats.out"))) == 2
    tool.report(output, root=tmp_path)
    data = json.loads((output / "coverage.json").read_text())
    files = {row["path"]: row for row in data["files"]}
    assert set(files) == {str(path.relative_to(tmp_path)) for path in (source, unloaded, bundled)}
    assert files["src/bw/lua/probe.lua"]["covered"] == files["src/bw/lua/probe.lua"]["lines"]
    assert files["src/common/core/example/unloaded.lua"]["covered"] == 0
    assert files["src/common/core/example/unloaded.lua"]["lines"] == 2
    assert files["src/common/core/crowdsec/lib/unloaded.lua"]["covered"] == 0
    lcov = (output / "coverage.lcov").read_text()
    assert "DA:3,1\n" in lcov and "DA:5,1\n" in lcov
    assert "SF:src/common/core/example/unloaded.lua\nDA:2,0\nDA:3,0\nLF:2\nLH:0\n" in lcov


def test_run_preserves_command_failure_and_normal_run_stays_uninstrumented(tmp_path):
    _tool()
    output = tmp_path / "coverage"
    result = subprocess.run([sys.executable, str(TOOL), "run", str(output), "--", "lua", "-e", "os.exit(7)"], capture_output=True, text=True)
    assert result.returncode == 7, result.stderr
    assert list(output.glob("*.stats.out"))
    env = {key: value for key, value in os.environ.items() if not key.startswith("LUA_INIT") and key != "BW_LUA_COVERAGE_DIR"}
    result = subprocess.run(["lua", "-e", 'assert(not package.loaded["luacov.runner"])'], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_report_refuses_missing_measurement(tmp_path):
    tool = _tool()
    with pytest.raises(ValueError, match="No LuaCov stats"):
        tool.report(tmp_path)


@pytest.mark.parametrize("floor, code", [(51, 1), (50, 0)], ids=["below-floor", "at-floor"])
def test_report_enforces_floor_and_accepts_exact_boundary(tmp_path, monkeypatch, capsys, floor, code):
    tool = _tool()
    source = tmp_path / "src/bw/lua/probe.lua"
    source.parent.mkdir(parents=True)
    source.write_text("return 1\n")
    (source.parent / "unloaded.lua").write_text("return 2\n")
    output = tmp_path / "coverage"
    subprocess.run(["lua", str(source)], env=tool.coverage_env(output), check=True, timeout=30)
    original_report = tool.report
    monkeypatch.setattr(tool, "report", lambda directory: original_report(directory, root=tmp_path))
    monkeypatch.setattr(sys, "argv", [str(TOOL), "report", str(output), "--fail-under", str(floor)])
    assert tool.main() == code
    assert json.loads((output / "coverage.json").read_text())["total"]["percent"] == 50.0
    assert f"floor {floor}%" in capsys.readouterr().out
