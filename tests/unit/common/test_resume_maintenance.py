"""Maintenance ports: execute product code while isolating external services."""

import importlib.util
import json
import re
import runpy
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from jinja2 import Environment
from sqlalchemy import event

from fixtures.seed import seed_minimal, session
from jobs import Job
from model import Jobs, Plugins

ROOT = Path(__file__).resolve().parents[3]
COMMON = ROOT / "src/common"


@pytest.mark.parametrize("engine,maria_client,routines", [("mysql", True, False), ("mariadb", True, True), ("mysql", False, True)])
def test_dump_routines_follow_server_and_client(engine, maria_client, routines, monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("resume_backup", COMMON / "core/backup/backup.py")
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    runner = Mock(return_value=SimpleNamespace(stdout=b"SQL", stderr=b"", returncode=0))
    monkeypatch.setattr(backup, "run", runner)
    monkeypatch.setattr(backup, "mysql_client_command", lambda _: ("mariadb-dump" if maria_client else "mysqldump", maria_client))
    db = SimpleNamespace(database_uri=f"{engine}://user:password@localhost/data")
    _, archive = backup.backup_database(datetime.now().astimezone(), db, tmp_path)
    cmd = runner.call_args.args[0]
    assert ("--routines" in cmd) is routines
    assert all(flag in cmd for flag in ("--single-transaction", "--triggers", "--events", "--no-tablespaces"))
    assert archive.exists()


def _run_lua(body, harness):
    lua = shutil.which("lua") or shutil.which("luajit")
    if not lua:
        pytest.skip("standalone Lua unavailable")
    result = subprocess.run([lua, "-"], input=harness + "\nlocal function content()\n" + body + "\nend\ncontent()\n", text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("loading,marker,expected", [("no", True, "ok"), ("no", False, "ok"), ("yes", True, "loading"), (False, False, "loading")])
def test_readiness_uses_configuration_not_reload_marker(loading, marker, expected):
    config = (COMMON / "confs/healthcheck.conf").read_text()
    body = config.split("content_by_lua_block {", 1)[1].split("\n\t\t}", 1)[0]
    state = json.dumps(loading) if loading else "nil"
    harness = f"""
package.preload['bunkerweb.utils'] = function() return {{ get_variable = function() return {state} end }} end
ngx = {{ say = print }}
io.open = function() return {"{ close = function() end }" if marker else "nil"} end
"""
    assert _run_lua(body, harness) == expected


def test_loading_body_has_retry_status():
    config = (COMMON / "confs/default-server-http.conf").read_text()
    loading = config.split('{% if IS_LOADING == "yes" +%}', 1)[1].split("{% endif %}", 1)[0]
    body = loading.split("content_by_lua_block {", 1)[1].rsplit("\n\t\t}", 1)[0]
    harness = """
ngx = { header = {}, var = { scheme = 'http' }, config = { subsystem = 'http' }, HTTP_SERVICE_UNAVAILABLE = 503 }
package.preload['bunkerweb.utils'] = function() return { rand = function() return 'nonce' end } end
package.preload['resty.template'] = function() return { render = function(name)
    assert(name == 'index.html')
    assert(ngx.status == 503, 'loading response must be 503')
    assert(ngx.header['Retry-After'] == '3', 'loading retry delay must be 3')
    print('loading body rendered')
end } end
"""
    assert _run_lua(body, harness) == "loading body rendered"


def test_default_page_only_claims_root_and_keeps_deny_guard():
    template = (COMMON / "core/misc/confs/default-server-http/page.conf").read_text()
    rendered = Environment().from_string(template).render(IS_LOADING="no", DISABLE_DEFAULT_SERVER="yes", DENY_HTTP_STATUS="403")
    assert re.search(r"location\s+=\s+/\s*\{", rendered), "prefix / wrongly serves default page for arbitrary paths"
    assert 'if ($default_server_allowed != "yes")' in rendered
    assert "return 403;" in rendered
    assert not Environment().from_string(template).render(IS_LOADING="yes")


@pytest.fixture
def cache_db(db):
    seed_minimal(db)
    with session(db) as s:
        s.add(Plugins(id="other", name="Other", description="Other", version="1.0"))
        s.flush()
        s.add_all(
            [
                Jobs(name="sibling", plugin_id="general", file_name="sibling.py", every="hour"),
                Jobs(name="unrelated", plugin_id="other", file_name="other.py", every="hour"),
            ]
        )
    for job_name in ("testjob", "sibling", "unrelated"):
        assert db.upsert_job_cache(None, f"{job_name}.bin", job_name.encode(), job_name=job_name) == ""
    return db


def test_cache_plugin_filter_is_in_sql(cache_db):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(cache_db.sql_engine, "before_cursor_execute", capture)
    try:
        rows = cache_db.get_jobs_cache_files(plugin_id="general")
    finally:
        event.remove(cache_db.sql_engine, "before_cursor_execute", capture)
    assert {row["job_name"] for row in rows} == {"testjob", "sibling"}
    blob_queries = [sql for sql in statements if "bw_jobs_cache.data" in sql]
    assert len(blob_queries) == 1
    assert "JOIN" in blob_queries[0] and "bw_jobs.plugin_id" in blob_queries[0].split("WHERE")[-1], statements


def test_selective_blobs_retain_sibling_metadata(cache_db):
    rows = cache_db.get_jobs_cache_files(plugin_id="general", data_job_name="testjob")
    assert {row["job_name"] for row in rows} == {"testjob", "sibling"}
    assert next(row for row in rows if row["job_name"] == "testjob")["data"] == b"testjob"
    assert "data" not in next(row for row in rows if row["job_name"] == "sibling")
    assert all("data" not in row for row in cache_db.get_jobs_cache_files(plugin_id="general", with_data=False))
    assert len(cache_db.get_jobs_cache_files(job_name="testjob")) == 1


def test_restore_selects_blobs_without_deleting_siblings(tmp_path):
    job = Job.__new__(Job)
    job.job_path = tmp_path / "general"
    job.job_path.mkdir()
    job.job_name = "testjob"
    job.logger = Mock()
    (job.job_path / "sibling.bin").write_bytes(b"existing sibling")
    sibling_dir = job.job_path / "tree"
    sibling_dir.mkdir()
    (sibling_dir / "keep.pem").write_bytes(b"existing folder")
    job.db = Mock()
    job.db.get_jobs_cache_files.return_value = [
        {"job_name": "testjob", "service_id": "mine", "file_name": "testjob.bin", "data": b"restored"},
        {"job_name": "sibling", "service_id": None, "file_name": "sibling.bin"},
        {"job_name": "sibling", "service_id": "tree", "file_name": "certs.tgz"},
    ]
    assert job._restore_cache(manual=False)
    assert (job.job_path / "mine/testjob.bin").read_bytes() == b"restored"
    assert (job.job_path / "sibling.bin").read_bytes() == b"existing sibling"
    assert (sibling_dir / "keep.pem").read_bytes() == b"existing folder"
    job.db.get_jobs_cache_files.assert_called_once_with(plugin_id="general", data_job_name="testjob")


def _report(i):
    return {"date": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=i)).isoformat(), "id": i}


def _run_send(monkeypatch, reports, replies, cache_ok=True):
    job = Mock()
    job.db.get_metadata.return_value = {"scheduler_first_start": False}
    job.db.get_instances.return_value = []
    job.get_cache.side_effect = lambda name, **kw: (
        b"id" if name == "instance.id" else json.dumps({"created": datetime.now().astimezone().isoformat(), "reports": []}).encode()
    )
    job.cache_file.return_value = (cache_ok, "cache failure" if not cache_ok else "")
    job.del_cache.return_value = (True, "")
    caller = Mock()
    caller.send_to_apis.return_value = (True, {"instance": {"status": "success", "msg": reports}})
    sender = Mock(side_effect=replies)
    for name, attrs in {
        "jobs": {"Job": Mock(return_value=job)},
        "logger": {"getLogger": Mock(return_value=Mock())},
        "API": {"API": Mock()},
        "ApiCaller": {"ApiCaller": Mock(return_value=caller)},
        "bunkernet": {"send_reports": sender},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("MULTISITE", "no")
    monkeypatch.setenv("USE_BUNKERNET", "yes")
    monkeypatch.setattr("time.sleep", lambda _: None)
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(COMMON / "core/bunkernet/jobs/bunkernet-send.py"), run_name="__main__")
    return job, sender, exit_info.value.code


def test_report_cap_keeps_newest_and_sorts_unsorted_inputs(monkeypatch):
    job, sender, status = _run_send(monkeypatch, [_report(i) for i in reversed(range(10005))], [(True, 429, {})])
    assert status == 0
    sent = sender.call_args.args[0]
    assert [row["id"] for row in sent] == list(range(100))
    payload = job.cache_file.call_args.args[1]
    cached = json.loads(payload)["reports"]
    assert [row["id"] for row in cached] == list(range(5, 10005))
    assert b"\n" not in payload


def test_report_cap_applies_to_each_ack_and_retains_failed_batch(monkeypatch):
    job, sender, status = _run_send(monkeypatch, [_report(i) for i in reversed(range(10205))], [(True, 200, {}), (True, 403, {})])
    assert status == 0
    assert len(sender.call_args_list) == 2
    snapshots = [json.loads(call.args[1])["reports"] for call in job.cache_file.call_args_list]
    assert len(snapshots) == 2
    assert all(len(snapshot) <= 10000 for snapshot in snapshots)
    assert all(row["id"] >= 205 for row in snapshots[-1])
    assert all(row["id"] >= 100 for row in snapshots[0]), "acknowledged batch would be replayed"


def test_report_cache_failure_stops_before_second_batch(monkeypatch):
    job, sender, status = _run_send(monkeypatch, [_report(i) for i in range(250)], [(True, 200, {})], cache_ok=False)
    assert status == 2
    assert sender.call_count == 1
    assert not job.del_cache.called
