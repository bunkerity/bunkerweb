"""UB4-10: an API burst must allow ten requests, then reject two with Retry-After."""

import importlib
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def burst(monkeypatch):
    aliases = ("ci_limit_handlers", "ci_limit_models")
    for alias, directory in zip(aliases, ("core_handlers", "models")):
        package = ModuleType(alias)
        package.__path__ = [str(ROOT / "tests" / directory)]
        monkeypatch.setitem(sys.modules, alias, package)
    handler = importlib.import_module("ci_limit_handlers.limit_handler")
    model = importlib.import_module("ci_limit_models.limit").Limit
    data = yaml.safe_load((ROOT / "tests/api/limit.yml").read_text())["actions"]["rate_limit_auth"]
    # Exercise the existing max_requests contract before the spec opts into it.
    action = model(**(data | {"max_requests": 10}))
    monkeypatch.setattr(handler, "sleep", lambda _: None)

    def run(responses):
        responses = iter(responses)
        monkeypatch.setattr(handler, "perform_request", lambda *_: SimpleNamespace(response=next(responses)))
        handler.handle(logging.getLogger(__name__), action)

    yield run
    for name in list(sys.modules):
        if any(name.startswith(f"{alias}.") for alias in aliases):
            sys.modules.pop(name)


def response(code, retry_after="30"):
    return httpx.Response(code, headers={"Retry-After": retry_after} if retry_after is not None else {})


def test_exact_api_burst_passes(burst):
    burst([response(200) for _ in range(10)] + [response(429), response(429)])


@pytest.mark.parametrize(
    "codes",
    [
        [200] * 11 + [429],
        [200] * 9 + [429] * 3,
        [429] * 12,
        [429] + [200] * 10 + [429],
        [500] * 10 + [429] * 2,
        [200] * 9 + ["connection failed", 429, 429],
    ],
)
def test_wrong_count_order_or_failed_request_fails(burst, codes):
    with pytest.raises(SystemExit) as failed:
        burst([response(code) if isinstance(code, int) else code for code in codes])
    assert failed.value.code == 1


@pytest.mark.parametrize("retry_after", [None, "", "0", "-1", "later"])
def test_first_limited_response_needs_positive_retry_after(burst, retry_after):
    with pytest.raises(SystemExit) as failed:
        burst([response(200) for _ in range(10)] + [response(429, retry_after), response(429)])
    assert failed.value.code == 1


def test_api_spec_pins_allowed_count():
    data = yaml.safe_load((ROOT / "tests/api/limit.yml").read_text())
    assert data["actions"]["rate_limit_auth"].get("max_requests") == 10
