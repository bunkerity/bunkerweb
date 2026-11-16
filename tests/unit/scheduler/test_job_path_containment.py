"""Job discovery must reject paths escaping the plugin's own jobs directory."""

import logging

import pytest

from JobScheduler import JobScheduler


@pytest.mark.parametrize("kind", ["parent", "sibling", "absolute", "absolute-inside", "dotdot-inside", "symlink", "jobs-symlink"])
def test_scheduler_rejects_job_path_escape(tmp_path, caplog, kind):
    plugin = tmp_path / "plugin"
    jobs = plugin / "jobs"
    jobs.mkdir(parents=True)
    outside = tmp_path / "other.py"
    outside.write_text("raise AssertionError('must not run')\n")
    (jobs / "link.py").symlink_to(outside)
    filename = {
        "parent": "../other.py",
        "sibling": "../../other/jobs/run.py",
        "absolute": str(outside),
        "absolute-inside": str(jobs / "run.py"),
        "dotdot-inside": "sub/../run.py",
        "symlink": "link.py",
        "jobs-symlink": "run.py",
    }[kind]
    if kind == "jobs-symlink":
        (jobs / "link.py").unlink()
        jobs.rmdir()
        jobs.symlink_to(tmp_path, target_is_directory=True)
    scheduler = JobScheduler(logging.getLogger("path-containment"))
    job = {"name": "run", "file": filename, "every": "hour", "reload": False}

    assert scheduler._JobScheduler__validate_jobs([job], "plugin", str(plugin / "plugin.json")) == []
    assert "jobs directory" in caplog.text


@pytest.mark.parametrize("filename", ["run.py", "sub/run.py", "./run.py"])
def test_scheduler_keeps_contained_relative_paths(tmp_path, filename):
    scheduler = JobScheduler()
    job = {"name": "run", "file": filename, "every": "hour", "reload": False}
    assert scheduler._JobScheduler__validate_jobs([job], "plugin", str(tmp_path / "plugin.json")) == [job]
