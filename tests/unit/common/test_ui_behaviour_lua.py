"""Behaviour of ``ui.lua``: the Web UI plugin marks https as configured only when it is enabled."""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua


@pytest.mark.parametrize(("use_ui", "configured"), [("yes", "yes"), ("no", "nil")])
def test_https_configured_follows_use_ui(use_ui, configured):
    out = run(
        "ui",
        f"""
VARIABLES = {{ USE_UI = "{use_ui}" }}
local c = ctx()
local r = PLUGIN:new(c):set()
emit("msg", r.msg) emit("status", r.status) emit("https", c.bw.https_configured)
""",
    )
    assert out["msg"] == f"set https_configured to {use_ui}"
    assert out["status"] == "nil"
    assert out["https"] == configured
