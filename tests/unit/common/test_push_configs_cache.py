import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


def _load_cache_functions(cache_path, failover_path):
    tree = ast.parse(SOURCE.read_text())
    names = {"RETIRED_CACHE_ROWS", "RETIRED_CACHE_PATHS"}
    body = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))
        or (isinstance(node, ast.FunctionDef) and node.name in {"_purge_retired_caches", "_materialize_caches"})
    ]

    class Logger:
        def info(self, _message):
            pass

        def error(self, _message):
            pass

    namespace = {
        "BytesIO": __import__("io").BytesIO,
        "CACHE_PATH": cache_path,
        "Database": object,
        "FAILOVER_PATH": failover_path,
        "LOGGER": Logger(),
        "Path": Path,
        "S_IRGRP": 0o040,
        "S_IRUSR": 0o400,
        "S_IWUSR": 0o200,
        "_write_atomic": lambda *_args: pytest.fail("retired cache was materialized"),
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["_purge_retired_caches"], namespace["_materialize_caches"]


def test_retired_certificate_caches_are_deleted_and_never_materialized(tmp_path):
    retired_paths = {
        ("jobs", "api-server-cert.key"),
        ("jobs", "api-server-cert.pem"),
        ("misc", "api-server-cert.key"),
        ("misc", "api-server-cert.pem"),
        ("misc", "default-server-cert.key"),
        ("misc", "default-server-cert.pem"),
    }
    cache_path = tmp_path / "cache"
    failover_path = tmp_path / "failover"
    snapshot_cache = failover_path / "previous" / "cache"
    for cache_root in (cache_path, snapshot_cache):
        for plugin_id, file_name in retired_paths:
            path = cache_root / plugin_id / file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"secret")

    class Database:
        def __init__(self):
            self.deleted = []

        def delete_job_cache(self, file_name, *, job_name):
            self.deleted.append((job_name, file_name))
            return ""

        def get_jobs_cache_files(self):
            return [
                {
                    "plugin_id": plugin_id,
                    "job_name": "default-server-cert" if file_name.startswith("default") else "api-server-cert",
                    "file_name": file_name,
                    "data": b"secret",
                }
                for plugin_id, file_name in retired_paths
            ]

    db = Database()
    purge, materialize = _load_cache_functions(cache_path, failover_path)
    purge(db)
    materialize(db)

    assert set(db.deleted) == {
        ("api-server-cert", "api-server-cert.key"),
        ("api-server-cert", "api-server-cert.pem"),
        ("default-server-cert", "default-server-cert.key"),
        ("default-server-cert", "default-server-cert.pem"),
    }
    assert not any((cache_root / plugin_id / file_name).exists() for cache_root in (cache_path, snapshot_cache) for plugin_id, file_name in retired_paths)
    source = SOURCE.read_text()
    assert source.index("_purge_retired_caches(db)") < source.index("snapshot = _snapshot_failover()")


def test_retired_certificate_cache_db_failure_is_fatal(tmp_path):
    class Database:
        @staticmethod
        def delete_job_cache(_file_name, *, job_name):
            return f"{job_name} database busy"

    purge, _ = _load_cache_functions(tmp_path / "cache", tmp_path / "failover")

    with pytest.raises(RuntimeError, match="Failed to purge retired caches from the database"):
        purge(Database())
