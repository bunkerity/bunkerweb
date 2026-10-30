#!/usr/bin/env python3

from logging import getLogger
from os import environ, getenv
from pathlib import Path
from sys import path as sys_path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
for rel in (getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(rel if rel.startswith("/") else ROOT / rel))

from kubernetes.client import ApiClient, Configuration
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from controllers.KubernetesController import KubernetesController


class TestSlowApplyWatchdog(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.marker = Path(tmp.name) / "autoconf.healthy"
        self.marker.write_text("ok")
        self.now = 100.0
        clock = patch("controllers.Controller.monotonic", lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.addCleanup(Configuration.set_default, Configuration._default)
        with patch.dict(environ, {"DATABASE_URI": f"sqlite:///{tmp.name}/db.sqlite3", "DATABASE_URI_READONLY": ""}), patch(
            "controllers.KubernetesController.config.load_incluster_config", lambda: Configuration.set_default(Configuration())
        ):
            self.ctrl = KubernetesController()
        self.ctrl._logger = getLogger("watchdog-test")
        self.addCleanup(self.ctrl._db.sql_engine.dispose)
        # The same check runs against the old source, which has no runtime configuration yet.
        configure = getattr(self.ctrl, "_configure_lock_watchdog", None)
        if configure:
            configure()
            self.addCleanup(event.remove, Engine, "after_cursor_execute", self.ctrl._database_progress)

    def test_hold_above_old_limit_within_runtime_budget_stays_healthy(self):
        with self.ctrl._internal_lock:
            self.now += 601
            self.assertFalse(self.ctrl._check_lock_hold(self.marker))
        self.assertTrue(self.marker.exists())

    def test_stalled_hold_above_runtime_budget_is_unhealthy(self):
        with self.ctrl._internal_lock:
            self.now += getattr(self.ctrl, "_lock_max_hold", 600) + 1
            self.assertTrue(self.ctrl._check_lock_hold(self.marker))
        self.assertFalse(self.marker.exists())

    def test_long_apply_with_completed_sql_keeps_making_progress(self):
        with self.ctrl._internal_lock:
            for _ in range(20):
                self.now += 300
                with self.ctrl._db.sql_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self.assertFalse(self.ctrl._check_lock_hold(self.marker))
            self.now += getattr(self.ctrl, "_lock_max_hold", 600) + 1
            self.assertTrue(self.ctrl._check_lock_hold(self.marker))

    def test_sibling_sql_cannot_hide_stuck_holder(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        self.addCleanup(engine.dispose)
        with self.ctrl._internal_lock:
            self.now += getattr(self.ctrl, "_lock_max_hold", 600) + 1

            def sibling():
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

            thread = Thread(target=sibling)
            thread.start()
            thread.join()
            self.assertTrue(self.ctrl._check_lock_hold(self.marker))

    def test_save_config_worker_sql_counts_as_progress(self):
        with self.ctrl._internal_lock:
            for _ in range(20):
                self.now += 300

                def worker():
                    with self.ctrl._db.sql_engine.connect() as conn:
                        conn.execute(text("SELECT 1"))

                thread = Thread(target=worker)
                thread.start()
                thread.join()
                self.assertFalse(self.ctrl._check_lock_hold(self.marker))

    def test_completed_api_request_is_holder_progress(self):
        with self.ctrl._internal_lock, patch.object(ApiClient, "call_api", return_value=object()):
            for _ in range(20):
                self.now += 300
                self.ctrl._corev1.api_client.call_api("/api/v1/pods", "GET")
                self.assertFalse(self.ctrl._check_lock_hold(self.marker))

    def test_sibling_api_cannot_hide_stuck_holder(self):
        with self.ctrl._internal_lock, patch.object(ApiClient, "call_api", return_value=object()):
            self.now += getattr(self.ctrl, "_lock_max_hold", 600) + 1
            thread = Thread(target=lambda: self.ctrl._corev1.api_client.call_api("/api/v1/pods", "GET"))
            thread.start()
            thread.join()
            self.assertTrue(self.ctrl._check_lock_hold(self.marker))

    def test_budget_uses_validated_db_timeout_overrides(self):
        self.ctrl._db._connect_timeout = 20
        self.ctrl._db._read_timeout = 1200
        configure = getattr(self.ctrl, "_configure_lock_watchdog", None)
        if configure:
            configure()
        with self.ctrl._internal_lock:
            self.now += 6000
            self.assertFalse(self.ctrl._check_lock_hold(self.marker))

    def test_readonly_uri_timeouts_and_retries_extend_the_budget(self):
        self.ctrl._db.database_uri_readonly = "mysql+pymysql://u:p@db/bw?connect_timeout=20&read_timeout=1800&write_timeout=2400"
        self.ctrl._db._request_retry_attempts = 3
        self.ctrl._db._request_retry_delay = 10
        configure = getattr(self.ctrl, "_configure_lock_watchdog", None)
        if configure:
            configure()
        with self.ctrl._internal_lock:
            self.now += 50000
            self.assertFalse(self.ctrl._check_lock_hold(self.marker))

    def test_replacement_engine_sql_counts_as_progress(self):
        replacement = create_engine("sqlite://")
        self.addCleanup(replacement.dispose)
        self.ctrl._db.sql_engine = replacement
        with self.ctrl._internal_lock:
            for _ in range(20):
                self.now += 300
                with replacement.connect() as conn:
                    conn.execute(text("SELECT 1"))
                self.assertFalse(self.ctrl._check_lock_hold(self.marker))


if __name__ == "__main__":
    main(verbosity=2)
