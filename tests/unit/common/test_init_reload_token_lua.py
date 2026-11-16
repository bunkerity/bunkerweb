"""Init captures its reload token; rejected init cannot clear another reload's marker."""

import pytest

from test_init_rejects_invalid_config_lua import INIT_HARNESS, ROOT
from test_reload_readiness_lua import run_lua


@pytest.mark.parametrize("template", ["init-lua.conf", "init-stream-lua.conf"])
@pytest.mark.parametrize(
    "failure,process,successor", [("none", "master", False), ("manifest", "master", False), ("manifest", "master", True), ("manifest", "single", False)]
)
def test_init_captures_and_releases_only_owned_marker(tmp_path, template, failure, process, successor):
    source = (ROOT / "src/common/confs" / template).read_text()
    body = tmp_path / "init.lua"
    body.write_text(source.split("init_by_lua_block {", 1)[1].split("\n}", 1)[0])
    harness = INIT_HARNESS.replace("local failure, body_path = arg[1], arg[2]", f'local failure, body_path = "{failure}", [[{body}]]')
    harness = harness.replace("local touched = false", 'local marker = "current"\nlocal touched = false')
    harness = harness.replace("load_plugin = function()", "load_plugin = function()\n" + ('marker = "successor"' if successor else ""))
    harness = harness.replace(
        "io.open = function(path)",
        'io.open = function(path)\nif path == "/var/tmp/bunkerweb_reloading" then\n'
        'if marker then return { read = function() return marker end, close = function() end } end\nreturn nil, "No such file", 2 end',
    )
    harness = harness.replace(
        "local ok, err = pcall(body)",
        f'package.preload["ngx.process"] = function() return {{ type = function() return "{process}" end }} end\n'
        "os.remove = function() marker = nil; return true end\nlocal ok, err = pcall(body)",
    )
    harness += '\nassert(package.loaded["bunkerweb.reload_marker_token"] == "current", "init did not capture the reload token")\n'
    expected = "nil" if failure == "manifest" and process == "master" and not successor else ('"successor"' if successor else '"current"')
    harness += f'assert(marker == {expected}, "wrong marker cleanup: " .. tostring(marker))\n'
    run_lua(harness)
