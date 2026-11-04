import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = REPO_ROOT / "src/common/core/letsencrypt/jobs/certbot-deploy.py"
API_CALLER = REPO_ROOT / "src/common/utils/ApiCaller.py"
sys.path[:0] = [str(REPO_ROOT / "src/common/utils"), str(REPO_ROOT / "src/deps/python")]


def run_deploy(reload_replies):
    """Run certbot-deploy.py against a stub API whose /reload answers with the given replies in turn."""
    logger = MagicMock()
    calls = []
    replies = list(reload_replies)

    def request(method, url, **kwargs):
        calls.append(url)
        if url.lstrip("/").startswith("reload"):
            return True, "", *replies.pop(0)
        return True, "", 200, {"status": "success"}

    api = SimpleNamespace(endpoint="http://bw:5000", request=request)
    modules = {
        "Database": SimpleNamespace(
            Database=lambda *args, **kwargs: SimpleNamespace(
                get_instances=lambda: [{}],
                get_non_default_settings=lambda **kwargs: {"SERVER_NAME": "a.example.com"},
            )
        ),
        "logger": SimpleNamespace(getLogger=lambda name: logger),
        "API": SimpleNamespace(API=SimpleNamespace(from_instance=lambda instance: api)),
    }
    exit_info = {"code": None}
    with patch.dict(sys.modules, modules):
        spec = spec_from_file_location("ApiCaller", API_CALLER)
        api_caller = module_from_spec(spec)
        spec.loader.exec_module(api_caller)
        sys.modules["ApiCaller"] = api_caller
        with (
            patch.object(api_caller, "sleep"),
            patch("tarfile.TarFile.add"),
            patch.dict("os.environ", {"CERTBOT_TOKEN": "tok", "RENEWED_DOMAINS": "a.example.com"}),
            patch("sys.path", list(sys.path)),
        ):
            try:
                run_path(str(DEPLOY), run_name="__main__")
            except SystemExit as exc:
                exit_info["code"] = exc.code
    return exit_info["code"], [url for url in calls if url.lstrip("/").startswith("reload")]


class CertbotDeployReloadBusyTest(unittest.TestCase):
    def test_busy_reload_is_retried_until_it_succeeds(self):
        code, reloads = run_deploy([(503, {"msg": "busy"}), (503, {"msg": "busy"}), (200, {"status": "success"})])
        self.assertEqual(len(reloads), 3)
        self.assertEqual(code, 0)

    def test_reload_busy_on_every_attempt_fails_the_hook(self):
        code, reloads = run_deploy([(503, {"msg": "busy"})] * 3)
        self.assertEqual(len(reloads), 3)
        self.assertEqual(code, 1)

    def test_other_errors_are_not_retried(self):
        code, reloads = run_deploy([(500, {"msg": "boom"})])
        self.assertEqual(len(reloads), 1)
        self.assertEqual(code, 1)

    def test_first_try_success(self):
        code, reloads = run_deploy([(200, {"status": "success"})])
        self.assertEqual(len(reloads), 1)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
