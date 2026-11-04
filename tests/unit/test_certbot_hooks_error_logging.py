import sys
import unittest
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

JOBS_DIR = Path(__file__).resolve().parents[2] / "src/common/core/letsencrypt/jobs"


def run_hook(script, reply):
    logger = MagicMock()
    api = SimpleNamespace(endpoint="http://bw:5000", request=lambda *args, **kwargs: (True, "", *reply))
    modules = {
        "Database": SimpleNamespace(Database=lambda *args, **kwargs: SimpleNamespace(get_instances=lambda: [{}])),
        "logger": SimpleNamespace(getLogger=lambda name: logger),
        "API": SimpleNamespace(API=SimpleNamespace(from_instance=lambda instance: api)),
    }
    with patch.dict(sys.modules, modules), patch.dict("os.environ", {"CERTBOT_TOKEN": "tok", "CERTBOT_VALIDATION": "val"}):
        with patch("sys.path", list(sys.path)), self_exit() as exit_info:
            run_path(str(JOBS_DIR / script), run_name="__main__")
    return exit_info["code"], [call.args[0] for call in logger.error.call_args_list]


class self_exit:
    def __enter__(self):
        self.info = {"code": None}
        return self.info

    def __exit__(self, exc_type, exc, tb):
        if exc_type is SystemExit:
            self.info["code"] = exc.code
            return True
        return False


class CertbotHooksErrorLoggingTest(unittest.TestCase):
    def test_non_200_without_status_key_is_logged(self):
        for script in ("certbot-auth.py", "certbot-cleanup.py"):
            for http_status, body in ((403, {}), (502, "<html>")):
                with self.subTest(script=script, http_status=http_status):
                    code, errors = run_hook(script, (http_status, body))
                    self.assertEqual(code, 1)
                    self.assertEqual(len(errors), 1)
                    self.assertIn(f"HTTP {http_status}", errors[0])
                    self.assertNotIn("Exception while running", errors[0])

    def test_dict_reply_keeps_status_and_msg(self):
        code, errors = run_hook("certbot-auth.py", (400, {"status": "ko", "msg": "bad token"}))
        self.assertEqual(code, 1)
        self.assertIn("HTTP 400, status = ko, msg = bad token", errors[0])


if __name__ == "__main__":
    unittest.main()
