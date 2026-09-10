"""``jobs/custom-cert.py``'s single-site roster strip now calls `strip_default_server` /
`strip_default_server_unless_alone` (wave 19, lane N18 -- port of note #10) instead of hand-rolling
`kept or all_domains`. `tests/unit/certificates/test_custom_cert_single_site_default_server.py`
already proves the helper's two named edge inputs end to end (reserved id alone -> kept; reserved id
plus an alias -> stripped, both through `import_certificate`). Neither drives a `SERVER_NAME` that
repeats the reserved id with nothing else: this pins that shape down. A regression that let
`strip_default_server_unless_alone` empty the roster would not reach `all_domains[0]` (line 408) at
all -- `if not all_domains:` (line 401) exits first, logging "No services found, exiting ...". That
is the wrong-path signature this test rules out, by asserting the RIGHT path is reached instead: the
per-service "Custom SSL is not enabled, skipping" branch, which only runs when `all_domains` still
holds the (kept, not stripped) reserved id.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "customcert" / "jobs" / "custom-cert.py"


def run_job(monkeypatch, **environment):
    """Execute the job end to end against a mocked `Job`; return (the mock, the exit code)."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in ("SERVER_NAME", "MULTISITE", "DISABLE_DEFAULT_SERVER", "USE_CUSTOM_SSL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    job_mock = Mock()
    job_mock.cache_hash.return_value = None
    job_mock.cache_file.return_value = (True, "")
    job_mock.del_cache.return_value = (True, "")
    job_mock.db.import_certificate.return_value = ("", None)

    jobs_module = ModuleType("jobs")
    jobs_module.Job = Mock(return_value=job_mock)
    logger_module = ModuleType("logger")
    logger_mock = Mock()
    logger_module.getLogger = Mock(return_value=logger_mock)
    job_mock.test_logger = logger_mock

    module = ModuleType("bw_custom_cert_executed")
    module.__dict__["__file__"] = str(JOB_PATH)
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    with patch.dict(sys.modules, {"jobs": jobs_module, "logger": logger_module}):
        with pytest.raises(SystemExit) as exited:
            exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return job_mock, exited.value.code


class TestDuplicateReservedIdOnly:
    def test_two_copies_of_the_reserved_id_alone_do_not_empty_the_roster(self, monkeypatch):
        """A strip that collapsed `["default-server", "default-server"]` to `[]` -- instead of
        keeping it, because nothing else remains once the reserved id is removed -- would exit
        through the `if not all_domains:` guard with "No services found, exiting ..." and never
        reach the per-service branch at all."""
        job_mock, _ = run_job(
            monkeypatch,
            SERVER_NAME="default-server default-server",
            MULTISITE="no",
            USE_CUSTOM_SSL="no",
        )
        info = "\n".join(str(call.args[0]) for call in job_mock.test_logger.info.call_args_list)
        assert "Custom SSL is not enabled, skipping" in info
        assert "No services found" not in info
        assert not job_mock.db.import_certificate.called
