"""`tests/scripts/before/latest_stable.py` must authenticate when it can, retry, and say why it failed.

The silent version printed an empty line on any exception, so the `upgrade` category went red with
"Failed to fetch latest stable release from GitHub" and nothing else -- an unauthenticated
`api.github.com` call from a hosted runner (60 req/h per shared IP) rate-limited, unretried, unlogged.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "tests/scripts/before/latest_stable.py"


@pytest.fixture
def latest_stable(monkeypatch):
    # httpx is a harness dependency, not a unit one: the module only needs the name to import.
    monkeypatch.setitem(sys.modules, "httpx", ModuleType("httpx"))
    spec = importlib.util.spec_from_file_location("latest_stable", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sleep", lambda _s: None)
    return module


class _Response:
    def __init__(self, tag=None, error=None):
        self._tag, self._error = tag, error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return {"tag_name": self._tag}


class _Client:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def get(self, path):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_bearer_token_from_the_environment(latest_stable, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_abc")
    assert latest_stable.request_headers()["Authorization"] == "Bearer ghs_abc"
    monkeypatch.delenv("GITHUB_TOKEN")
    assert "Authorization" not in latest_stable.request_headers()


def test_transient_failure_is_retried_and_reported(latest_stable, capsys):
    client = _Client([ConnectionResetError("peer"), _Response(tag="v1.6.15")])
    assert latest_stable.latest_stable(client) == "1.6.15"
    assert client.calls == 2
    assert "attempt 1/3 failed" in capsys.readouterr().err


def test_exhausted_attempts_print_nothing_but_explain(latest_stable, capsys):
    client = _Client([_Response(error=RuntimeError("403 rate limit"))] * 3)
    assert latest_stable.latest_stable(client) == ""
    assert client.calls == 3
    assert capsys.readouterr().err.count("failed") == 3
