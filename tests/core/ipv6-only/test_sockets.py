#!/usr/bin/env python3
"""Exercise the real socket gate with capture rows, without Docker."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("ipv6_only_check", Path(__file__).with_name("check.py"))
assert spec and spec.loader
check = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, BW_TESTS_IPV6_ONLY_DIR="."):
    spec.loader.exec_module(check)

COMMANDS = (["ss", "-4", "-a", "-t", "-u", "-n", "-p"], ["ss", "-6", "-a", "-t", "-u", "-n", "-p"], ["ip", "-j", "addr"], ["ip", "-j", "-4", "route"])
RESTART_ERRORS = (
    (128, "FailedPrecondition: container abc init process is not running: failed precondition", ""),
    (137, "", ""),
    (128, "OCI runtime exec failed: exec failed: cannot exec in a stopped container", ""),
)


def sample(container="bw-scheduler", command=COMMANDS[1], timestamp=20, code=0, out=None, err=""):
    if out is None:
        out = "Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port\n" if command[0] == "ss" else "[]"
    return dict(time=timestamp, container=container, pid="123", command=command, code=code, out=out, err=err)


class SocketGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = patch.object(check, "ROOT", Path(self.directory.name))
        root.start()
        self.addCleanup(root.stop)
        self.rows = [sample(container, command) for container in check.CONTAINERS for command in COMMANDS]

    def run_gate(self, since=15):
        (check.ROOT / "sockets.jsonl").write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        check.sockets(since)

    def test_healthy_samples(self):
        self.run_gate()

    def test_restart_signatures_recover(self):
        for code, out, err in RESTART_ERRORS:
            with self.subTest(code=code, out=out):
                self.rows.insert(0, sample(timestamp=10, code=code, out=out, err=err))
                try:
                    self.run_gate()
                finally:
                    self.rows.pop(0)

    def test_all_samples_fail(self):
        self.rows = [{**row, "code": 127, "out": "", "err": "ss: not found"} for row in self.rows]
        with self.assertRaisesRegex(AssertionError, "NO_SOCKET_SAMPLES"):
            self.run_gate()

    def test_command_keeps_failing(self):
        for row in self.rows:
            if row["container"] == "bw-scheduler" and row["command"] == COMMANDS[2]:
                row.update(code=127, out="", err="ip: not found")
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            self.run_gate()

    def test_permission_error_without_later_success(self):
        self.rows.append(sample(timestamp=30, code=1, out="", err="permission denied"))
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            self.run_gate()

    def test_restart_without_later_success(self):
        self.rows.append(sample(timestamp=30, code=128, out="container is not running"))
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            self.run_gate()

    def test_other_command_success_does_not_mask_failure(self):
        self.rows.extend([sample(timestamp=30, code=137, out=""), sample(command=COMMANDS[0], timestamp=40)])
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            self.run_gate()

    def test_other_container_success_does_not_mask_failure(self):
        self.rows.extend([sample(timestamp=30, code=137, out=""), sample(container="redis", timestamp=40)])
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            self.run_gate()

    def test_ipv4_address_before_recovery_still_fails(self):
        address = json.dumps([{"addr_info": [{"family": "inet", "local": "192.0.2.1"}]}])
        self.rows.insert(0, sample(command=COMMANDS[2], timestamp=5, out=address))
        self.rows.insert(1, sample(command=COMMANDS[2], timestamp=10, code=137, out=""))
        with self.assertRaisesRegex(AssertionError, "IPv4Address"):
            self.run_gate()

    def test_ipv4_route_still_fails(self):
        self.rows.append(sample(command=COMMANDS[3], out='[{"dst": "default"}]'))
        with self.assertRaises(AssertionError):
            self.run_gate()

    def test_ipv4_peer_still_fails(self):
        self.rows.append(sample(command=COMMANDS[0], out=sample(command=COMMANDS[0])["out"] + "tcp ESTAB 0 0 127.0.0.1:80 192.0.2.1:123\n"))
        with self.assertRaisesRegex(AssertionError, "NON_LOOPBACK_IPV4_SOCKET"):
            self.run_gate()

    def test_unexpected_ipv4_wildcard_still_fails(self):
        self.rows.append(sample(command=COMMANDS[0], out=sample(command=COMMANDS[0])["out"] + "tcp LISTEN 0 0 0.0.0.0:8080 0.0.0.0:*\n"))
        with self.assertRaisesRegex(AssertionError, "STRICT_LOOPBACK_ONLY_SOCKET_GATE"):
            self.run_gate()

    def test_both_families_need_post_reload_samples(self):
        for command in COMMANDS[:2]:
            with self.subTest(family=command[1]):
                for row in self.rows:
                    row["time"] = 10 if row["command"] == command else 20
                with self.assertRaisesRegex(AssertionError, "NO_POST_RELOAD_SAMPLE"):
                    self.run_gate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
