"""Oversized timestamps in the Basic Authentication and Bad Behavior dashboards fall back (dev 8db44b794).

`datetime.fromtimestamp` raises `OverflowError` for a value beyond the platform's `time_t` range
(`1e30`, `10**20`), which neither formatter caught, so one such row broke the whole dashboard.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FORMATTERS = (("authbasic", "_format_date"), ("badbehavior", "_format_increment_date"))


def _formatter(plugin, name):
    path = ROOT / "src" / "common" / "core" / plugin / "ui" / "actions.py"
    spec = importlib.util.spec_from_file_location(f"test_{plugin}_actions_overflow", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, name)


@pytest.mark.parametrize("plugin, name", FORMATTERS)
@pytest.mark.parametrize("value", [10**20, 1e30, float("1e30"), "1e30", "99999999999999999999"])
def test_an_oversized_timestamp_does_not_raise(plugin, name, value):
    result = _formatter(plugin, name)(value)

    assert isinstance(result, str)


@pytest.mark.parametrize("plugin, name", FORMATTERS)
def test_a_numeric_oversized_timestamp_falls_back_to_the_epoch(plugin, name):
    format_date = _formatter(plugin, name)

    assert format_date(10**20) == format_date(0)


@pytest.mark.parametrize("plugin, name", FORMATTERS)
def test_a_text_oversized_timestamp_falls_back_to_the_text(plugin, name):
    assert _formatter(plugin, name)("99999999999999999999") == "99999999999999999999"


@pytest.mark.parametrize("plugin, name", FORMATTERS)
def test_ordinary_values_are_unchanged(plugin, name):
    format_date = _formatter(plugin, name)

    assert format_date(1_758_702_308).startswith("2025-09-2")
    assert format_date("1758702308").startswith("2025-09-2")
    assert format_date("not a date") == "not a date"
    assert format_date(None) == ""
