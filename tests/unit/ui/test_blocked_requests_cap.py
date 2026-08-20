"""`METRICS_MAX_BLOCKED_REQUESTS_REDIS` is a `text` setting whose default is `10k`.

`int("10k")` raises. The caller caught it with a bare `except` and returned its 100000 fallback,
so on the **default configuration** the UI scanned ten times the cap the Redis list is actually
trimmed to -- silently, and with the log line that would have said so swallowed by the same
`except`. The bare `except` is the mechanism here, not the `int()`: without it the ValueError
would have been a stack trace on day one.

The parser mirrors `core/metrics/metrics.lua:361` deliberately. Two independent parsers for one
setting is how the UI's idea of the cap drifts from the runtime's, so the cases the Lua rejects
are asserted to be rejected here too.
"""

import importlib.util
import sys
from pathlib import Path
from re import findall

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
_LUA = _SRC / "common" / "core" / "metrics" / "metrics.lua"


@pytest.fixture(scope="module")
def instance_module():
    for path in (_SRC / "ui", _SRC / "common" / "utils", _SRC / "common" / "api", _SRC / "common" / "db"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("instance_model_cap_under_test", _SRC / "ui" / "app" / "models" / "instance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeClient:
    def __init__(self, settings=None, raises=None):
        self.settings = settings if settings is not None else {}
        self.raises = raises

    def get_global_settings(self, **_):
        if self.raises:
            raise self.raises
        return self.settings


def _utils(module, client):
    utils = object.__new__(module.InstancesUtils)
    # Name-mangled: the attribute is set in `InstancesUtils.__init__`, which wants a live client.
    setattr(utils, "_InstancesUtils__api_client", client)
    return utils


# --------------------------------------------------------------------------------------
# The defect
# --------------------------------------------------------------------------------------
def test_the_shipped_default_is_read_as_ten_thousand_not_a_hundred_thousand(instance_module):
    """The whole bug in one assertion: `10k` is the default in `metrics/plugin.json`."""
    utils = _utils(instance_module, FakeClient({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "10k"}))

    assert utils._get_max_blocked_requests_redis() == 10000


def test_the_default_really_is_the_one_the_plugin_ships(instance_module):
    """Anchors the test above to the manifest, so a changed default does not leave it asserting
    a value nothing uses."""
    from json import loads

    manifest = loads((_SRC / "common" / "core" / "metrics" / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["settings"]["METRICS_MAX_BLOCKED_REQUESTS_REDIS"]["default"] == "10k"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("10000", 10000),
        ("10k", 10000),
        ("10K", 10000),
        ("1m", 1000000),
        ("1M", 1000000),
        (" 100k ", 100000),
        ("0", 0),
        (5000, 5000),
    ],
)
def test_every_form_the_setting_accepts_parses(instance_module, value, expected):
    assert instance_module._parse_count(value, 100000) == expected


@pytest.mark.parametrize("value", ["1.5k", "-5", "1e3", "10g", "", "abc", "10 k", None])
def test_what_the_lua_parser_rejects_is_rejected_here_too(instance_module, value):
    """Falling back is correct; inventing a value the runtime would not honour is not."""
    assert instance_module._parse_count(value, 100000) == 100000


def test_the_setting_regex_and_the_parser_agree_on_what_is_valid(instance_module):
    """The manifest's own regex is the contract both parsers implement."""
    from json import loads
    from re import fullmatch

    manifest = loads((_SRC / "common" / "core" / "metrics" / "plugin.json").read_text(encoding="utf-8"))
    pattern = manifest["settings"]["METRICS_MAX_BLOCKED_REQUESTS_REDIS"]["regex"]

    for candidate in ("10000", "10k", "10K", "1m", "1M", "0"):
        assert fullmatch(pattern, candidate), f"{candidate} should be schema-valid"
        assert instance_module._parse_count(candidate, -1) != -1, f"{candidate} is schema-valid but the parser rejects it"
    for candidate in ("1.5k", "-5", "1e3", "10g"):
        assert not fullmatch(pattern, candidate), f"{candidate} should be schema-invalid"
        assert instance_module._parse_count(candidate, -1) == -1, f"{candidate} is schema-invalid but the parser accepts it"


def test_the_parser_still_matches_the_lua_one_it_mirrors():
    """Read out of the Lua rather than restated, so a change there fails here instead of drifting."""
    source = _LUA.read_text(encoding="utf-8")

    assert '"^(%d+)([kKmM]?)$"' in source, "the Lua parse_count pattern moved; re-check _parse_count against it"
    assert findall(r"num \* (\d+)", source)[:2] == ["1000", "1000000"], "the Lua multipliers changed"


# --------------------------------------------------------------------------------------
# The narrowed `except`
# --------------------------------------------------------------------------------------
def test_an_unreachable_api_still_falls_back_rather_than_five_hundred_ing(instance_module):
    """Five page-rendering call sites depend on this, so the API being down must not 500 them."""
    from app.api_client import ApiUnavailableError

    utils = _utils(instance_module, FakeClient(raises=ApiUnavailableError("api down")))

    assert utils._get_max_blocked_requests_redis() == 100000


def test_an_unexpected_error_is_no_longer_swallowed(instance_module):
    """The narrowing, stated as behaviour: a bare `except` here is what hid the 10x for months.

    Anything that is not an API transport failure is a defect and must surface.
    """
    utils = _utils(instance_module, FakeClient(raises=KeyError("something else entirely")))

    with pytest.raises(KeyError):
        utils._get_max_blocked_requests_redis()


def test_a_missing_setting_falls_back(instance_module):
    utils = _utils(instance_module, FakeClient({}))

    assert utils._get_max_blocked_requests_redis() == 100000


def test_a_negative_result_is_clamped(instance_module):
    """`max(0, ...)` is pre-existing behaviour and the Redis scan relies on it."""
    utils = _utils(instance_module, FakeClient({"METRICS_MAX_BLOCKED_REQUESTS_REDIS": "-1"}))

    assert utils._get_max_blocked_requests_redis() == 100000
