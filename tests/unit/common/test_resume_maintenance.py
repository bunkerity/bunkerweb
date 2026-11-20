"""Maintenance ports: execute product code while isolating external services."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from jinja2 import Environment
from sqlalchemy import event

from fixtures.seed import seed_minimal, session
from model import Jobs, Plugins

ROOT = Path(__file__).resolve().parents[3]
COMMON = ROOT / "src/common"


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
