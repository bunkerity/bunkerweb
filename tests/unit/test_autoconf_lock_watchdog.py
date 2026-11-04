#!/usr/bin/env python3

from os import getenv
from pathlib import Path
from sys import path as sys_path
from tempfile import TemporaryDirectory
from time import sleep
from unittest.mock import MagicMock, patch
import unittest

ROOT = Path(__file__).resolve().parents[2]
# AUTOCONF_SRC points the test at another copy of src/autoconf (used to run it against the unfixed code).
for rel in (getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(rel if rel.startswith("/") else ROOT / rel))

from kubernetes.client import Configuration  # type: ignore  # noqa: E402
import Config as config_module  # type: ignore  # noqa: E402
import controllers.KubernetesController as kc_module  # type: ignore  # noqa: E402


def fake_config_init(self, *args, **kwargs):
    self._type = "kubernetes"
    self._supported_config_types = ()


class TestLockWatchdog(unittest.TestCase):
    def setUp(self):
        self.addCleanup(Configuration.set_default, Configuration._default)
        for p in (
            patch.object(config_module.Config, "__init__", fake_config_init),
            patch("controllers.KubernetesController.config.load_incluster_config", lambda: Configuration.set_default(Configuration())),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ctrl = kc_module.KubernetesController()
        self.ctrl._logger = MagicMock()
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / "autoconf.healthy"
        self.marker.write_text("ok")

    def test_lock_held_past_the_limit_removes_the_marker(self):
        with self.ctrl._internal_lock:
            sleep(0.2)
            self.assertTrue(self.ctrl._check_lock_hold(self.marker, max_hold=0.1))
        self.assertFalse(self.marker.exists())
        self.ctrl._logger.error.assert_called_once()

    def test_normal_hold_keeps_the_marker(self):
        with self.ctrl._internal_lock:
            self.assertFalse(self.ctrl._check_lock_hold(self.marker, max_hold=60))
        self.assertTrue(self.marker.exists())

    def test_released_lock_keeps_the_marker(self):
        with self.ctrl._internal_lock:
            sleep(0.2)
        self.assertFalse(self.ctrl._check_lock_hold(self.marker, max_hold=0.1))
        self.assertTrue(self.marker.exists())

    def test_watch_sites_still_work_with_acquire_release(self):
        lock = self.ctrl._internal_lock
        self.assertTrue(lock.acquire())
        self.assertFalse(lock.acquire(timeout=0.05))
        lock.release()
        self.assertTrue(lock.acquire(timeout=0.5))
        lock.release()


if __name__ == "__main__":
    unittest.main()
