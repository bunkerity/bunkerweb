"""Out-of-range timestamp strings keep the existing text fallback."""

import pytest


@pytest.mark.parametrize("plugin,formatter", [("authbasic", "_format_date"), ("badbehavior", "_format_increment_date")])
def test_oversized_timestamp_string_keeps_text(load_plugin, plugin, formatter):
    assert getattr(load_plugin(plugin), formatter)("1e30") == "1e30"
