import sys
from types import ModuleType
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
for source_dir in (REPO_ROOT / "src/common/db", REPO_ROOT / "src/common/utils", REPO_ROOT / "src/api"):
    sys.path.insert(0, str(source_dir))

from Database import Database  # noqa: E402
from logger import getLogger  # noqa: E402
from model import Base, Jobs, Jobs_cache, Plugins  # noqa: E402

auth_guard_module = ModuleType("app.auth.guard")


def guard_stub():
    return None


auth_guard_module.guard = guard_stub
sys.modules["app.auth.guard"] = auth_guard_module

from app.routers import cache as cache_router  # noqa: E402


class CacheDeletePluginBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "db.sqlite3"
        self.database = Database(getLogger("TEST"), f"sqlite:///{database_path}", log=False)
        Base.metadata.create_all(self.database.sql_engine)
        self._seed_database()

        self.api = FastAPI()
        self.api.include_router(cache_router.router)
        self.client = TestClient(self.api)
        self.db_patch = patch.object(cache_router, "get_db", return_value=self.database)
        self.db_patch.start()
        self.checked_changes_patch = patch.object(self.database, "checked_changes", return_value="")
        self.checked_changes = self.checked_changes_patch.start()

    def tearDown(self):
        self.checked_changes_patch.stop()
        self.db_patch.stop()
        self.client.close()
        self.database.close()
        self.temp_dir.cleanup()

    def _seed_database(self):
        with self.database._db_session() as session:
            session.add_all(
                [
                    Plugins(id="p1", name="p1", description="", version="1", type="external"),
                    Plugins(id="p2", name="p2", description="", version="1", type="external"),
                    Jobs(name="j1", plugin_id="p1", file_name="j1.py", every="day"),
                    Jobs(name="j2", plugin_id="p2", file_name="j2.py", every="day"),
                    Jobs_cache(job_name="j1", service_id=None, file_name="owned.pem", data=b"certificate"),
                ]
            )
            session.commit()

    def _delete_bulk(self, *, plugin, job_name, file_name):
        return self.client.request(
            "DELETE",
            "/cache",
            json={"cache_files": [{"service": "global", "plugin": plugin, "jobName": job_name, "fileName": file_name}]},
        )

    def _cache_exists(self):
        with self.database._db_session() as session:
            return session.query(Jobs_cache).filter_by(job_name="j1", file_name="owned.pem", service_id=None).first() is not None

    def test_bulk_nonexistent_file_is_not_reported_as_deleted(self):
        response = self._delete_bulk(plugin="p2", job_name="j2", file_name="no-such-file")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["deleted"], 0)
        self.assertIn("errors", response.json())
        self.checked_changes.assert_not_called()

    def test_bulk_wrong_plugin_preserves_row_and_does_not_notify_scheduler(self):
        response = self._delete_bulk(plugin="p2", job_name="j1", file_name="owned.pem")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["deleted"], 0)
        self.assertTrue(self._cache_exists())
        self.checked_changes.assert_not_called()

    def test_bulk_correct_plugin_deletes_row_and_notifies_actual_plugin(self):
        response = self._delete_bulk(plugin="p1", job_name="j1", file_name="owned.pem")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"], 1)
        self.assertFalse(self._cache_exists())
        self.checked_changes.assert_called_once()
        self.assertEqual(self.checked_changes.call_args.kwargs["plugins_changes"], ["p1"])

    def test_single_wrong_plugin_returns_not_found_and_preserves_row(self):
        response = self.client.delete("/cache/global/p2/j1/owned.pem")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(self._cache_exists())
        self.checked_changes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
