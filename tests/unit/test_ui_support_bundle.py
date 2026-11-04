"""Tests for the Web UI support bundle (src/ui/app/support_bundle.py and the /support/ui_bundle route)."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from io import BytesIO
from logging import Formatter, LogRecord
from os import symlink
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src/ui"), str(REPO_ROOT / "src/common/utils"), str(REPO_ROOT / "src/common/db")]

from app.support_bundle import (  # noqa: E402
    ERROR_BLOCK_LINES,
    Anonymizer,
    RingBufferHandler,
    build_environment,
    build_plugins_report,
    build_support_bundle,
    cut_text,
    error_blocks,
    log_sources,
    read_log_tail,
)

DOMAINS = ("secret.example.org", "other.test")
NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def record(msg):
    return LogRecord("UI", 20, __file__, 1, msg, None, None)


def bundle_files(data):
    with ZipFile(BytesIO(data)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in archive.namelist()}


def make_bundle(**overrides):
    kwargs = dict(
        domains=DOMAINS,
        environ={},
        integration="Docker",
        ring={"pid": 1, "started": "now", "records": []},
        plugins={"plugins": []},
        environment={},
        now=NOW,
    )
    kwargs.update(overrides)
    return bundle_files(build_support_bundle(**kwargs))


class RedactionTest(unittest.TestCase):
    def setUp(self):
        self.anonymizer = Anonymizer(DOMAINS)

    def assertGone(self, text, *secrets):
        out = self.anonymizer.redact(text)
        for secret in secrets:
            self.assertNotIn(secret, out, f"{secret!r} survived in {out!r}")
        return out

    def test_service_domains(self):
        out = self.assertGone("GET https://www.secret.example.org/x and other.test", "secret.example.org", "other.test")
        self.assertIn("[ANONYMIZED_DOMAIN]", out)
        self.assertEqual(self.anonymizer.redact("notsecret.example.org.evil"), "notsecret.example.org.evil")

    def test_no_domains_does_not_match_everything(self):
        self.assertEqual(Anonymizer().redact("plain text"), "plain text")

    def test_ipv4(self):
        out = self.assertGone("client 203.0.113.7:8080 via 10.0.0.1", "203.0.113.7", "10.0.0.1")
        self.assertIn("[ANONYMIZED_IPv4]:8080", out)
        self.assertEqual(self.anonymizer.redact("version 1.6.16 and 1.2.3.4.5"), "version 1.6.16 and 1.2.3.4.5")

    def test_ipv6_forms(self):
        for address in (
            "2001:0db8:0000:0000:0000:ff00:0042:8329",
            "2001:db8::ff00:42:8329",
            "::1",
            "::ffff:192.0.2.128",
            "fe80::1%eth0",
            "fe80::a:b%wlan0",
        ):
            with self.subTest(address=address):
                out = self.anonymizer.redact(f"peer {address} closed")
                self.assertEqual(out, "peer [ANONYMIZED_IPv6] closed")
        self.assertEqual(self.anonymizer.redact("peer [2001:db8::1]:443."), "peer [[ANONYMIZED_IPv6]]:443.")
        self.assertEqual(self.anonymizer.redact("from 2001:db8::1."), "from [ANONYMIZED_IPv6].")

    def test_non_addresses_are_kept(self):
        line = "[2026-10-05 12:34:56 +0000] [UI] [12] [INFO] - took 12:30:45"
        self.assertEqual(self.anonymizer.redact(line), line)

    def test_uri_userinfo(self):
        out = self.assertGone("db mysql+pymysql://bunkerweb:S3cretPw@db:3306/bw ready", "S3cretPw", "bunkerweb:")
        self.assertIn("mysql+pymysql://[REDACTED]@db:3306/bw", out)
        self.assertGone("redis://:onlypass@cache:6379", "onlypass")
        self.assertEqual(self.anonymizer.redact("see http://host/path@thing"), "see http://host/path@thing")

    def test_authorization_forms(self):
        self.assertGone("Authorization: Bearer abc123.def-456", "abc123")
        self.assertGone("authorization=Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpw")
        self.assertGone("Authorization: Token tok_live_9999", "tok_live_9999")
        self.assertGone("sent Bearer eyJhbGciOi.payload.sig now", "eyJhbGciOi")
        self.assertGone("sent Basic dXNlcjpwYXNzd29yZA== now", "dXNlcjpw")
        self.assertEqual(self.anonymizer.redact("a basic setup"), "a basic setup")
        self.assertGone('{"Authorization": "Bearer jsonbearer"}', "jsonbearer")

    def test_cookies(self):
        self.assertGone("Cookie: session=abc; theme=dark; csrf_token=zzz", "abc", "zzz", "dark")
        self.assertGone("Set-Cookie: bw_session=value123; Path=/; HttpOnly", "value123")
        self.assertGone('{"cookie": "a=b; c=d"}', "a=b")

    def test_key_value_and_query_params(self):
        for key in ("token", "api_key", "SECRET", "password", "passwd", "session_id", "csrf", "access-token", "x_key"):
            with self.subTest(key=key):
                self.assertGone(f"call {key}=hunter2 done", "hunter2")
                self.assertGone(f"GET /x?a=1&{key}=hunter2&b=2 HTTP/1.1", "hunter2")
                self.assertGone(f"{key}: hunter2", "hunter2")
                self.assertGone(f'{key}="hunter2 spaced"', "hunter2", "spaced")
        self.assertEqual(self.anonymizer.redact("GET /x?a=1&b=2"), "GET /x?a=1&b=2")

    def test_json_pairs(self):
        for key in ("token", "api_key", "secret", "password", "passwd", "session", "csrf_token"):
            with self.subTest(key=key):
                self.assertGone(f'{{"{key}": "p@ss w0rd", "ok": 1}}', "p@ss", "w0rd")
                self.assertGone(f"{{'{key}': 'hunter2'}}", "hunter2")
                self.assertGone(f'{{"{key}": 12345}}', "12345")
        self.assertEqual(json.loads(self.anonymizer.redact('{"token": "abc", "ok": 1}'))["ok"], 1)

    def test_authorization_values_are_redacted_whole(self):
        self.assertGone(
            'Authorization: Digest username="digestuser", realm="r", nonce="digestnonce1", uri="/x?a=1&b=2", response="digestresp2"',
            "digestuser",
            "digestnonce1",
            "digestresp2",
        )
        self.assertGone("Authorization: Negotiate YIIabcnegotiate9", "YIIabcnegotiate9")
        self.assertGone("Proxy-Authorization: Custom-Scheme customsecret99", "customsecret99")
        self.assertGone("Authorization: AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/2026, SignedHeaders=host, Signature=sigsecret77", "AKIAEXAMPLE", "sigsecret77")
        self.assertGone("authorization=Bearer bearersecret&a=1", "bearersecret")
        self.assertEqual(self.anonymizer.redact("Authorization: Bearer abcd1234 done"), "Authorization: [REDACTED] [REDACTED] done")

    def test_percent_encoded_query_keys(self):
        for key in ("%74oken", "%2574oken", "api%5Fkey", "pass%77ord", "%53ECRET", "access%2Dtoken"):
            with self.subTest(key=key):
                out = self.assertGone(f"GET /x?a=1&{key}=percent-key-secret&b=2 HTTP/1.1", "percent-key-secret")
                self.assertIn("&b=2", out)
        self.assertEqual(self.anonymizer.redact("GET /x?a%20b=1&c=2"), "GET /x?a%20b=1&c=2")

    def test_structured_secret_values(self):
        self.assertGone('token: ["list-secret"]', "list-secret")
        self.assertGone("secret=['a1secret', 'b2secret']", "a1secret", "b2secret")
        self.assertGone('token: ["a]b-secret", "c-secret"] after', "a]b-secret", "c-secret")
        self.assertGone('password = ("t1secret", "t2secret")', "t1secret", "t2secret")
        self.assertGone('{"token": {"k": "nested-secret", "m": ["deep-secret"]}}', "nested-secret", "deep-secret")
        self.assertGone('token: [\n  "multi1-secret",\n  "multi2-secret"\n]', "multi1-secret", "multi2-secret")
        self.assertGone('token: ["unterminated-secret", "more-secret"', "unterminated-secret", "more-secret")
        out = self.assertGone('{"password": ["p1secret", "p2secret"], "ok": 1}', "p1secret", "p2secret")
        self.assertEqual(json.loads(out)["ok"], 1)
        self.assertEqual(self.anonymizer.redact("items: [1, 2] size={}"), "items: [1, 2] size={}")

    def test_idempotent(self):
        once = self.anonymizer.redact("token=abc Authorization: Bearer xyz1234 mysql://u:p@h/d 10.0.0.1")
        self.assertEqual(self.anonymizer.redact(once), once)


class CutTest(unittest.TestCase):
    def ring(self, text, **kwargs):
        handler = RingBufferHandler(**kwargs)
        handler.setFormatter(Formatter("%(message)s"))
        handler.emit(record(text))
        return handler, handler.snapshot()["records"]

    def assertCutLeaksNothing(self, pads, template, secret):
        cuts = 0
        for pad in pads:
            _, records = self.ring("x" * pad + template)
            if not records[0].endswith("[truncated]"):
                continue
            cuts += 1
            for size in range(3, len(secret) + 1):
                if secret[:size] in records[0]:
                    self.fail(f"pad={pad}: secret prefix {secret[:size]!r} survived the cut")
        self.assertGreater(cuts, 5)

    def test_record_cut_across_uri_password(self):
        self.assertCutLeaksNothing(range(4070, 4110), " mysql://bw:SecretPassw0rd@db/bw", "SecretPassw0rd")

    def test_record_cut_across_bearer_token(self):
        self.assertCutLeaksNothing(range(4050, 4100), " Authorization: Bearer abcdefghijklmnopqrstuvwxyz", "abcdefghijklmnopqrstuvwxyz")
        self.assertCutLeaksNothing(range(4060, 4100), " Bearer abcdefghijklmnopqrstuvwxyz", "abcdefghijklmnopqrstuvwxyz")

    def test_record_cut_across_token_value(self):
        self.assertCutLeaksNothing(range(4070, 4110), " token=s3cr3tvalue123", "s3cr3tvalue123")

    def test_record_cut_keeps_utf8_valid(self):
        _, records = self.ring("é" * 3000)
        self.assertLessEqual(len(records[0].encode()), 4096 + len(" [truncated]"))

    def test_ring_byte_bounds_and_eviction(self):
        handler = RingBufferHandler(record_cap=50, total_cap=200)
        handler.setFormatter(Formatter("%(message)s"))
        for index in range(30):
            handler.emit(record(f"record-{index:02d} " + "y" * (index * 5)))
        snapshot = handler.snapshot()
        self.assertLessEqual(snapshot["bytes"], 200)
        self.assertEqual(snapshot["bytes"], sum(len(item.encode()) for item in snapshot["records"]))
        self.assertGreater(snapshot["records_evicted"], 0)
        self.assertGreater(snapshot["records_cut"], 0)
        self.assertEqual(len(snapshot["records"]) + snapshot["records_evicted"], 30)
        self.assertTrue(snapshot["records"][-1].startswith("record-29"))

    def test_cut_text(self):
        self.assertEqual(cut_text("abc", 3), ("abc", False))
        self.assertEqual(cut_text("abcd", 3), ("abc [truncated]", True))

    def test_file_tail_start_drops_partial_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            head = "[2026-10-05 10:00:00 +0000] [UI] [1] [❌] - connect mysql://bw:SecretPassw0rd@db/bw failed\n"
            tail = "[2026-10-05 10:00:01 +0000] [UI] [1] [ℹ️ ] - next line\n"
            path.write_text(head + tail, encoding="utf-8")
            for offset in range(head.index("bw:Secret"), head.index("failed")):
                cap = len((head + tail).encode()) - len(head[:offset].encode())
                text, _ = read_log_tail(path.as_posix(), cap)
                self.assertEqual(text, tail, offset)

    def test_file_tail_on_line_boundary_keeps_first_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            path.write_text("one\ntwo\nthree\n", encoding="utf-8")
            text, size = read_log_tail(path.as_posix(), len("two\nthree\n"))
            self.assertEqual((text, size), ("two\nthree\n", 14))
            self.assertEqual(read_log_tail(path.as_posix(), 100)[0], "one\ntwo\nthree\n")

    def test_file_tail_cut_in_bundle_leaks_no_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            head = "[2026-10-05 10:00:00 +0000] [UI] [1] [INFO] - Authorization: Bearer abcdefghijklmnopqrstuvwxyz and token=tokenvalue99\n"
            tail = "[2026-10-05 10:00:01 +0000] [UI] [1] [INFO] - next\n"
            path.write_text(head + tail, encoding="utf-8")
            for secret_at in (head.index("abcdefghij"), head.index("tokenvalue99")):
                for delta in range(0, 8):
                    cap = len(tail.encode()) + len(head.encode()) - (secret_at + delta)
                    files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": path.as_posix()}, file_cap=cap)
                    log = files["logs/ui.log"]
                    for fragment in ("klmnop", "pqrstuv", "wxyz", "kenvalue99", "value99", "e99"):
                        self.assertNotIn(fragment, log)

    def test_planted_secrets_never_reach_any_zip_member(self):
        secrets = (
            "digestuser",
            "digestnonce1",
            "digestresp2",
            "negosecret3",
            "percent-key-secret",
            "list-secret",
            "b2secret",
            "deep-secret",
        )
        lines = (
            '[2026-10-05 10:00:00 +0000] [UI] [1] [ERROR] - Authorization: Digest username="digestuser", nonce="digestnonce1", response="digestresp2"',
            "[2026-10-05 10:00:01 +0000] [UI] [1] [ERROR] - Authorization: Negotiate negosecret3",
            "[2026-10-05 10:00:02 +0000] [UI] [1] [ERROR] - GET /x?a=1&%74oken=percent-key-secret HTTP/1.1",
            "[2026-10-05 10:00:03 +0000] [UI] [1] [ERROR] - token: [\"list-secret\"] secret=['a1', 'b2secret']",
            '[2026-10-05 10:00:04 +0000] [UI] [1] [ERROR] - {"session": {"meta": {"k": ["deep-secret"]}}}',
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            files = make_bundle(
                environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": path.as_posix()},
                ring={"pid": 1, "started": "now", "records": list(lines)},
                plugins={"plugins": []},
            )
        self.assertIn("logs/ui.log", files)
        self.assertIn("logs/ui-recent.log", files)
        self.assertIn("errors.txt", files)
        for name, content in files.items():
            for secret in secrets:
                self.assertNotIn(secret, content, f"{secret!r} survived in {name}")

    def assertCasesGone(self, prefix, cases):
        """Each case goes through build_support_bundle as a file log record and a ring buffer record; no ZIP member may hold a secret."""
        for name, (text, secrets, kept) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                record = prefix + text
                path = Path(tmp, "ui.log")
                path.write_text(record + "\n", encoding="utf-8")
                files = make_bundle(
                    environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": path.as_posix()},
                    ring={"pid": 1, "started": "now", "records": [record]},
                )
                self.assertIn("logs/ui.log", files)
                self.assertIn("logs/ui-recent.log", files)
                for member, content in files.items():
                    for secret in secrets:
                        self.assertNotIn(secret, content, f"{secret!r} survived in {member}")
                if kept:
                    self.assertIn(kept, files["logs/ui.log"])

    def test_multiline_and_spaced_secrets_never_reach_any_zip_member(self):
        prefix = "[2026-10-05 10:00:00 +0000] [UI] [1] [ERROR] - "
        cases = {
            "digest with spaces": (
                'Authorization: Digest username = "digestuser", nonce = "digestnonce1" , response = "digestresp2"',
                ("digestuser", "digestnonce1", "digestresp2"),
                "",
            ),
            "json list on the next line": ('{"token":\n  ["jsonlist1", "jsonlist2"], "ok": 1}', ("jsonlist1", "jsonlist2"), '"ok": 1'),
            "json scalar on the next line": ('{"token":\n  "jsonscalar3", "ok": 1}', ("jsonscalar3",), '"ok": 1'),
            "json mapping on the next line": ('{"password":\n  {"inner": "jsonmap4"}, "ok": 1}', ("jsonmap4",), '"ok": 1'),
            "yaml block list": ("token:\n  - yamlitem1\n  - yamlitem2\nother: kept-one", ("yamlitem1", "yamlitem2"), "other: kept-one"),
            "yaml list at key indent": ("token:\n- yamlflat5\n- yamlflat6\nother: kept-two", ("yamlflat5", "yamlflat6"), "other: kept-two"),
            "yaml nested mapping": (
                "secret:\n  inner: yamlnested3\n  deeper:\n    k: yamlnested4\nother: kept-three",
                ("yamlnested3", "yamlnested4"),
                "other: kept-three",
            ),
            "indented yaml key": ("config:\n  token:\n    - yamldeep7\n  name: kept-four", ("yamldeep7",), "name: kept-four"),
            "encoded key with a list": ('GET /x?a=1&%74oken=["encsecret1", "encsecret2"]&b=2 HTTP/1.1', ("encsecret1", "encsecret2"), "&b=2 HTTP/1.1"),
            "double encoded key with a mapping": ('GET /x?%2574oken={"k": "encsecret3"}&b=2', ("encsecret3",), "&b=2"),
        }
        self.assertCasesGone(prefix, cases)

    def test_digest_parameter_spacing_never_reaches_any_zip_member(self):
        prefix = "[2026-10-05 10:00:00 +0000] [UI] [1] [ERROR] - "
        cases = {
            "space after the equal sign": (
                'Authorization: Digest username="digestuser", nonce= "digestnonce1", response="digestresp2"',
                ("digestuser", "digestnonce1", "digestresp2"),
                "",
            ),
            "space before the equal sign": (
                'Authorization: Digest username ="digestuser", nonce =digestnonce1, response ="digestresp2"',
                ("digestuser", "digestnonce1", "digestresp2"),
                "",
            ),
            "spaces on both sides, unquoted": (
                "Authorization: Digest username= digestuser, nonce = digestnonce1, response=  digestresp2 status=200",
                ("digestuser", "digestnonce1", "digestresp2"),
                "status=200",
            ),
            "padding equal signs": (
                'Authorization: Digest username="digestuser", nonce= "digestnonce1==", cnonce =digestcn2==, response= digestresp2=',
                ("digestuser", "digestnonce1", "digestcn2", "digestresp2"),
                "",
            ),
        }
        self.assertCasesGone(prefix, cases)

    def test_yaml_block_scalars_never_reach_any_zip_member(self):
        prefix = "[2026-10-05 10:00:00 +0000] [UI] [1] [ERROR] - "
        cases = {}
        for marker in ("|", "|-", "|+", ">", ">-", ">+", "|2", ">2-", "|+1", "| # note"):
            cases[f"token {marker}"] = (
                f"token: {marker}\n  blocksecret1\n  blocksecret2\nother: kept-one",
                ("blocksecret1", "blocksecret2"),
                "other: kept-one",
            )
        cases["password folded"] = ("password: >-\n  foldedsecret1\n  foldedsecret2\nother: kept-two", ("foldedsecret1", "foldedsecret2"), "other: kept-two")
        cases["blank line inside the block"] = (
            "config:\n  password: |\n    blanksecret1\n\n    blanksecret2\n  name: kept-three",
            ("blanksecret1", "blanksecret2"),
            "name: kept-three",
        )
        cases["quoted key"] = ('"token": |\n  quotedsecret1\nother: kept-four', ("quotedsecret1",), "other: kept-four")
        cases["authorization key"] = ("authorization: |\n  authsecret1\n  authsecret2\nother: kept-five", ("authsecret1", "authsecret2"), "other: kept-five")
        cases["cookie key"] = ("cookie: >-\n  cookiesecret1\nother: kept-six", ("cookiesecret1",), "other: kept-six")
        self.assertCasesGone(prefix, cases)

    def test_error_block_cut(self):
        lines = ["[2026-10-05 10:00:00 +0000] [UI] [1] [❌] - boom token=firstsecret"]
        lines += [f"  frame {n}" for n in range(1, 300)]
        lines[ERROR_BLOCK_LINES - 1] = "  frame password=edgesecret"
        lines[ERROR_BLOCK_LINES] = "  frame Bearer droppedbearer123"
        text = Anonymizer().redact("\n".join(lines) + "\n[2026-10-05 10:00:01 +0000] [UI] [1] [INFO] - fine\n")
        blocks, cut = error_blocks(text)
        self.assertEqual((len(blocks), cut), (1, 1))
        self.assertEqual(len(blocks[0]), ERROR_BLOCK_LINES + 1)
        self.assertEqual(blocks[0][-1], "[truncated]")
        joined = "\n".join(blocks[0])
        for secret in ("firstsecret", "edgesecret", "droppedbearer123"):
            self.assertNotIn(secret, joined)

    def test_error_blocks_boundaries(self):
        text = "\n".join(
            [
                "[2026-10-05 10:00:00 +0000] [UI] [1] [INFO] - fine",
                "[2026-10-05 10:00:01 +0000] [UI] [1] [❌] - one",
                "Traceback (most recent call last):",
                "  File x",
                "[2026-10-05 10:00:02 +0000] [UI] [1] [⚠️ ] - warn",
                "  stray continuation",
                "Traceback (most recent call last):",
                "ValueError: bare",
            ]
        )
        blocks, cut = error_blocks(text)
        self.assertEqual([block[0][-3:] for block in blocks], ["one", "t):"])
        self.assertEqual(cut, 0)

    def test_bundle_keeps_last_20_blocks_and_dedups(self):
        lines = [f"[2026-10-05 10:{n:02d}:00 +0000] [UI] [1] [❌] - failure {n}" for n in range(30)]
        files = make_bundle(ring={"pid": 1, "started": "now", "records": lines + lines})
        errors = files["errors.txt"]
        self.assertEqual(errors.count("failure"), 20)
        self.assertIn("failure 29", errors)
        self.assertNotIn("failure 9\n", errors)
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["error_blocks"], {"found": 30, "kept": 20, "cut_at_line_cap": 0})


class LogSourcesTest(unittest.TestCase):
    def paths(self, environ, integration):
        return {source["path"]: source["writers"] for source in log_sources(environ, integration)}

    def test_stderr_only_has_no_file(self):
        self.assertEqual(log_sources({}, "Docker"), [])
        self.assertEqual(log_sources({"LOG_TYPES": "stderr syslog"}, "Linux"), [])

    def test_container_capture_output_defaults(self):
        paths = self.paths({"CAPTURE_OUTPUT": "yes"}, "Docker")
        self.assertEqual(
            set(paths),
            {
                "/var/log/bunkerweb/ui.log",
                "/var/log/bunkerweb/ui-access.log",
                "/var/log/bunkerweb/tmp-ui.log",
                "/var/log/bunkerweb/tmp-ui-access.log",
            },
        )
        self.assertEqual(paths["/var/log/bunkerweb/ui.log"], ["main UI error log"])
        self.assertEqual(paths["/var/log/bunkerweb/tmp-ui.log"], ["temporary UI error log"])

    def test_container_log_file_path_is_not_shared_with_the_temporary_ui(self):
        paths = self.paths({"LOG_TYPES": "stderr file", "LOG_FILE_PATH": "/data/log/ui.log"}, "Docker")
        self.assertIn("/data/log/ui.log", paths)
        self.assertIn("/data/log/ui-access.log", paths)
        self.assertEqual(paths["/data/log/ui.log"], ["main UI error log", "main UI app logger"])
        # The temporary UI loses LOG_FILE_PATH, so file logging stays off for it and it writes to stderr
        self.assertEqual(set(paths), {"/data/log/ui.log", "/data/log/ui-access.log"})

    def test_linux_shares_the_files_and_deduplicates(self):
        paths = self.paths({"LOG_TYPES": "file", "LOG_FILE_PATH": "/var/log/bunkerweb/ui.log"}, "Linux")
        self.assertEqual(set(paths), {"/var/log/bunkerweb/ui.log", "/var/log/bunkerweb/ui-access.log"})
        self.assertEqual(
            paths["/var/log/bunkerweb/ui.log"],
            ["main UI error log", "main UI app logger", "temporary UI error log", "temporary UI app logger"],
        )
        self.assertEqual(paths["/var/log/bunkerweb/ui-access.log"], ["main UI access log", "temporary UI access log"])

    def test_linux_without_log_file_path_keeps_separate_defaults(self):
        paths = self.paths({"CAPTURE_OUTPUT": "yes"}, "Linux")
        self.assertIn("/var/log/bunkerweb/ui.log", paths)
        self.assertIn("/var/log/bunkerweb/tmp-ui.log", paths)

    def test_file_type_with_invalid_path_is_not_a_file_source(self):
        self.assertEqual(log_sources({"LOG_TYPES": "file", "LOG_FILE_PATH": "/var/log/../etc/x.log"}, "Linux"), [])
        self.assertEqual(log_sources({"LOG_TYPES": "file"}, "Docker"), [])

    def test_traversal_path_is_rejected_when_reading(self):
        files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": "/var/log/../etc/passwd"})
        statuses = {item["path"]: item["status"] for item in json.loads(files["manifest.json"])["log_sources"]}
        self.assertTrue(statuses["/var/log/../etc/passwd"].startswith("skipped"))
        self.assertFalse(any(name.startswith("logs/") and name != "logs/ui-recent.log" for name in files))

    def test_stream_symlink_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp, "ui.log")
            symlink("/dev/null", link)
            files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": link.as_posix()})
            statuses = {item["path"]: item["status"] for item in json.loads(files["manifest.json"])["log_sources"]}
            self.assertIn("not a regular file", statuses[link.as_posix()])

    def test_missing_files_are_reported_with_stderr_commands(self):
        files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": "/nonexistent/dir/ui.log"})
        manifest = json.loads(files["manifest.json"])
        self.assertEqual({item["status"] for item in manifest["log_sources"]}, {"not found"})
        reasons = " ".join(item["reason"] for item in manifest["unavailable"])
        self.assertIn("docker logs", reasons)
        self.assertIn("journalctl -u bunkerweb-ui", reasons)


class ManifestAndCapsTest(unittest.TestCase):
    def test_manifest_lists_files_and_truncations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            path.write_text("".join(f"[2026-10-05 10:00:00 +0000] [UI] [1] [INFO] - line {n:04d}\n" for n in range(200)), encoding="utf-8")
            files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": path.as_posix()}, file_cap=1000)
            manifest = json.loads(files["manifest.json"])
            source = next(item for item in manifest["log_sources"] if item["path"] == path.as_posix())
            self.assertEqual(source["status"], "included")
            self.assertEqual(source["writers"], ["main UI error log"])
            self.assertEqual(len(source["conditions"]), 1)
            self.assertEqual(source["cut_to_last_bytes"], 1000)
            self.assertGreater(source["file_bytes"], 1000)
            self.assertLessEqual(source["included_bytes"], 1000)
            self.assertEqual({entry["name"] for entry in manifest["files"]}, {name for name in files if name != "manifest.json"})
            self.assertEqual(manifest["caps"]["file_tail_bytes"], 1000)
            self.assertIn("line 0199", files["logs/ui.log"])
            self.assertNotIn("line 0000", files["logs/ui.log"])

    def test_total_cap_truncates_and_records_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            line = "[2026-10-05 10:00:00 +0000] [UI] [1] [INFO] - line {:04d}\n"
            path.write_text("".join(line.format(n) for n in range(500)), encoding="utf-8")
            Path(tmp, "ui-access.log").write_text("".join(line.format(n) for n in range(30)), encoding="utf-8")
            files = make_bundle(environ={"CAPTURE_OUTPUT": "yes", "LOG_FILE_PATH": path.as_posix()}, total_cap=2000)
            manifest = json.loads(files["manifest.json"])
            entry = next(item for item in manifest["files"] if item["name"] == "logs/ui.log")
            self.assertIn("total size cap", entry["truncated"])
            self.assertLessEqual(entry["bytes"], 2000)
            self.assertTrue(files["logs/ui.log"].startswith("[2026-"), "the cut must not start inside a line")
            self.assertLessEqual(sum(item["bytes"] for item in manifest["files"] if item["name"].startswith("logs/")), 2000)
            access = [item for item in manifest["files"] if item["name"] == "logs/ui-access.log"]
            skipped = {"item": "logs/ui-access.log", "reason": "total size cap reached"} in manifest["unavailable"]
            self.assertTrue(skipped or "truncated" in access[0])
            self.assertIn("plugins.json", files)
            self.assertIn("environment.json", files)

    def test_ring_stats_in_manifest(self):
        handler = RingBufferHandler(record_cap=30, total_cap=100)
        handler.setFormatter(Formatter("%(message)s"))
        for index in range(20):
            handler.emit(record("m" * (10 + index * 3)))
        files = make_bundle(ring=handler.snapshot())
        manifest = json.loads(files["manifest.json"])
        self.assertGreater(manifest["ring"]["records_evicted"], 0)
        self.assertGreater(manifest["ring"]["records_cut"], 0)
        self.assertIn("logs/ui-recent.log", files)
        self.assertIn("worker pid", files["logs/ui-recent.log"])

    def test_ring_records_are_anonymized_at_build(self):
        files = make_bundle(ring={"pid": 1, "started": "now", "records": ["client 203.0.113.9 asked secret.example.org"]})
        self.assertNotIn("203.0.113.9", files["logs/ui-recent.log"])
        self.assertNotIn("secret.example.org", files["logs/ui-recent.log"])


class PluginStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.roots = {kind: Path(self.tmp.name, kind) for kind in ("core", "external", "pro")}

    def plugin(self, kind, plugin_id, disk_version, blueprints=True, page=False):
        root = self.roots[kind].joinpath(plugin_id)
        root.mkdir(parents=True)
        if disk_version:
            root.joinpath("plugin.json").write_text(json.dumps({"id": plugin_id, "version": disk_version}))
        if blueprints:
            root.joinpath("ui", "blueprints").mkdir(parents=True)
        return root

    def blueprint(self, plugin_id, kind, version, priority=2):
        return {
            "name": plugin_id,
            "plugin_priority": priority,
            "root_path": f"/x/{plugin_id}",
            "import_path": self.roots[kind].joinpath(plugin_id, "ui", "blueprints").as_posix(),
            "plugin_version": version,
        }

    def report(self, db_plugins, blueprints):
        result = build_plugins_report(db_plugins, self.roots, blueprints, {"pid": 7})
        return {item["id"]: item for item in result["plugins"]}

    def test_ok(self):
        self.plugin("pro", "alpha", "1.2")
        out = self.report([{"id": "alpha", "type": "pro", "version": "1.2", "page": True}], [self.blueprint("alpha", "pro", "1.2")])
        self.assertEqual(out["alpha"]["status"], "ok")
        self.assertEqual(out["alpha"]["loaded"][0]["recorded_version"], "1.2")
        self.assertEqual(out["alpha"]["page"], {"database": True, "filesystem": True})

    def test_database_disk_mismatch(self):
        self.plugin("external", "beta", "2.0")
        out = self.report([{"id": "beta", "type": "ui", "version": "1.0"}], [self.blueprint("beta", "external", "2.0")])
        self.assertEqual(out["beta"]["status"], "mismatch")
        self.assertEqual(out["beta"]["mismatches"], [{"pair": "database/disk", "database": "1.0", "disk": "2.0"}])
        self.assertEqual(out["beta"]["type"], "external")

    def test_equal_priority_stale_blueprint_is_a_load_mismatch(self):
        self.plugin("pro", "gamma", "3.0")
        stale = self.blueprint("gamma", "pro", "2.0")
        out = self.report([{"id": "gamma", "type": "pro", "version": "3.0"}], [stale])
        self.assertEqual(out["gamma"]["status"], "mismatch")
        self.assertEqual(out["gamma"]["mismatches"], [{"pair": "disk/loaded", "disk": "3.0", "loaded": "2.0"}])

    def test_unknown_without_recorded_load_version(self):
        self.plugin("pro", "delta", "1.0")
        out = self.report([{"id": "delta", "type": "pro", "version": "1.0"}], [])
        self.assertEqual(out["delta"]["status"], "unknown")
        out = self.report([{"id": "delta", "type": "pro", "version": "1.0"}], [self.blueprint("delta", "pro", None)])
        self.assertEqual(out["delta"]["status"], "unknown")

    def test_unknown_without_disk_version_and_ok_without_ui(self):
        out = self.report([{"id": "ghost", "type": "external", "version": "1.0"}], [])
        self.assertEqual(out["ghost"]["status"], "unknown")
        self.plugin("core", "plain", "1.0", blueprints=False)
        out = self.report([{"id": "plain", "type": "core", "version": "1.0"}], [])
        self.assertEqual(out["plain"]["status"], "ok")

    def test_blueprints_without_import_path_are_ignored(self):
        self.plugin("core", "plain", "1.0", blueprints=False)
        out = self.report([{"id": "plain", "type": "core", "version": "1.0"}], [{"name": "x", "import_path": None}])
        self.assertEqual(out["plain"]["loaded"], [])


class NoSecretTest(unittest.TestCase):
    SECRETS = (
        "LICENSEKEY-9f8e7d",
        "mysql+pymysql://bw:DbPassw0rd@db:3306/bw",
        "DbPassw0rd",
        "flask-secret-key-value",
        "api-token-value-123",
        "smtp-password-value",
        "service-secret-value",
        "192.0.2.55",
        "instance-host.internal.corp",
    )

    def test_no_secret_reaches_the_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ui.log")
            path.write_text(
                "[2026-10-05 10:00:00 +0000] [UI] [1] [❌] - DATABASE_URI=mysql+pymysql://bw:DbPassw0rd@db:3306/bw "
                "PRO_LICENSE_KEY=LICENSEKEY-9f8e7d FLASK_SECRET_KEY=flask-secret-key-value from 192.0.2.55\n"
                "[2026-10-05 10:00:01 +0000] [UI] [1] [INFO] - API_TOKEN: api-token-value-123 SMTP_PASSWORD='smtp-password-value'\n",
                encoding="utf-8",
            )
            environ = {
                "CAPTURE_OUTPUT": "yes",
                "LOG_FILE_PATH": path.as_posix(),
                "DATABASE_URI": self.SECRETS[1],
                "PRO_LICENSE_KEY": self.SECRETS[0],
                "FLASK_SECRET_KEY": self.SECRETS[3],
                "API_TOKEN": self.SECRETS[4],
                "SMTP_PASSWORD": self.SECRETS[5],
            }
            metadata = {
                "version": "1.6.16~rc3",
                "is_pro": True,
                "pro_license": self.SECRETS[0],
                "pro_status": "active",
                "pro_expire": datetime(2027, 1, 1, tzinfo=timezone.utc),
                "pro_services": 5,
                "database_version": "10.11.6-MariaDB",
                "database_uri": self.SECRETS[1],
                "flask_secret": self.SECRETS[3],
            }
            instances = [{"name": "bw", "type": "static", "method": "ui", "status": "up", "hostname": self.SECRETS[8], "secret": self.SECRETS[6]}]
            environment = build_environment(
                metadata=metadata, integration="Docker", instances=instances, service_count=3, db_dialect="mysql", db_revision="abc123", worker={"pid": 1}
            )
            data = build_support_bundle(
                domains=DOMAINS,
                environ=environ,
                integration="Docker",
                ring={"pid": 1, "started": "now", "records": ["token=" + self.SECRETS[4]]},
                plugins={"plugins": []},
                environment=environment,
                now=NOW,
            )
        blob = "\n".join(bundle_files(data).values())
        for secret in self.SECRETS:
            self.assertNotIn(secret, blob)
        env = json.loads(bundle_files(data)["environment.json"])
        self.assertEqual(
            env["pro"], {"active": True, "status": "active", "expire": "2027-01-01T00:00:00+00:00", "services_allowed": 5, "services_configured": 3}
        )
        self.assertEqual(env["database"]["dialect"], "mysql")
        self.assertEqual(env["database"]["alembic_revision"], "abc123")
        self.assertTrue(env["instances"][0]["hostname"].startswith("host-"))
        self.assertEqual(set(env), {"bunkerweb_version", "integration", "pro", "python", "libraries", "database", "instances", "worker"})


class RouteGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from flask import Flask
        from flask_login import LoginManager, UserMixin

        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        dependencies = ModuleType("app.dependencies")
        config = MagicMock()
        config.get_config.return_value = {"SERVER_NAME": "", "www_SERVER_NAME": "secret.example.org"}
        db = MagicMock()
        db.get_plugins.return_value = []
        db.get_metadata.return_value = {"version": "1.6.16~rc3", "is_pro": False, "pro_status": "invalid", "pro_expire": None, "pro_services": 0}
        db.get_instances.return_value = []
        db.get_services.return_value = []
        db.sql_engine.dialect.name = "sqlite"
        db._db_session.side_effect = RuntimeError("no database")
        dependencies.BW_CONFIG, dependencies.DB = config, db
        dependencies.CORE_PLUGINS_PATH = dependencies.EXTERNAL_PLUGINS_PATH = dependencies.PRO_PLUGINS_PATH = tmp
        cls.previous = sys.modules.get("app.dependencies")
        sys.modules["app.dependencies"] = dependencies
        sys.modules.pop("app.routes.support", None)
        from app.routes.support import support

        class User(UserMixin):
            def __init__(self, name, admin):
                self.id, self.admin = name, admin

        users = {"admin": User("admin", True), "reader": User("reader", False)}
        app = Flask(__name__)
        app.secret_key = "test"
        manager = LoginManager(app)

        @manager.request_loader
        def load(request):
            return users.get(request.headers.get("X-User", ""))

        app.register_blueprint(support)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        sys.modules.pop("app.routes.support", None)
        if cls.previous is None:
            sys.modules.pop("app.dependencies", None)
        else:
            sys.modules["app.dependencies"] = cls.previous

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get("/support/ui_bundle").status_code, 401)

    def test_non_admin_gets_403(self):
        response = self.client.get("/support/ui_bundle", headers={"X-User": "reader"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b"PK", response.data[:2])

    def test_admin_gets_the_zip(self):
        response = self.client.get("/support/ui_bundle", headers={"X-User": "admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertRegex(response.headers["Content-Disposition"], r"bunkerweb-ui-support-\d{8}T\d{6}Z\.zip")
        files = bundle_files(response.data)
        self.assertTrue({"manifest.json", "plugins.json", "environment.json", "errors.txt"} <= set(files))
        self.assertEqual(json.loads(files["environment.json"])["database"]["dialect"], "sqlite")


class TemplateAndLocalesTest(unittest.TestCase):
    def test_card_is_admin_only(self):
        template = REPO_ROOT.joinpath("src/ui/app/templates/support.html").read_text(encoding="utf-8")
        start = template.index("{% if user_admin %}")
        end = template.index("{% endif %}", start)
        self.assertIn("/ui_bundle", template[start:end])
        self.assertEqual(template.count("/ui_bundle"), 1)

    def test_keys_in_every_locale(self):
        locales = sorted(REPO_ROOT.joinpath("src/ui/app/static/locales").glob("*.json"))
        self.assertEqual(len(locales), 19)
        for locale in locales:
            card = json.loads(locale.read_text(encoding="utf-8"))["support"]["card"]["ui_bundle"]
            self.assertEqual(set(card), {"button", "help", "title"}, locale.name)
            self.assertTrue(all(card.values()), locale.name)


if __name__ == "__main__":
    unittest.main()
