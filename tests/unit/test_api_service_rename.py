"""PATCH /services/{old} rename must carry every service-owned row along with it.

`update_service` used to rename a service by rewriting the SERVER_NAME-prefixed keys
in the full config snapshot and calling `save_config`. Because the old service id
disappears from the incoming config, `save_config` treats that as a deletion of the
old service, which cascades away its custom configs and job cache rows (real bug,
seen on a stack with a stored custom ModSecurity rule: after a rename, `GET
/configs?service=<new>&with_data=true` returned `[]`).

The fix moves the service row and every dependent row (per-service settings, custom
configs, job cache) in the same `Database.save_config` transaction as the rest of
the PATCH. These tests exercise the real router through FastAPI's TestClient and
assert that nothing was dropped. They also cover: renaming to an existing name
(rejected, nothing changed), an invalid new name (422), and failures inside the
transaction rolling back cleanly (old service and its rows intact).
"""

import logging
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

REPO = Path(__file__).resolve().parents[2]

for path in (
    REPO / "src" / "api",
    REPO / "src" / "common" / "db",
    REPO / "src" / "common" / "utils",
    REPO / "src" / "common" / "api",
    REPO / "src" / "common" / "gen",
):
    sys.path.insert(0, str(path))

# The real app.auth.guard module loads a Biscuit keypair from /var/lib/bunkerweb at
# import time, which isn't available (or writable) outside the container. Stub it out
# so importing app.routers.services doesn't need a real keypair; the TestClient app
# below also overrides this dependency.
_guard_stub = types.ModuleType("app.auth.guard")
_guard_stub.guard = lambda: None
_original_guard_module = sys.modules.get("app.auth.guard")
_guard_stub_installed = _original_guard_module is None
sys.modules.setdefault("app.auth.guard", _guard_stub)

from Configurator import Configurator  # noqa: E402
from Database import Database  # noqa: E402
from model import Custom_configs, Jobs_cache, Metadata, Services, Services_settings  # noqa: E402

import app.routers.services as services_router  # noqa: E402

LOGGER = logging.getLogger("test_api_service_rename")
LOGGER.addHandler(logging.NullHandler())

SETTINGS_JSON = REPO / "src" / "common" / "settings.json"
CORE_DIR = REPO / "src" / "common" / "core"

CANARY_RULE = 'SecRule REQUEST_URI "@streq /f7-canary" "id:9910007,phase:1,deny,status:403,msg:\'f7 canary\'"'


class ApiServiceRenameTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bw-test-service-rename-")
        self.addCleanup(self._rmtree)
        self._original_get_db = services_router.get_db
        self.addCleanup(self._restore_router_get_db)

        db_path = os.path.join(self.tmpdir, "db.sqlite3")
        self.db = Database(LOGGER, sqlalchemy_string=f"sqlite:///{db_path}")

        configurator = Configurator(
            str(SETTINGS_JSON),
            str(CORE_DIR),
            [],
            [],
            {"SERVER_NAME": "", "MULTISITE": "yes"},
            LOGGER,
        )
        ret, err = self.db.init_tables([configurator.get_settings(), configurator.get_plugins("core"), [], []])
        self.assertFalse(err, err)
        self.assertTrue(ret)

        err = self.db.initialize_db(version="1.6.15", integration="Linux")
        self.assertFalse(err, err)

        # save_config only runs its per-service bookkeeping when MULTISITE=yes is
        # already stored (see Database.get_non_default_settings), matching how the
        # scheduler seeds a real deployment before the API ever touches a service.
        err = self.db.save_config({"MULTISITE": "yes"}, "manual", changed=False)
        self.assertNotIsInstance(err, str, err)

        # The router reads/writes through get_db(); point it at this test's own
        # temp-file database instead of the real singleton.
        services_router.get_db = lambda: self.db
        app = FastAPI()
        app.include_router(services_router.router)
        app.dependency_overrides[services_router.guard] = lambda: None
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def _restore_router_get_db(self):
        services_router.get_db = self._original_get_db

    @classmethod
    def tearDownClass(cls):
        if _guard_stub_installed:
            if _original_guard_module is None:
                sys.modules.pop("app.auth.guard", None)
            else:
                sys.modules["app.auth.guard"] = _original_guard_module

    def _rmtree(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_service(self, name: str, *, security_mode: str = "detect", is_draft: bool = False) -> None:
        conf = self.db.get_non_default_settings(methods=False, with_drafts=True)
        conf[f"{name}_IS_DRAFT"] = "yes" if is_draft else "no"
        conf[f"{name}_SERVER_NAME"] = name
        conf[f"{name}_SECURITY_MODE"] = security_mode
        existing = set((conf.get("SERVER_NAME", "") or "").split())
        conf["SERVER_NAME"] = " ".join(sorted(existing | {name}))
        ret = self.db.save_config(conf, "api", changed=True)
        self.assertNotIsInstance(ret, str, ret)

    def _add_custom_config(self, service_id: str, name: str, data: str) -> None:
        err = self.db.upsert_custom_config(
            "modsec",
            name,
            {"data": data, "type": "modsec", "name": name, "method": "api", "service_id": service_id},
            service_id=service_id,
        )
        self.assertEqual(err, "")

    def _add_job_cache(self, service_id: str, file_name: str, data: bytes, checksum: str) -> str:
        job_name = next(iter(self.db.get_jobs()))
        err = self.db.upsert_job_cache(service_id, file_name, data, job_name=job_name, checksum=checksum)
        self.assertEqual(err, "")
        return job_name

    def _service_ids(self) -> set:
        return {s["id"] for s in self.db.get_services(with_drafts=True)}

    def _snapshot(self, db=None) -> dict:
        db = db or self.db
        with db._db_session() as session:
            metadata = session.query(Metadata).get(1)
            return {
                "services": sorted(((row.id, row.method, row.is_draft) for row in session.query(Services).all()), key=repr),
                "settings": sorted(
                    [
                        (row.service_id, row.setting_id, row.suffix, row.value, row.file_name, row.method, row.is_draft)
                        for row in session.query(Services_settings).all()
                    ],
                    key=repr,
                ),
                "custom_configs": sorted(
                    [(row.service_id, row.type, row.name, row.data, row.checksum, row.method, row.is_draft) for row in session.query(Custom_configs).all()],
                    key=repr,
                ),
                "jobs_cache": sorted(
                    [(row.job_name, row.service_id, row.file_name, row.data, row.checksum, row.last_update) for row in session.query(Jobs_cache).all()],
                    key=repr,
                ),
                "metadata": tuple(getattr(metadata, column.name) for column in Metadata.__table__.columns) if metadata else None,
            }

    def _create_atomic_fixture(self, *, is_draft: bool = True) -> str:
        self._create_service("a.example.com", is_draft=is_draft)
        conf = self.db.get_non_default_settings(methods=False, with_drafts=True)
        conf["a.example.com_SERVER_NAME"] = "a.example.com alias.example.com"
        conf["a.example.com_USE_GZIP"] = "no"
        ret = self.db.save_config(conf, "api", changed=True)
        self.assertNotIsInstance(ret, str, ret)
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)
        return self._add_job_cache("a.example.com", "cache_file.txt", b"cached-bytes", "checksum-1")

    def _assert_unchanged(self, before: dict):
        fresh = Database(LOGGER, sqlalchemy_string=f"sqlite:///{os.path.join(self.tmpdir, 'db.sqlite3')}")
        self.assertEqual(self._snapshot(fresh), before)

    def _service_rows(self, snapshot: dict, service: str) -> dict:
        return {
            "services": [row for row in snapshot["services"] if row[0] == service],
            "settings": [row for row in snapshot["settings"] if row[0] == service],
            "custom_configs": [row for row in snapshot["custom_configs"] if row[0] == service],
            "jobs_cache": [row for row in snapshot["jobs_cache"] if row[1] == service],
        }

    # -- happy path -----------------------------------------------------------------

    def test_rename_moves_custom_config_job_cache_and_settings(self):
        self._create_service("a.example.com")
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)
        job_name = self._add_job_cache("a.example.com", "cache_file.txt", b"cached-bytes", "checksum-1")

        before = self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com")
        self.assertTrue(before.get("data"))
        before_checksum = before["checksum"]

        conf = self.db.get_non_default_settings(methods=False, with_drafts=True)
        conf["a.example.com_SERVER_NAME"] = "a.example.com alias.example.com"
        conf["a.example.com_USE_GZIP"] = "no"
        ret = self.db.save_config(conf, "api", changed=True)
        self.assertNotIsInstance(ret, str, ret)

        resp = self.client.patch(
            "/services/a.example.com",
            json={"server_name": "b.example.com", "variables": {"USE_GZIP": "yes"}, "is_draft": True},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        ids = self._service_ids()
        self.assertNotIn("a.example.com", ids)
        self.assertIn("b.example.com", ids)

        # Old id: everything gone.
        self.assertEqual(self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com"), {})
        self.assertIsNone(self.db.get_job_cache_file(job_name, "cache_file.txt", service_id="a.example.com"))

        # New id: custom config carried its data/checksum, job cache carried its data,
        # per-service setting kept its method.
        after = self.db.get_custom_config("modsec", "deny_rule", service_id="b.example.com")
        self.assertEqual(after["checksum"], before_checksum)
        self.assertEqual(after["data"], CANARY_RULE.encode("utf-8"))

        self.assertEqual(self.db.get_job_cache_file(job_name, "cache_file.txt", service_id="b.example.com"), b"cached-bytes")

        conf_b = self.db.get_config(methods=True, with_drafts=True, service="b.example.com")
        self.assertEqual(conf_b["SECURITY_MODE"]["value"], "detect")
        self.assertEqual(conf_b["SECURITY_MODE"]["method"], "api")
        self.assertEqual(conf_b["USE_GZIP"]["value"], "yes")
        self.assertTrue({s["id"]: s["is_draft"] for s in self.db.get_services(with_drafts=True)}["b.example.com"])

        # The per-service SERVER_NAME value (what nginx's server_name directive is
        # built from) must follow the rename too, or the old hostname keeps being
        # served even though the service id/custom configs/job cache all moved.
        self.assertEqual(conf_b["SERVER_NAME"]["value"], "b.example.com alias.example.com")
        with self.db._db_session() as session:
            self.assertTrue(session.query(Metadata).get(1).custom_configs_changed)

    def test_rename_preserves_draft_flag(self):
        self._create_service("draft.example.com", is_draft=True)

        resp = self.client.patch("/services/draft.example.com", json={"server_name": "draft2.example.com"})
        self.assertEqual(resp.status_code, 200, resp.text)

        drafts = {s["id"]: s["is_draft"] for s in self.db.get_services(with_drafts=True)}
        self.assertIn("draft2.example.com", drafts)
        self.assertTrue(drafts["draft2.example.com"])

    def test_rename_rolls_back_when_row_move_raises_after_parent_update(self):
        self._create_atomic_fixture()
        before = self._snapshot()
        original = self.db._rename_service_rows

        def fail_after_parent_update(session, old_name, new_name):
            service = session.query(Services).get(old_name)
            service.id = new_name
            session.flush()
            raise RuntimeError("simulated row move failure")

        self.db._rename_service_rows = fail_after_parent_update
        try:
            response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})
        finally:
            self.db._rename_service_rows = original

        self.assertEqual(response.status_code, 500, response.text)
        self._assert_unchanged(before)

    def test_rename_rolls_back_when_settings_pass_raises(self):
        self._create_atomic_fixture()
        before = self._snapshot()
        original = self.db._session_factory.add_all

        def fail_add_all(_objects):
            raise RuntimeError("simulated settings pass failure")

        self.db._session_factory.add_all = fail_add_all
        try:
            response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})
        finally:
            del self.db._session_factory.add_all

        self.assertEqual(self.db._session_factory.add_all, original)
        self.assertEqual(response.status_code, 500, response.text)
        self._assert_unchanged(before)

    def test_rename_rolls_back_when_commit_raises(self):
        self._create_atomic_fixture()
        before = self._snapshot()

        def fail_commit():
            raise RuntimeError("simulated commit failure")

        original = self.db._session_factory.commit
        self.db._session_factory.commit = fail_commit
        try:
            response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})
        finally:
            del self.db._session_factory.commit

        self.assertEqual(self.db._session_factory.commit, original)
        self.assertEqual(response.status_code, 500, response.text)
        self._assert_unchanged(before)

    def test_same_name_update_still_applies_variables(self):
        self._create_service("a.example.com")

        response = self.client.patch("/services/a.example.com", json={"server_name": "a.example.com", "variables": {"USE_GZIP": "yes"}})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._service_ids(), {"a.example.com"})
        self.assertEqual(self.db.get_config(methods=True, with_drafts=True, service="a.example.com")["USE_GZIP"]["value"], "yes")

    def test_invalid_variable_is_rejected_before_rename(self):
        self._create_atomic_fixture()
        before = self._snapshot()

        response = self.client.patch(
            "/services/a.example.com",
            json={"server_name": "z.example.com", "variables": {"USE_GZIP": "not-a-boolean"}},
        )

        self.assertEqual(response.status_code, 422, response.text)
        self._assert_unchanged(before)

    def test_concurrent_target_collision_is_rejected_without_partial_state(self):
        self._create_atomic_fixture()
        before = self._snapshot()
        second = Database(LOGGER, sqlalchemy_string=f"sqlite:///{os.path.join(self.tmpdir, 'db.sqlite3')}")
        original = self.db._rename_service_rows

        def create_target_then_check(session, old_name, new_name):
            now = datetime.now().astimezone()
            with second._db_session() as other_session:
                other_session.add(Services(id=new_name, method="api", is_draft=False, creation_date=now, last_update=now))
                other_session.commit()
            return original(session, old_name, new_name)

        self.db._rename_service_rows = create_target_then_check
        try:
            response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})
        finally:
            self.db._rename_service_rows = original

        self.assertEqual(response.status_code, 400, response.text)
        concurrent_state = self._snapshot()
        self.assertNotEqual(before, concurrent_state)
        self.assertEqual(self._snapshot(), concurrent_state)

    def test_unrelated_service_rows_survive_a_rename(self):
        self._create_atomic_fixture()
        self._create_service("b.example.com")
        before = self._snapshot()

        response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self._service_rows(self._snapshot(), "b.example.com"), self._service_rows(before, "b.example.com"))

    def test_autoconf_owned_service_cannot_be_renamed_by_api(self):
        self._create_services_without_own_server_name("a.example.com", "b.example.com", method="autoconf")
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)
        before = self._snapshot()

        response = self.client.patch("/services/a.example.com", json={"server_name": "z.example.com"})

        self.assertEqual(response.status_code, 403, response.text)
        self._assert_unchanged(before)

    def test_save_config_retries_the_rename_after_a_conflict(self):
        self._create_atomic_fixture(is_draft=False)
        conf = self.db.get_non_default_settings(methods=False, with_drafts=True)
        rewritten = {}
        for key, value in conf.items():
            rewritten[f"z.example.com_{key[len('a.example.com_'):]}" if key.startswith("a.example.com_") else key] = value
        rewritten["SERVER_NAME"] = "z.example.com"
        rewritten["z.example.com_SERVER_NAME"] = "z.example.com alias.example.com"

        original = self.db._session_factory.commit
        calls = 0

        def fail_once():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise IntegrityError("simulated conflict", {}, RuntimeError("duplicate"))
            return original()

        self.db._session_factory.commit = fail_once
        try:
            result = self.db.save_config(rewritten, "api", changed=True, rename=("a.example.com", "z.example.com"))
        finally:
            del self.db._session_factory.commit

        self.assertEqual(self.db._session_factory.commit, original)
        self.assertNotIsInstance(result, str, result)
        self.assertEqual(calls, 2)
        self.assertEqual(self._service_ids(), {"z.example.com"})

    # -- validation -------------------------------------------------------------------

    def test_rename_to_existing_name_is_rejected_and_nothing_changes(self):
        self._create_service("a.example.com")
        self._create_service("c.example.com")
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)

        resp = self.client.patch("/services/a.example.com", json={"server_name": "c.example.com"})
        self.assertEqual(resp.status_code, 400, resp.text)

        ids = self._service_ids()
        self.assertIn("a.example.com", ids)
        self.assertIn("c.example.com", ids)
        self.assertTrue(self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com").get("data"))

    def test_rename_rejects_invalid_server_name(self):
        self._create_service("a.example.com")

        resp = self.client.patch("/services/a.example.com", json={"server_name": "Invalid.COM"})
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("a.example.com", self._service_ids())

    def test_rename_keeps_aliases_and_drops_the_old_hostname(self):
        self._create_service("app.example.com")
        conf = self.db.get_non_default_settings(methods=False, with_drafts=True)
        conf["app.example.com_SERVER_NAME"] = "app.example.com www.app.example.com alias.example.com"
        ret = self.db.save_config(conf, "api", changed=True)
        self.assertNotIsInstance(ret, str, ret)

        resp = self.client.patch("/services/app.example.com", json={"server_name": "new.example.com"})
        self.assertEqual(resp.status_code, 200, resp.text)

        tokens = self.db.get_config(methods=True, with_drafts=True, service="new.example.com")["SERVER_NAME"]["value"].split()
        self.assertEqual(tokens[0], "new.example.com")
        self.assertEqual(set(tokens), {"new.example.com", "www.app.example.com", "alias.example.com"})

    # -- services that do not own their SERVER_NAME row ------------------------------

    def _create_services_without_own_server_name(self, *names: str, method: str = "api") -> None:
        # An environment-style definition: the roster lives in the global SERVER_NAME
        # only, no per-service SERVER_NAME row exists (the snapshot then falls back to
        # the global roster for every service).
        conf = {"MULTISITE": "yes", "SERVER_NAME": " ".join(names)}
        # save_config only materialises a service that carries at least one setting.
        conf.update({f"{name}_USE_MODSECURITY": "no" for name in names})
        ret = self.db.save_config(conf, method, changed=True)
        self.assertNotIsInstance(ret, str, ret)
        self.assertEqual(self._service_ids(), set(names))

    def test_rename_without_own_server_name_row_does_not_claim_sibling_hostnames(self):
        self._create_services_without_own_server_name("a.example.com", "b.example.com")

        resp = self.client.patch("/services/a.example.com", json={"server_name": "new.example.com"})
        self.assertEqual(resp.status_code, 200, resp.text)

        self.assertEqual(self._service_ids(), {"new.example.com", "b.example.com"})
        conf_new = self.db.get_config(methods=True, with_drafts=True, service="new.example.com")
        self.assertEqual(conf_new["SERVER_NAME"]["value"], "new.example.com")
        conf_b = self.db.get_config(methods=True, with_drafts=True, service="b.example.com")
        self.assertNotIn("new.example.com", conf_b["SERVER_NAME"]["value"].split())

    def test_rename_of_service_defined_outside_the_api_is_refused(self):
        self._create_services_without_own_server_name("a.example.com", "b.example.com", method="scheduler")
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)

        resp = self.client.patch("/services/a.example.com", json={"server_name": "new.example.com"})
        self.assertEqual(resp.status_code, 403, resp.text)

        self.assertEqual(self._service_ids(), {"a.example.com", "b.example.com"})
        self.assertTrue(self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com").get("data"))

        # What the scheduler does on its next pass with the unchanged environment:
        # nothing must be removed because the rename never happened.
        ret = self.db.save_config(
            {"MULTISITE": "yes", "SERVER_NAME": "a.example.com b.example.com", "a.example.com_USE_MODSECURITY": "no", "b.example.com_USE_MODSECURITY": "no"},
            "scheduler",
            changed=True,
        )
        self.assertNotIsInstance(ret, str, ret)
        self.assertTrue(self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com").get("data"))

    # -- rollback safety --------------------------------------------------------------

    def test_dependent_row_move_failure_leaves_old_service_intact(self):
        self._create_service("a.example.com")
        self._add_custom_config("a.example.com", "deny_rule", CANARY_RULE)
        job_name = self._add_job_cache("a.example.com", "cache_file.txt", b"cached-bytes", "checksum-1")

        def fail_commit():
            raise RuntimeError("simulated commit failure")

        # Patch the scoped_session's commit for this call only: it shadows the
        # proxied Session.commit, so rename_service's flush()+bulk updates still run
        # against the real connection but the transaction never completes -- the
        # except block's rollback() must undo them.
        original = self.db._session_factory.commit
        self.db._session_factory.commit = fail_commit
        try:
            err = self.db.rename_service("a.example.com", "z.example.com")
        finally:
            del self.db._session_factory.commit
        self.assertEqual(self.db._session_factory.commit, original)

        self.assertIn("simulated commit failure", err)

        ids = self._service_ids()
        self.assertIn("a.example.com", ids)
        self.assertNotIn("z.example.com", ids)
        self.assertEqual(
            self.db.get_custom_config("modsec", "deny_rule", service_id="a.example.com").get("data"),
            CANARY_RULE.encode("utf-8"),
        )
        self.assertEqual(self.db.get_job_cache_file(job_name, "cache_file.txt", service_id="a.example.com"), b"cached-bytes")

        # The database must still be usable afterwards (the patch was cleanly undone).
        err = self.db.rename_service("a.example.com", "z.example.com")
        self.assertEqual(err, "")
        self.assertIn("z.example.com", self._service_ids())


if __name__ == "__main__":
    unittest.main()
