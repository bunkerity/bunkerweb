"""DatabaseJobsMixin — job-run history and job-cache CRUD.

Jobs_runs/Jobs_cache carry FKs to Jobs.name (and Jobs -> Plugins), so ``seed_minimal``
(which creates plugin ``general`` + job ``testjob``) is required for PG/MariaDB.
"""

from datetime import datetime, timedelta, timezone

import pytest

from fixtures.seed import seed_minimal

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def jdb(db):
    seed_minimal(db)
    return db


class TestJobRuns:
    def test_add_and_get_history(self, jdb):
        assert jdb.add_job_run("testjob", True, DT) == ""
        jobs = jdb.get_jobs()
        assert jobs["testjob"]["plugin_id"] == "general"
        assert jobs["testjob"]["every"] == "hour"
        assert len(jobs["testjob"]["history"]) == 1
        assert jobs["testjob"]["history"][0]["success"] is True

    def test_cleanup_excess_keeps_newest(self, jdb):
        for _ in range(5):
            jdb.add_job_run("testjob", True, DT)
        assert jdb.cleanup_jobs_runs_excess(2) == "Removed 3 excess jobs runs"
        assert len(jdb.get_jobs()["testjob"]["history"]) == 2

    def test_cleanup_under_limit_noop(self, jdb):
        jdb.add_job_run("testjob", True, DT)
        assert jdb.cleanup_jobs_runs_excess(10) == "Removed 0 excess jobs runs"

    def test_get_last_job_run_returns_the_newest_run(self, jdb):
        newest = DT.astimezone() + timedelta(minutes=1)
        jdb.add_job_run("testjob", True, DT, DT)
        jdb.add_job_run("testjob", False, newest, newest)

        last_run = jdb.get_last_job_run("testjob")

        assert last_run["success"] is False
        assert datetime.fromisoformat(last_run["end_date"]) == newest

    def test_get_last_job_run_returns_none_for_an_absent_job(self, jdb):
        assert jdb.get_last_job_run("missing-job") is None


class TestJobCache:
    def test_upsert_insert_update_and_checksum_skip(self, jdb):
        assert jdb.upsert_job_cache(None, "f.txt", b"v1", job_name="testjob", checksum="c1") == ""
        assert jdb.get_job_cache_file("testjob", "f.txt") == b"v1"
        # same checksum -> data is NOT replaced (only the expiry timestamp refreshes)
        assert jdb.upsert_job_cache(None, "f.txt", b"v2-ignored", job_name="testjob", checksum="c1") == ""
        assert jdb.get_job_cache_file("testjob", "f.txt") == b"v1"
        # changed checksum -> data replaced
        assert jdb.upsert_job_cache(None, "f.txt", b"v3", job_name="testjob", checksum="c2") == ""
        assert jdb.get_job_cache_file("testjob", "f.txt") == b"v3"

    def test_plugin_id_gate(self, jdb):
        jdb.upsert_job_cache(None, "f.txt", b"v1", job_name="testjob", checksum="c1")
        assert jdb.get_job_cache_file("testjob", "f.txt", plugin_id="wrong") is None
        assert jdb.get_job_cache_file("testjob", "f.txt", plugin_id="general") == b"v1"

    def test_delete_job_cache(self, jdb):
        jdb.upsert_job_cache(None, "f.txt", b"v1", job_name="testjob", checksum="c1")
        assert jdb.delete_job_cache("f.txt", job_name="testjob") == ""
        assert jdb.get_job_cache_file("testjob", "f.txt") is None

    def test_get_jobs_cache_files(self, jdb):
        jdb.upsert_job_cache(None, "f.txt", b"v1", job_name="testjob", checksum="c1")
        files = jdb.get_jobs_cache_files(job_name="testjob")
        assert len(files) == 1
        assert files[0]["plugin_id"] == "general"
        assert files[0]["job_name"] == "testjob"
        assert files[0]["file_name"] == "f.txt"
