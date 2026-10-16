import ast
from contextlib import nullcontext
from pathlib import Path
from shutil import rmtree
from tarfile import open as tar_open

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


WARNINGS = []
MATERIALIZED = []


def _load_cache_functions(cache_path, failover_path):
    WARNINGS.clear()
    MATERIALIZED.clear()
    tree = ast.parse(SOURCE.read_text())
    names = {"RETIRED_CACHE_ROWS", "RETIRED_CACHE_PATHS"}
    body = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))
        or (
            isinstance(node, ast.FunctionDef)
            and node.name in {"_purge_retired_caches", "_cache_row_usable", "_is_letsencrypt_tree", "_materialize_cache_row", "_materialize_caches"}
        )
    ]

    class Logger:
        def info(self, _message):
            pass

        def error(self, _message):
            pass

        def warning(self, message):
            WARNINGS.append(message)

    class CachePublicationLockError(Exception):
        pass

    namespace = {
        "BytesIO": __import__("io").BytesIO,
        "CachePublicationLockError": CachePublicationLockError,
        "CACHE_PATH": cache_path,
        "Database": object,
        "FAILOVER_PATH": failover_path,
        "LOGGER": Logger(),
        "Path": Path,
        "S_IRGRP": 0o040,
        "S_IRUSR": 0o400,
        "S_IWUSR": 0o200,
        # `_materialize_cache_row` swallows every exception (it logs and goes on), so raising here is not
        # enough to fail the test: the call is also recorded and asserted on below.
        "_write_atomic": lambda *args: MATERIALIZED.append(args),
        # the publication and Let's Encrypt write locks are real file locks in the job; a no-op here
        "cache_publication_lock": lambda _logger: nullcontext(),
        "le_cache_write_lock": None,
        "nullcontext": nullcontext,
        "rmtree": rmtree,
        "tar_open": tar_open,
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

    assert MATERIALIZED == [], "a retired cache row was materialized"
    assert set(db.deleted) == {
        ("api-server-cert", "api-server-cert.key"),
        ("api-server-cert", "api-server-cert.pem"),
        ("default-server-cert", "default-server-cert.key"),
        ("default-server-cert", "default-server-cert.pem"),
        # Retired when the GeoIP databases moved to the `geoip` core plugin
        ("mmdb-country", "country.mmdb"),
        ("mmdb-asn", "asn.mmdb"),
    }
    assert not any((cache_root / plugin_id / file_name).exists() for cache_root in (cache_path, snapshot_cache) for plugin_id, file_name in retired_paths)
    source = SOURCE.read_text()
    assert source.index("_purge_retired_caches(db)") < source.index("snapshot = _snapshot_failover()")


def test_retired_certificate_cache_db_failure_is_not_fatal(tmp_path):
    """A row that will not delete must not cost the fleet its configuration.

    This asserted `pytest.raises(RuntimeError)` until 2026-08-03. The raise ran before any instance
    was contacted, so one transient `(1146, "Table 'db.bw_jobs_cache' doesn't exist")` on a freshly
    forked Celery child aborted the entire push and left every instance serving the old
    configuration. `_materialize_caches` skips every RETIRED_CACHE_ROWS entry, so a surviving row
    never reaches disk nor an instance: it is worth a warning, not a dead push.
    """

    class Database:
        def __init__(self):
            self.calls = []

        def delete_job_cache(self, file_name, *, job_name):
            self.calls.append((job_name, file_name))
            return f"{job_name} database busy"

    purge, _ = _load_cache_functions(tmp_path / "cache", tmp_path / "failover")
    db = Database()

    assert purge(db) is None
    # Every row is still attempted -- one failing delete must not short-circuit the others.
    assert len(db.calls) == 6
    assert WARNINGS, "a swallowed purge failure must still be reported"


def test_an_undeletable_retired_key_file_still_aborts_the_push(tmp_path, monkeypatch):
    """The asymmetry with the test above is deliberate, and it is the security-relevant half.

    Everything left under CACHE_PATH once this returns is copied into the failover snapshot
    (`_snapshot_failover`) and shipped to every instance (`_push_all`), and the retired entries
    include `api-server-cert.key` and `default-server-cert.key`. Aborting the push beats
    redistributing retired private keys, so an unlink failure must keep propagating.
    """

    def unlink_denied(self, missing_ok=False):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "unlink", unlink_denied)
    purge, _ = _load_cache_functions(tmp_path / "cache", tmp_path / "failover")

    class Database:
        @staticmethod
        def delete_job_cache(_file_name, *, job_name):
            return ""

    with pytest.raises(PermissionError):
        purge(Database())
