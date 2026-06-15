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
