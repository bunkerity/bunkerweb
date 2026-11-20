"""LX1-09: restore an aged-away failover snapshot from the DB before attempting recovery."""

import io
import logging
import shutil
import tarfile
from types import SimpleNamespace

import pytest

import cache_restore
import jobs
import test_main_loop as loop

drive = loop.drive


@pytest.mark.parametrize("state", ["deleted", "partial", "complete", "incomplete-archive", "corrupt-archive", "no-archive"])
def test_runtime_failover_recovers_only_a_complete_backup(drive, monkeypatch, state):
    target = drive.sandbox.FAILOVER_PATH
    monkeypatch.setattr(cache_restore, "FOLDER_ROOTS", (drive.sandbox.TMP_PATH,))
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        for name in ("config", "custom_configs", "cache"):
            member = tarfile.TarInfo(f"{name}/last-good")
            member.size = len(name)
            archive.addfile(member, io.BytesIO(name.encode()))
    rows = [{"file_name": f"folder:{target}.tgz", "service_id": "", "job_name": "failover-backup", "data": data.getvalue()}]
    job = object.__new__(jobs.Job)
    job.job_path = drive.sandbox.CACHE_PATH / "jobs"
    job.job_name = "failover-backup"
    job.db = SimpleNamespace(get_jobs_cache_files=lambda **kw: rows)
    job.logger = logging.getLogger("lxq-failover")
    restored = []

    def restore(**kwargs):
        restored.append(kwargs)
        return job.restore_cache(**kwargs)

    drive.job = SimpleNamespace(restore_cache=restore)
    drive.iterations = 2

    def age_snapshot():
        assert all((target / name / "last-good").is_file() for name in ("config", "cache", "custom_configs"))
        if state == "partial":
            shutil.rmtree(target / "cache")
            (target / "config/last-good").write_text("stale partial snapshot")
        elif state != "complete":
            shutil.rmtree(target)
        if state == "no-archive":
            rows.clear()
        elif state == "corrupt-archive":
            rows[0]["data"] = b"not a tar archive"
        elif state == "incomplete-archive":
            partial = io.BytesIO()
            with tarfile.open(fileobj=partial, mode="w:gz") as archive:
                for name in ("config", "custom_configs"):
                    member = tarfile.TarInfo(f"{name}/last-good")
                    member.size = len(name)
                    archive.addfile(member, io.BytesIO(name.encode()))
            rows[0]["data"] = partial.getvalue()
        drive.db.metadata["plugins_config_changed"] = ["headers"]
        loop.answer(drive, "error", "config check failed: invalid directive")

    drive.on_iteration[1] = age_snapshot
    uploads = []

    def send(path, endpoint, *args, **kwargs):
        if target in path.parents:
            uploads.append((endpoint, (path / "last-good").read_text()))
        return True

    monkeypatch.setattr(drive.main, "send_file_to_bunkerweb", send)
    drive.run()
    assert drive.stops == []
    assert restored == [{"job_name": "failover-backup", "plugin_id": "jobs"}] * (1 if state == "complete" else 2)
    if state in ("complete", "deleted", "partial"):
        assert sorted(uploads) == [("/cache", "cache"), ("/confs", "config"), ("/custom_configs", "custom_configs")]
    else:
        assert uploads == [], "an absent/failed/incomplete restore must not publish a partial rollback"
