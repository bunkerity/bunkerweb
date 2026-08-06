import importlib
import sys
from types import ModuleType
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests"


def test_invalid_manifest_entry_still_runs_cleanup(monkeypatch):
    monkeypatch.syspath_prepend(str(TESTS))
    openssl = ModuleType("OpenSSL")
    crypto = ModuleType("OpenSSL.crypto")
    openssl.crypto = crypto
    logger = ModuleType("logger")
    logger.log = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "OpenSSL", openssl)
    monkeypatch.setitem(sys.modules, "OpenSSL.crypto", crypto)
    monkeypatch.setitem(sys.modules, "logger", logger)
    test_module = importlib.import_module("Test")
    monkeypatch.setattr(test_module, "sleep", lambda _: None)

    class Harness(test_module.Test):
        cleaned = False

        def _setup_test(self):
            return True

        def _cleanup_test(self):
            self.cleaned = True
            return True

        def _debug_fail(self):
            pass

    harness = Harness("invalid", "docker", 0.01, [{}])
    assert harness.run_tests() is False
    assert harness.cleaned is True
