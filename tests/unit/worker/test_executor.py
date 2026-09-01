"""worker/executor.py JobExecutor._is_allowed_job_path — job sandbox path guard.

Loaded by file path (executor.py is stdlib-only, no relative imports, no Celery at
module load). The guard decides whether a resolved job path is under an allowed root —
the boundary that stops a crafted job path from executing arbitrary files.
"""

import importlib.util
import logging
from pathlib import Path

_EXECUTOR = Path(__file__).resolve().parents[3] / "src" / "worker" / "executor.py"
_spec = importlib.util.spec_from_file_location("bw_worker_executor", _EXECUTOR)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
JobExecutor = _mod.JobExecutor

LOGGER = logging.getLogger("exec-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)


class TestIsAllowedJobPath:
    def _ex(self):
        return JobExecutor(LOGGER)

    def test_paths_under_allowed_roots(self):
        ex = self._ex()
        assert ex._is_allowed_job_path(Path("/usr/share/bunkerweb/core/myplugin/jobs/x.py")) is True
        assert ex._is_allowed_job_path(Path("/etc/bunkerweb/plugins/p/jobs/y.py")) is True
        assert ex._is_allowed_job_path(Path("/etc/bunkerweb/pro/plugins/pp/jobs/z.py")) is True

    def test_paths_outside_allowed_roots(self):
        ex = self._ex()
        assert ex._is_allowed_job_path(Path("/etc/passwd")) is False
        assert ex._is_allowed_job_path(Path("/tmp/evil/jobs/x.py")) is False
        # sibling of an allowed root, but not under it
        assert ex._is_allowed_job_path(Path("/usr/share/bunkerweb/coreXX/jobs/x.py")) is False

    def test_allowed_roots_constant(self):
        assert _mod.ALLOWED_ROOTS  # non-empty tuple of roots


class TestLastError:
    """`run` returns a bare int, so a job that never even loads is recorded as "2" and nothing else.
    `last_error` is what lets `tasks.execute_job` put the reason on the job run instead."""

    def test_a_refused_path_leaves_the_reason_behind(self, tmp_path):
        ex = JobExecutor(LOGGER)

        assert ex.run({"name": "evil", "path": str(tmp_path), "file": "x.py"}) == 2
        assert "outside allowed job directories" in ex.last_error

    def test_a_successful_run_clears_the_previous_reason(self, tmp_path, monkeypatch):
        """The executor is reused across dispatches in a worker child, so a stale message would be
        attributed to the next job that fails for an unrelated reason."""
        job = tmp_path / "jobs"
        job.mkdir()
        (job / "ok.py").write_text("x = 1\n")
        monkeypatch.setattr(_mod, "ALLOWED_ROOTS", (tmp_path,))

        ex = JobExecutor(LOGGER)
        ex.run({"name": "evil", "path": str(tmp_path.parent), "file": "x.py"})
        assert ex.last_error is not None

        assert ex.run({"name": "ok", "path": str(tmp_path), "file": "ok.py"}) == 0
        assert ex.last_error is None

    def test_a_job_that_raises_reports_what_it_raised(self, tmp_path, monkeypatch):
        job = tmp_path / "jobs"
        job.mkdir()
        (job / "boom.py").write_text("raise RuntimeError('upstream unreachable')\n")
        monkeypatch.setattr(_mod, "ALLOWED_ROOTS", (tmp_path,))

        ex = JobExecutor(LOGGER)

        assert ex.run({"name": "boom", "path": str(tmp_path), "file": "boom.py"}) == 2
        assert "upstream unreachable" in ex.last_error
