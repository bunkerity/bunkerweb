"""A forged dispatch cannot execute a file elsewhere under an allowed plugin root."""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest


@pytest.fixture
def executor(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3] / "src/worker/executor.py"
    spec = importlib.util.spec_from_file_location("contained_executor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ALLOWED_ROOTS", (tmp_path,))
    return module.JobExecutor(logging.getLogger("contained-executor"))


@pytest.mark.parametrize("kind", ["parent", "sibling", "absolute", "absolute-inside", "dotdot-inside", "symlink", "jobs-symlink"])
def test_worker_refuses_escape_without_executing(tmp_path, executor, caplog, kind):
    plugin = tmp_path / "plugin"
    jobs = plugin / "jobs"
    jobs.mkdir(parents=True)
    marker = tmp_path / "executed"
    body = f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
    outside = plugin / "other.py"
    outside.write_text(body)
    sibling = tmp_path / "other/jobs/run.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(body)
    (jobs / "run.py").write_text(body)
    (jobs / "link.py").symlink_to(sibling)
    filename = {
        "parent": "../other.py",
        "sibling": "../../other/jobs/run.py",
        "absolute": str(sibling),
        "absolute-inside": str(jobs / "run.py"),
        "dotdot-inside": "sub/../run.py",
        "symlink": "link.py",
        "jobs-symlink": "run.py",
    }[kind]
    if kind == "jobs-symlink":
        (jobs / "run.py").unlink()
        (jobs / "link.py").unlink()
        jobs.rmdir()
        jobs.symlink_to(sibling.parent, target_is_directory=True)

    assert executor.run({"name": "run", "path": str(plugin), "file": filename}) == 2
    assert not marker.exists()
    assert "jobs directory" in executor.last_error
    assert executor.last_error in caplog.text


@pytest.mark.parametrize("filename", ["run.py", "sub/run.py", "./run.py"])
def test_worker_executes_contained_relative_paths(tmp_path, executor, filename):
    plugin = tmp_path / "plugin"
    script = plugin / "jobs" / filename
    script.parent.mkdir(parents=True)
    marker = tmp_path / "executed"
    script.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    old_path = sys.path[:]
    assert executor.run({"name": "run", "path": str(plugin), "file": filename}) == 0
    assert marker.exists()
    assert sys.path == old_path


def test_system_exit_still_restores_import_path(tmp_path, executor):
    jobs = tmp_path / "plugin/jobs"
    jobs.mkdir(parents=True)
    (jobs / "run.py").write_text("raise SystemExit(1)\n")
    old_path = sys.path[:]
    with pytest.raises(SystemExit) as exc:
        executor.run({"name": "run", "path": str(jobs.parent), "file": "run.py"})
    assert exc.value.code == 1
    assert sys.path == old_path
