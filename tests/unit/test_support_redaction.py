"""Tests for the support redaction shared by the Web UI diagnostics and `bwcli support` (src/common/utils/support_common.py, UI login route)."""

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


if __name__ == "__main__":
    unittest.main()
