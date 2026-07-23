"""Regression tests for the multiple-group default-sibling lock bug.

A multisite "multiple" group (e.g. reverse-proxy #1) has members the user never sets. The scheduler
config round-trip (db.get_config materialises every group member at its default -> variables.env ->
save_config(method="scheduler")) must NOT persist those default-valued siblings as Services_settings
rows: a persisted non-ui/api/default method row renders the field disabled in the Web UI even though
the value is an untouched default.

Covers both directions:
- a fresh default sibling is not persisted (is_default_value recognises the plugin default);
- a pre-existing corrupted scheduler row holding a default value self-heals (is removed) on the next
  scheduler save.
"""

from copy import deepcopy
from json import loads
from pathlib import Path
from sys import path as sys_path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra_path in (REPO_ROOT / "src" / "common" / "db", REPO_ROOT / "src" / "common" / "utils"):
    _extra_path_str = str(_extra_path)
    if _extra_path_str not in sys_path:
        sys_path.insert(0, _extra_path_str)

from Database import Database  # type: ignore  # noqa: E402
from model import Services_settings, Global_values, Templates, Template_steps, Template_settings  # type: ignore  # noqa: E402

SERVICE = "app.example.com"


def _multiple_setting(setting_id: str, default: str, group: str = "test-rp", context: str = "multisite") -> dict:
    return {
        "context": context,
        "default": default,
        "help": setting_id,
        "id": setting_id.lower().replace("_", "-"),
        "label": setting_id,
        "regex": "^.*$",
        "type": "text",
        "multiple": group,
    }


def _test_plugin() -> dict:
    return {
        "id": "testrp",
        "name": "Test RP",
        "description": "Multiple groups for testing",
        "version": "1.0",
        "stream": "no",
        "type": "core",
        "method": "manual",
        "settings": {
            # Anchored group: HOST has an empty default, so a real slot must set it (non-default anchor).
            "TEST_RP_HOST": _multiple_setting("TEST_RP_HOST", ""),  # user-set, non-default
            "TEST_RP_TIMEOUT": _multiple_setting("TEST_RP_TIMEOUT", "60s"),  # untouched default sibling
            # Anchorless group (limit-req shape): BOTH members have non-empty defaults, so an all-default
            # slot is a valid user-declared configuration that must NOT vanish.
            "TEST_LIM_URL": _multiple_setting("TEST_LIM_URL", "/", "test-lim"),
            "TEST_LIM_RATE": _multiple_setting("TEST_LIM_RATE", "2r/s", "test-lim"),
            # GLOBAL multi-member group (access-logs shape) — same anchored-sibling / anchorless logic
            # applies to global settings via process_global_settings.
            "TEST_GLOG_FILE": _multiple_setting("TEST_GLOG_FILE", "/log", "test-glog", "global"),
            "TEST_GLOG_FMT": _multiple_setting("TEST_GLOG_FMT", "combined", "test-glog", "global"),
        },
    }


class DefaultMultipleSiblingLockTest(TestCase):
    def setUp(self):
        self.tmpdir = TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.sqlite3"
        self.logger = SimpleNamespace(info=lambda *_a: None, warning=lambda *_a: None, error=lambda *_a: None, debug=lambda *_a: None)
        self.db = Database(self.logger, sqlalchemy_string=f"sqlite:///{db_path}")
        general = loads((REPO_ROOT / "src" / "common" / "settings.json").read_text())
        ret, err = self.db.init_tables([general, deepcopy(_test_plugin())])
        self.assertFalse(err, err)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def _rows(self, setting_id: str, suffix: int):
        with self.db._db_session() as session:
            return session.query(Services_settings).filter_by(service_id=SERVICE, setting_id=setting_id, suffix=suffix).all()

    def _grows(self, setting_id: str, suffix: int):
        with self.db._db_session() as session:
            return session.query(Global_values).filter_by(setting_id=setting_id, suffix=suffix).all()

    def _mk_template(self, *settings):
        # settings: iterable of (setting_id, default, suffix)
        from datetime import datetime

        now = datetime.now().astimezone()
        with self.db._db_session() as session:
            session.add(Templates(id="tmpl", name="Tmpl", plugin_id=None, method="manual", creation_date=now, last_update=now))
            session.flush()
            session.add(Template_steps(id=1, template_id="tmpl", title="Step", subtitle=None))
            for order, (sid, default, suffix) in enumerate(settings, 1):
                session.add(Template_settings(template_id="tmpl", setting_id=sid, step_id=1, default=default, suffix=suffix, order=order))
            session.commit()

    def _use_template(self, extra=None):
        # A service that uses the template, round-tripped through get_config -> save_config.
        init = {"SERVER_NAME": SERVICE, "MULTISITE": "yes", f"{SERVICE}_SERVER_NAME": SERVICE, f"{SERVICE}_USE_TEMPLATE": "tmpl"}
        if extra:
            init.update(extra)
        self.assertNotIsInstance(self.db.save_config(init, "scheduler", changed=False), str)
        self.assertNotIsInstance(self.db.save_config(self.db.get_config(methods=False), "scheduler", changed=False), str)

    def _seeded(self, **extra):
        # Build a save_config dict the way real callers do: bare defaults seeded via get_config, then
        # the explicit overrides. Needed so is_default_value takes its realistic (non-clean) branch.
        cfg = self.db.get_config(methods=False)
        cfg.update({"SERVER_NAME": SERVICE, "MULTISITE": "yes", f"{SERVICE}_SERVER_NAME": SERVICE})
        cfg.update(extra)
        return cfg

    def _establish_service(self):
        # A multisite service with a user-provided _1 group member (HOST_1). This creates the suffix-1
        # row that later makes get_config materialise the whole group's siblings.
        initial = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_RP_HOST_1": "http://custom:8080",
        }
        err = self.db.save_config(initial, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        self.assertEqual(len(self._rows("TEST_RP_HOST", 1)), 1)

    def test_default_sibling_not_persisted_as_scheduler_row(self):
        self._establish_service()

        # Emulate the scheduler round-trip: get_config materialises TEST_RP_TIMEOUT_1=60s, then
        # save_config(method="scheduler") re-ingests the full default-filled config.
        full = self.db.get_config(methods=False)
        self.assertEqual(full.get(f"{SERVICE}_TEST_RP_TIMEOUT_1"), "60s")
        err = self.db.save_config(full, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)

        # The untouched default sibling must NOT get a persisted row (else it renders disabled in the UI).
        self.assertEqual(self._rows("TEST_RP_TIMEOUT", 1), [])
        # The user-set member is untouched.
        self.assertEqual(len(self._rows("TEST_RP_HOST", 1)), 1)

    def test_stale_default_sibling_row_self_heals(self):
        self._establish_service()

        # Simulate an already-corrupted lock: a scheduler row holding the plugin default value.
        with self.db._db_session() as session:
            session.add(Services_settings(service_id=SERVICE, setting_id="TEST_RP_TIMEOUT", value="60s", suffix=1, method="scheduler"))
            session.commit()
        self.assertEqual(len(self._rows("TEST_RP_TIMEOUT", 1)), 1)

        full = self.db.get_config(methods=False)
        err = self.db.save_config(full, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)

        # The redundant default row is removed on the next scheduler save -> the field becomes editable.
        self.assertEqual(self._rows("TEST_RP_TIMEOUT", 1), [])

    def test_non_default_sibling_is_preserved(self):
        # Regression guard: the self-heal must NEVER delete a sibling whose value differs from the
        # plugin default. Set TIMEOUT_1=30s (default is 60s) and confirm it survives round-trips.
        self._establish_service()
        with self.db._db_session() as session:
            session.add(Services_settings(service_id=SERVICE, setting_id="TEST_RP_TIMEOUT", value="30s", suffix=1, method="scheduler"))
            session.commit()

        for _ in range(2):
            full = self.db.get_config(methods=False)
            err = self.db.save_config(full, "scheduler", changed=False)
            self.assertNotIsInstance(err, str, err)

        rows = self._rows("TEST_RP_TIMEOUT", 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, "30s")

    def test_round_trip_is_idempotent(self):
        # After the first self-heal, further scheduler round-trips must make NO further changes
        # (no re-creation of default rows, no delete churn) -> no reload loop.
        self._establish_service()
        counts = []
        for _ in range(3):
            full = self.db.get_config(methods=False)
            err = self.db.save_config(full, "scheduler", changed=False)
            self.assertNotIsInstance(err, str, err)
            with self.db._db_session() as session:
                counts.append(session.query(Services_settings).filter_by(service_id=SERVICE).filter(Services_settings.suffix == 1).count())
        # Only the HOST_1 anchor persists; the default TIMEOUT_1 sibling never accumulates -> stable.
        self.assertEqual(counts, [1, 1, 1])

    def test_ui_method_default_sibling_also_self_heals(self):
        # The bug (and the fix) apply to UI/API saves too, not just scheduler: a ui-method default
        # sibling row is likewise cleaned when compatible with the save method.
        self._establish_service()
        with self.db._db_session() as session:
            session.add(Services_settings(service_id=SERVICE, setting_id="TEST_RP_TIMEOUT", value="60s", suffix=1, method="ui"))
            session.commit()
        self.assertEqual(len(self._rows("TEST_RP_TIMEOUT", 1)), 1)

        # A ui save carrying the default value self-heals the redundant ui row.
        edit = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_RP_HOST_1": "http://custom:8080",
            f"{SERVICE}_TEST_RP_TIMEOUT_1": "60s",
        }
        err = self.db.save_config(edit, "ui", changed=False)
        self.assertNotIsInstance(err, str, err)
        self.assertEqual(self._rows("TEST_RP_TIMEOUT", 1), [])
        # The user-set HOST_1 (ui) is untouched.
        self.assertEqual(len(self._rows("TEST_RP_HOST", 1)), 1)

    def test_anchorless_all_default_slot_is_preserved(self):
        # THE key regression guard: for an anchorless group (limit-req shape), a slot whose members are
        # ALL at their defaults is a valid user-declared config and must survive every round-trip. If it
        # vanished, a rate-limit rule (or similar) declared at default values would be silently dropped.
        # Build the config the way real callers (Configurator / get_config) do: bare defaults seeded for
        # every setting, plus the explicit service-prefixed slot values.
        initial = self.db.get_config(methods=False)
        initial["SERVER_NAME"] = SERVICE
        initial["MULTISITE"] = "yes"
        initial[f"{SERVICE}_SERVER_NAME"] = SERVICE
        initial[f"{SERVICE}_TEST_LIM_URL_1"] = "/"  # equals plugin default
        initial[f"{SERVICE}_TEST_LIM_RATE_1"] = "2r/s"  # equals plugin default
        err = self.db.save_config(initial, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        self.assertEqual(len(self._rows("TEST_LIM_URL", 1)), 1)
        self.assertEqual(len(self._rows("TEST_LIM_RATE", 1)), 1)

        for _ in range(2):
            full = self.db.get_config(methods=False)
            err = self.db.save_config(full, "scheduler", changed=False)
            self.assertNotIsInstance(err, str, err)

        # Slot still present after repeated round-trips -> did NOT vanish.
        self.assertEqual(len(self._rows("TEST_LIM_URL", 1)), 1)
        self.assertEqual(len(self._rows("TEST_LIM_RATE", 1)), 1)

    def test_anchored_slot_keeps_anchor_drops_only_default_member(self):
        # A slot with a non-default anchor (URL=/api) keeps the anchor and drops just the default sibling
        # (RATE=2r/s), so the anchor renders and the default field stays editable.
        initial = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_LIM_URL_1": "/api",  # non-default anchor
            f"{SERVICE}_TEST_LIM_RATE_1": "2r/s",  # default sibling of an anchored slot
        }
        err = self.db.save_config(initial, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        full = self.db.get_config(methods=False)
        err = self.db.save_config(full, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)

        rows = self._rows("TEST_LIM_URL", 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, "/api")
        self.assertEqual(self._rows("TEST_LIM_RATE", 1), [])

    def test_bare_save_anchorless_slot_does_not_vanish(self):
        # C1: a bare save that submits ONLY service-prefixed keys (no unprefixed base default) must still
        # persist an all-default anchorless slot. Previously is_default_value's clean branch skipped it → vanish.
        bare = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_LIM_URL_1": "/",  # default value, bare save (no base key seeded)
            f"{SERVICE}_TEST_LIM_RATE_1": "2r/s",
        }
        err = self.db.save_config(bare, "ui", changed=False)
        self.assertNotIsInstance(err, str, err)
        self.assertEqual(len(self._rows("TEST_LIM_URL", 1)), 1)
        self.assertEqual(len(self._rows("TEST_LIM_RATE", 1)), 1)

    def test_global_anchored_slot_drops_default_sibling(self):
        # A global multiple slot with a non-default anchor keeps the anchor and drops its default sibling,
        # so the sibling stays editable on the global settings page (not locked as method=scheduler).
        cfg = self._seeded(TEST_GLOG_FILE_1="/custom", TEST_GLOG_FMT_1="combined")
        err = self.db.save_config(cfg, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        cfg = self._seeded(TEST_GLOG_FILE_1="/custom", TEST_GLOG_FMT_1="combined")
        err = self.db.save_config(cfg, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)

        anchor = self._grows("TEST_GLOG_FILE", 1)
        self.assertEqual(len(anchor), 1)
        self.assertEqual(anchor[0].value, "/custom")
        self.assertEqual(self._grows("TEST_GLOG_FMT", 1), [])  # default sibling dropped -> editable

    def test_edit_anchored_slot_down_to_all_default_does_not_vanish(self):
        # D1: an EXISTING anchored slot edited down to all-default values must not vanish. The delete-to-default
        # branch would otherwise drop the last rows; the slot must persist at its default values instead.
        create = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_LIM_URL_1": "/api",
            f"{SERVICE}_TEST_LIM_RATE_1": "10r/s",
        }
        self.assertNotIsInstance(self.db.save_config(create, "ui", changed=False), str)
        self.assertEqual(len(self._rows("TEST_LIM_URL", 1)), 1)
        self.assertEqual(len(self._rows("TEST_LIM_RATE", 1)), 1)

        # Edit both members down to their plugin defaults (bare save -> delete-to-default path).
        edit = {
            "SERVER_NAME": SERVICE,
            "MULTISITE": "yes",
            f"{SERVICE}_SERVER_NAME": SERVICE,
            f"{SERVICE}_TEST_LIM_URL_1": "/",
            f"{SERVICE}_TEST_LIM_RATE_1": "2r/s",
        }
        self.assertNotIsInstance(self.db.save_config(edit, "ui", changed=False), str)
        url = self._rows("TEST_LIM_URL", 1)
        rate = self._rows("TEST_LIM_RATE", 1)
        self.assertEqual(len(url), 1)
        self.assertEqual(url[0].value, "/")
        self.assertEqual(len(rate), 1)
        self.assertEqual(rate[0].value, "2r/s")

    def test_non_multisite_anchorless_slot_does_not_vanish(self):
        # The non-multisite (MULTISITE=no) save path is a separate branch; it must also persist an
        # all-default anchorless slot instead of skipping every member (which vanished the slot).
        cfg = self.db.get_config(methods=False)
        cfg.update({"SERVER_NAME": SERVICE, "MULTISITE": "no", "TEST_LIM_URL_1": "/", "TEST_LIM_RATE_1": "2r/s"})
        err = self.db.save_config(cfg, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        with self.db._db_session() as session:
            self.assertEqual(session.query(Global_values).filter_by(setting_id="TEST_LIM_URL", suffix=1).count(), 1)
            self.assertEqual(session.query(Global_values).filter_by(setting_id="TEST_LIM_RATE", suffix=1).count(), 1)

    def test_non_multisite_anchored_slot_keeps_anchor_skips_default(self):
        # Non-multisite anchored slot: the non-default anchor persists; the default sibling is skipped
        # (stays editable). No lock, no vanish.
        cfg = self.db.get_config(methods=False)
        cfg.update({"SERVER_NAME": SERVICE, "MULTISITE": "no", "TEST_LIM_URL_1": "/api", "TEST_LIM_RATE_1": "2r/s"})
        err = self.db.save_config(cfg, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        with self.db._db_session() as session:
            self.assertEqual(session.query(Global_values).filter_by(setting_id="TEST_LIM_URL", suffix=1).count(), 1)
            self.assertEqual(session.query(Global_values).filter_by(setting_id="TEST_LIM_RATE", suffix=1).count(), 0)

    def test_template_defined_slot_not_persisted(self):
        # A template that defines a full multiple slot keeps it alive without rows; the round-trip must NOT
        # persist its members (they would become spurious, field-locking rows).
        self._mk_template(("TEST_RP_HOST", "tmplhost", 1), ("TEST_RP_TIMEOUT", "60s", 1))
        self._use_template()
        self.assertEqual(self._rows("TEST_RP_HOST", 1), [])
        self.assertEqual(self._rows("TEST_RP_TIMEOUT", 1), [])

    def test_template_partial_slot_not_persisted(self):
        # Template defines only HOST_1; its sibling TIMEOUT_1's slot is kept alive by that HOST_1, so
        # TIMEOUT_1 must also NOT be persisted.
        self._mk_template(("TEST_RP_HOST", "tmplhost", 1))
        self._use_template()
        self.assertEqual(self._rows("TEST_RP_HOST", 1), [])
        self.assertEqual(self._rows("TEST_RP_TIMEOUT", 1), [])

    def test_template_slot_user_override_persists(self):
        # A user override of a template slot member (non-default) is persisted; the template-default member is
        # not. The round-trip (get_config -> save_config) also verifies global settings survive process_global_settings.
        self._mk_template(("TEST_RP_HOST", "tmplhost", 1))
        self._use_template({f"{SERVICE}_TEST_RP_TIMEOUT_1": "30s"})
        self.assertEqual(self._rows("TEST_RP_HOST", 1), [])
        rows = self._rows("TEST_RP_TIMEOUT", 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].value, "30s")

    def test_global_anchorless_slot_bare_save_does_not_vanish(self):
        # A global all-default anchorless slot declared via a BARE save (no unprefixed base default) must
        # persist. Previously is_default_value's clean branch skipped it → the slot vanished.
        bare = {"SERVER_NAME": SERVICE, "MULTISITE": "yes", f"{SERVICE}_SERVER_NAME": SERVICE, "TEST_GLOG_FMT_1": "combined"}
        err = self.db.save_config(bare, "scheduler", changed=False)
        self.assertNotIsInstance(err, str, err)
        self.assertEqual(len(self._grows("TEST_GLOG_FMT", 1)), 1)
