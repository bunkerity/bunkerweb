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
        self.elapsed = 0
        clock = patch.object(check.time, "monotonic", side_effect=lambda: self.elapsed)
        clock.start()
        self.addCleanup(clock.stop)
        sleeper = patch.object(check.time, "sleep", side_effect=self.advance)
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def advance(self, seconds):
        self.elapsed += seconds

    def write_rows(self):
        (check.ROOT / "sockets.jsonl").write_text("".join(json.dumps(row) + "\n" for row in self.rows))

    def append_after_sleep(self, text):
        def append(seconds):
            self.advance(seconds)
            with (check.ROOT / "sockets.jsonl").open("a") as output:
                output.write(text)

        self.sleep.side_effect = append

    def run_gate(self, since=15):
        self.write_rows()
        check.sockets(since)

    def test_post_reload_samples_arrive_later(self):
        later = [dict(row) for row in self.rows]
        for row in self.rows:
            row["time"] = 10
        self.append_after_sleep("".join(json.dumps(row) + "\n" for row in later))
        self.run_gate()
        self.sleep.assert_called_once()

    def test_same_command_recovery_arrives_later(self):
        self.rows.append(sample(timestamp=30, code=137, out=""))
        self.append_after_sleep(json.dumps(sample(timestamp=40)) + "\n")
        self.run_gate()
        self.sleep.assert_called_once()

    def test_partial_final_line_completes_later(self):
        self.rows.append(sample(timestamp=30, code=137, out=""))
        self.write_rows()
        recovery = json.dumps(sample(timestamp=40)) + "\n"
        with (check.ROOT / "sockets.jsonl").open("a") as output:
            output.write(recovery[:20])
        self.append_after_sleep(recovery[20:])
        check.sockets(15)
        self.sleep.assert_called_once()

    def test_permanent_failure_waits_until_deadline(self):
        self.rows.append(sample(timestamp=30, code=137, out=""))
        self.write_rows()
        with self.assertRaisesRegex(AssertionError, "CAPTURE_FAILED"):
            check.sockets(15, timeout=2)
        self.assertEqual(self.elapsed, 2)

    def test_missing_post_reload_sample_waits_until_deadline(self):
        for row in self.rows:
            row["time"] = 10
        self.write_rows()
        with self.assertRaisesRegex(AssertionError, "NO_POST_RELOAD_SAMPLE"):
            check.sockets(15, timeout=2)
        self.assertEqual(self.elapsed, 2)

    def test_complete_malformed_line_fails_immediately(self):
        self.write_rows()
        with (check.ROOT / "sockets.jsonl").open("a") as output:
            output.write('{"container":\n')
        with self.assertRaises(json.JSONDecodeError):
            check.sockets(15)
        self.sleep.assert_not_called()

    def test_ipv4_violations_fail_immediately_while_samples_pending(self):
        violations = (
            (COMMANDS[2], '[{"addr_info": [{"family": "inet", "local": "192.0.2.1"}]}]', "IPv4Address"),
            (COMMANDS[3], '[{"dst": "default"}]', "default"),
            (COMMANDS[0], sample(command=COMMANDS[0])["out"] + "tcp ESTAB 0 0 127.0.0.1:80 192.0.2.1:123\n", "NON_LOOPBACK_IPV4_SOCKET"),
            (COMMANDS[0], sample(command=COMMANDS[0])["out"] + "tcp LISTEN 0 0 0.0.0.0:8080 0.0.0.0:*\n", "STRICT_LOOPBACK_ONLY_SOCKET_GATE"),
        )
        for command, out, diagnostic in violations:
            with self.subTest(command=command, diagnostic=diagnostic):
                self.rows = [sample(container, cmd, timestamp=10) for container in check.CONTAINERS for cmd in COMMANDS]
                self.rows.append(sample(container=check.CONTAINERS[-1], command=command, out=out))
                with self.assertRaisesRegex(AssertionError, diagnostic):
                    self.run_gate()
                self.sleep.assert_not_called()

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

    def ss4(self, line, container="bw-scheduler"):
        self.rows.append(sample(container=container, command=COMMANDS[0], out=sample(command=COMMANDS[0])["out"] + line + "\n"))

    def test_scheduler_resolver_ephemeral_udp_socket_is_tolerated(self):
        # CI sample: musl binds an unconnected AF_INET UDP socket on 0.0.0.0 for each lookup, even without IPv4.
        self.ss4("udp   UNCONN 0      0            0.0.0.0:38543      0.0.0.0:*          ")
        self.run_gate()
        self.assertIn("bw-scheduler: udp   UNCONN", (check.ROOT / "ipv4-wildcard-listeners.json").read_text())

    def test_narrow_resolver_allowance_does_not_hide_real_listeners(self):
        cases = (
            ("fixed UDP port", "udp   UNCONN 0      0            0.0.0.0:5353       0.0.0.0:*", "bw-scheduler"),
            ("privileged UDP port", "udp   UNCONN 0      0            0.0.0.0:443        0.0.0.0:*", "bw-scheduler"),
            ("ephemeral TCP listener", "tcp   LISTEN 0      4096         0.0.0.0:38543      0.0.0.0:*", "bw-scheduler"),
            ("connected UDP", "udp   ESTAB  0      0            0.0.0.0:38543      0.0.0.0:*", "bw-scheduler"),
            ("other container", "udp   UNCONN 0      0            0.0.0.0:38543      0.0.0.0:*", "redis"),
        )
        for label, line, container in cases:
            with self.subTest(label):
                self.rows = [sample(name, command) for name in check.CONTAINERS for command in COMMANDS]
                self.ss4(line, container)
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
