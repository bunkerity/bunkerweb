"""Tests for the support redaction shared by the Web UI diagnostics and `bwcli support` (src/common/utils/support_common.py, UI login route)."""

import json
import sys
import unittest
from pathlib import Path
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "src/ui"), str(REPO_ROOT / "src/common/utils")]

from support_common import REDACTED, Anonymizer  # noqa: E402


def best_time(function, text, runs=3):
    best = float("inf")
    for _ in range(runs):
        start = perf_counter()
        function(text)
        best = min(best, perf_counter() - start)
    return best


class TestRedactorIsLinear(unittest.TestCase):
    """L02-F2: an attacker-sized value must not cost quadratic time in the redactor."""

    SHAPES = {
        "letters": lambda n: "a" * n,
        "dotted letters": lambda n: "a." * (n // 2),
        "scheme without userinfo": lambda n: "http://" + "a" * n,
    }

    def test_scan_time_grows_linearly(self):
        anonymizer = Anonymizer()
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                small = best_time(anonymizer.redact, shape(20000))
                large = best_time(anonymizer.redact, shape(40000))
                # Linear doubling costs ~2x, quadratic ~4x; the absolute bound catches a slow constant factor
                self.assertLess(large / max(small, 1e-6), 3.2, f"{small:.4f}s -> {large:.4f}s")
                self.assertLess(large, 0.25, f"{large:.4f}s for 40000 characters")

    def test_credentials_in_uri_userinfo_still_redacted(self):
        anonymizer = Anonymizer(anonymize=False)
        for text in (
            "fetching https://user:s3cr3t@host.example/x.zip now",
            "fetching 1http://user:s3cr3t@host.example/x.zip now",
            "fetching git+ssh://user:s3cr3t@host.example/x.git now",
            "fetching " + "a" * 5000 + "://user:s3cr3t@host.example",
        ):
            with self.subTest(text=text[:40]):
                redacted = anonymizer.redact(text)
                self.assertNotIn("s3cr3t", redacted)
                self.assertIn(f"{REDACTED}@host.example", redacted)


class TestLoginUsernameLog(unittest.TestCase):
    """L02-F2: the login route logs a bounded username."""

    def test_long_username_is_bounded_in_the_log_message(self):
        from app.utils import loggable_username

        username = "a" * 64000
        shown = loggable_username(username)
        self.assertLess(len(shown), 200)
        self.assertIn("64000", shown)

    def test_short_username_is_kept_and_control_characters_escaped(self):
        from app.utils import loggable_username

        self.assertEqual(loggable_username("admin"), "'admin'")
        self.assertNotIn("\n", loggable_username("ad\nmin"))

    def test_cut_never_leaves_a_credential_fragment(self):
        from app.utils import loggable_username

        # The cut falls inside the password, but the userinfo was masked first
        username = "https://admin:" + "S3CRETVALUE" * 20 + "@host.example/path"
        shown = loggable_username(username)
        self.assertNotIn("S3CRET", shown)


class TestJsonAuditLogBodies(unittest.TestCase):
    """L08-F2: a JSON audit record holds the request body as an escaped JSON string."""

    @staticmethod
    def audit_line(body):
        record = {
            "transaction": {
                "client_ip": "192.0.2.10",
                "request": {"request_line": "POST /login HTTP/1.1", "headers": {"Host": "app.example", "Content-Type": "application/json"}, "body": body},
                "response": {"http_code": 403},
            }
        }
        return json.dumps(record, separators=(",", ":"))

    def test_json_body_credentials_are_redacted(self):
        body = json.dumps({"user": "bob", "password": "P4ssw0rd-LEAK", "nested": {"token": "T0kenLEAK"}, "list": [{"api_key": "KeyLEAK"}]})
        out = Anonymizer(anonymize=False).redact(self.audit_line(body))
        for leak in ("P4ssw0rd-LEAK", "T0kenLEAK", "KeyLEAK"):
            self.assertNotIn(leak, out)
        decoded = json.loads(out)  # still one valid JSON record
        self.assertEqual(decoded["transaction"]["request"]["request_line"], "POST /login HTTP/1.1")
        self.assertIn("bob", out)

    def test_double_encoded_body_is_decoded_recursively(self):
        inner = json.dumps({"password": "DeepLEAK"})
        body = json.dumps({"payload": inner})
        out = Anonymizer(anonymize=False).redact(self.audit_line(body))
        self.assertNotIn("DeepLEAK", out)

    def test_form_body_still_redacted(self):
        out = Anonymizer(anonymize=False).redact(self.audit_line("user=bob&password=FormLEAK&x=1"))
        self.assertNotIn("FormLEAK", out)

    def test_unparsable_line_drops_the_body(self):
        line = self.audit_line(json.dumps({"password": "CutLEAK"}))
        broken = line[: line.index("CutLEAK") + 3]  # cut inside the escaped body, no closing quote
        out = Anonymizer(anonymize=False).redact(broken + "\nnext line password=Other1")
        self.assertNotIn("CutLEAK", out)
        self.assertNotIn("Other1", out)
        self.assertIn("POST /login", out)

    def test_other_lines_are_untouched(self):
        text = "[2026-11-17 10:00:00] - UI - INFO - something happened\n"
        self.assertEqual(Anonymizer(anonymize=False).redact(text), text)

    def test_multiple_lines_each_scrubbed(self):
        lines = [self.audit_line(json.dumps({"password": f"Leak{i}"})) for i in range(3)]
        out = Anonymizer(anonymize=False).redact("\n".join(lines))
        for i in range(3):
            self.assertNotIn(f"Leak{i}", out)
        self.assertEqual(len(out.splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
