#!/usr/bin/env python3

from os import getenv
from pathlib import Path
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from sys import path as sys_path
from threading import Event, Thread
from time import monotonic
from unittest.mock import patch
import unittest

ROOT = Path(__file__).resolve().parents[2]
# AUTOCONF_SRC points the test at another copy of src/autoconf (used to run it against the unfixed code).
for rel in (getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    sys_path.insert(0, str(rel if rel.startswith("/") else ROOT / rel))

from kubernetes.client import Configuration  # type: ignore  # noqa: E402
from urllib3.exceptions import HTTPError  # type: ignore  # noqa: E402
import Config as config_module  # type: ignore  # noqa: E402
import controllers.KubernetesController as kc_module  # type: ignore  # noqa: E402


class SilentPeer:
    """Accepts TCP connections and never answers: the shape of a connection the network dropped without a RST."""

    def __init__(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.conns = []
        self.stopped = Event()
        Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self.stopped.is_set():
            try:
                self.conns.append(self.sock.accept()[0])
            except OSError:
                return

    def close(self):
        self.stopped.set()
        self.sock.close()
        for conn in self.conns:
            conn.close()


def fake_config_init(self, *args, **kwargs):
    self._type = "kubernetes"
    self._supported_config_types = ()


class TestKubernetesRequestTimeout(unittest.TestCase):
    def setUp(self):
        self.peer = SilentPeer()
        self.addCleanup(self.peer.close)
        self.saved_default = Configuration._default

        def load_incluster_config():
            cfg = Configuration()
            cfg.host = f"http://127.0.0.1:{self.peer.port}"
            Configuration.set_default(cfg)

        self.addCleanup(Configuration.set_default, self.saved_default)
        # Tiny timeouts keep the fixed run fast; create=True lets the same test run against code without the constant.
        for p in (
            patch.object(config_module.Config, "__init__", fake_config_init),
            patch("controllers.KubernetesController.config.load_incluster_config", load_incluster_config),
            patch.object(kc_module, "API_REQUEST_TIMEOUT", (1, 1), create=True),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.ctrl = kc_module.KubernetesController()

    def run_locked(self, call, deadline):
        """API call made the way _watch makes it: with _internal_lock held. Returns (finished, error, elapsed)."""
        result = {}

        def work():
            with self.ctrl._internal_lock:
                try:
                    call()
                except Exception as e:  # noqa: BLE001
                    result["error"] = e

        started = monotonic()
        thread = Thread(target=work, daemon=True)
        thread.start()
        thread.join(deadline)
        return not thread.is_alive(), result.get("error"), monotonic() - started

    def test_apply_path_calls_on_silent_peer_release_the_lock(self):
        for name, call in (("get_instances", self.ctrl._get_controller_instances), ("get_configs", self.ctrl.get_configs)):
            with self.subTest(call=name):
                finished, error, elapsed = self.run_locked(call, deadline=12)
                self.assertTrue(finished, f"{name} is still blocked after 12s on a peer that never answers (hung)")
                self.assertIsInstance(error, HTTPError, f"expected a urllib3 timeout error, got {error!r}")
                self.assertTrue(self.ctrl._internal_lock.acquire(timeout=1), "lock still held after the call returned")
                self.ctrl._internal_lock.release()

    def test_watch_stream_is_not_cut_by_the_request_timeout(self):
        """A stream that has been quiet for longer than the request timeout must stay open (keepalive bounds it instead)."""
        errors = []

        def work():
            try:
                for _ in kc_module.watch.Watch().stream(self.ctrl._corev1.list_pod_for_all_namespaces):
                    pass
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        thread = Thread(target=work, daemon=True)
        thread.start()
        thread.join(3)
        self.assertEqual(errors, [])
        self.assertTrue(thread.is_alive(), "watch stream ended on an idle but healthy connection")

    def test_client_sockets_get_keepalive_and_user_timeout(self):
        from socket import IPPROTO_TCP, SO_KEEPALIVE, TCP_USER_TIMEOUT

        options = self.ctrl._corev1.api_client.rest_client.pool_manager.connection_pool_kw.get("socket_options")
        self.assertIsNotNone(options)
        self.assertIn((SOL_SOCKET, SO_KEEPALIVE, 1), options)
        self.assertIn((IPPROTO_TCP, TCP_USER_TIMEOUT, 60000), options)


if __name__ == "__main__":
    unittest.main()
