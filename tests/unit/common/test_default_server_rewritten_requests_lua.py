"""A request a custom config only rewrote must go through the default server's access phase.

A ``rewrite`` in a ``default-server-http`` custom config sets ``r->internal``. The default server's
access runner used to return at ``is_internal()`` for it, so bans and the configured access plugins
(``whitelist``, ``ssl``'s redirect, ...) were off for that request. The per-service runner already
tells a rewrite from a true internal request: the set phase marks ``ngx.ctx.bw.access_pending`` and
the access phase runs for an internal request that carries the mark, once.

The *rendered* ``set`` and ``access`` blocks are executed under a stand-alone ``lua`` over the same
request lifetimes ``test_access_rewritten_requests.py`` uses for the service blocks. An internal
redirect, a named location and a subrequest clear the Lua request context, and the default server's
set phase does not rebuild it on the internal path, so they must still skip.
"""

import subprocess

import pytest
from test_access_rewritten_requests import EXPECTED, HARNESS, SCENARIOS  # type: ignore
from test_default_server_runners_lua import LUA, lua_block, needs_lua, render  # type: ignore

# `whitelist` is in the default server's curated subset; the service harness orders a plugin called `p`.
DEFAULT_SERVER_HARNESS = HARNESS.replace('{ "p" }', '{ "whitelist" }')
assert DEFAULT_SERVER_HARNESS != HARNESS


def run(tmp_path, scenario: str):
    rendered = render("default-server-http.conf")
    (tmp_path / "set.lua").write_text(lua_block(rendered, "set_by_lua_block"), encoding="utf-8")
    (tmp_path / "access.lua").write_text(lua_block(rendered, "access_by_lua_block"), encoding="utf-8")
    (tmp_path / "harness.lua").write_text(DEFAULT_SERVER_HARNESS, encoding="utf-8")
    steps = ",".join(":".join(str(part).lower() for part in step) for step in SCENARIOS[scenario])
    result = subprocess.run(
        [str(LUA), str(tmp_path / "harness.lua"), str(tmp_path / "set.lua"), str(tmp_path / "access.lua"), steps],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    calls, bans, _ = result.stdout.strip().split("|")
    return int(calls), int(bans)


@needs_lua
@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_the_default_server_access_phase_runs_once_for_a_request_and_never_for_an_internal_redirect(tmp_path, scenario):
    """The ban check and the plugin chain both run once or not at all: zero for a rewritten request is
    the bypass, twice is a request processed twice."""
    expected_runs = EXPECTED[scenario][0]
    assert run(tmp_path, scenario) == (expected_runs, expected_runs), scenario
