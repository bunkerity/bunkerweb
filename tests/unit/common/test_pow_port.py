"""Run shipped PoW verification and solver; lowering the saved target must fail."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/antibot"


def _method(source, name):
    return re.search(rf"function antibot:{name}\(.*?(?=\nfunction antibot:|\Z)", source, re.S).group()


def _lua(body, digest=b"\0\0\x40" + b"\xff" * 29):
    source = (PLUGIN / "antibot.lua").read_text()
    helpers = source[source.index("local function first_value") : source.index("-- Drop the query")]  # noqa: E203
    script = """
local antibot = {}
local ngx = {req = {read_body = function() end, get_post_args = function() return {challenge='42'} end},
  header={}, var={scheme='http'}, OK=0, HTTP_OK=200}
local now = function() return 100 end
local rand = function() return 'prefix' end
local path_only = function(p) return p end
local is_safe_relative_path = function(p) return p end
local render = function(_, vars) print('difficulty=' .. tostring(vars.antibot_difficulty)) end
local sha256 = {new=function() return {
  update=function(_, value) assert(value == 'prefix42') end,
  final=function() return DIGEST end} end}
local to_hex = function(s) return (s:gsub('.', function(c) return string.format('%02x', c:byte()) end)) end
""".replace("DIGEST", '"' + "".join(f"\\{b:03d}" for b in digest) + '"')
    script += helpers
    for name in ("prepare_challenge", "display_challenge", "check_challenge", "header"):
        script += _method(source, name) + "\n"
    script += """
local self = setmetatable({session_data={prepared=true,type='javascript',random='prefix'},
  variables={USE_ANTIBOT='javascript',ANTIBOT_URI='/challenge',ANTIBOT_JAVASCRIPT_DIFFICULTY='28'},
  ctx={bw={uri='/challenge',antibot_nonce_script='script',antibot_nonce_style='style',antibot_display_content=true}},
  set_session_data=function() end, resolve_redirect_target=function() return '/' end,
  get_original_uri=function() return '/' end, ret=function(_, ...) return ... end}, {__index=antibot})
""" + body
    result = subprocess.run([shutil.which("lua"), "-"], input=script, text=True, capture_output=True, check=True)
    return result.stdout.strip()


@pytest.mark.skipif(not shutil.which("lua"), reason="Lua interpreter required")
@pytest.mark.parametrize("bits,accepted", [(16, True), (17, True), (18, False), (28, False)])
def test_saved_difficulty_controls_verification(bits, accepted):
    # 00 00 40 has exactly 17 leading zero bits, not a hex-boundary target.
    output = _lua(f"self.session_data.difficulty={bits}; local ok, reason=self:check_challenge(); print(tostring(ok)); print(reason)")
    assert output.splitlines()[0] == str(accepted).lower()
    if not accepted:
        assert "below configured difficulty" in output and "outdated" in output


@pytest.mark.skipif(not shutil.which("lua"), reason="Lua interpreter required")
def test_legacy_target_and_one_attempt_per_challenge():
    output = _lua("local ok=self:check_challenge(); print(ok); local again, reason=self:check_challenge(); print(tostring(again)); print(reason)")
    assert output.splitlines() == ["true", "nil", "challenge not prepared"]
    assert _lua("print(self:check_challenge())", b"\0\x80" + b"\xff" * 30).startswith("false\twrong value")


@pytest.mark.skipif(not shutil.which("lua"), reason="Lua interpreter required")
def test_difficulty_is_saved_once_and_rendered_from_session():
    output = _lua("""
self.session_data={}; self.variables.ANTIBOT_JAVASCRIPT_DIFFICULTY='17'
self:prepare_challenge(); self.variables.ANTIBOT_JAVASCRIPT_DIFFICULTY='28'
self:prepare_challenge(); print(self.session_data.difficulty); self:display_challenge()
self.session_data.difficulty=nil; self:display_challenge()
""")
    assert output.splitlines() == ["17", "difficulty=17", "difficulty=16"]


@pytest.mark.skipif(not shutil.which("lua"), reason="Lua interpreter required")
def test_blob_worker_csp_is_limited_to_javascript():
    output = _lua("""
self.ctx.bw.antibot_session_data=self.session_data
self:header(); print(ngx.header['Content-Security-Policy'])
self.session_data.type='captcha'; self:header(); print(ngx.header['Content-Security-Policy'])
""")
    javascript, captcha = output.splitlines()
    assert "worker-src blob:" in javascript
    assert "worker-src" not in captcha
    assert "require-trusted-types-for 'script'" in javascript
    assert "'nonce-script'" in javascript


def test_setting_rejects_invalid_difficulty():
    settings = json.loads((PLUGIN / "plugin.json").read_text())["settings"]
    setting = settings["ANTIBOT_JAVASCRIPT_DIFFICULTY"]
    assert setting["default"] == "16"
    for value in range(16, 29):
        assert re.fullmatch(setting["regex"], str(value))
    for value in ("15", "29", "0", "-1", "16.0", "016", "17\n", "16oops"):
        assert not re.fullmatch(setting["regex"], value)


def test_form_carries_prefix_in_data_random():
    # The script reads the prefix from the DOM: a string literal lets the image minifier fold its .length to the placeholder's
    page = (PLUGIN / "files/javascript.html").read_text()
    form = re.search(r"<form\b[^>]*\bid=\"form\"[^>]*>", page, re.S).group()
    assert 'data-random="{*random*}"' in form


def test_all_locales_expose_setting():
    for path in (PLUGIN / "locales").glob("*.json"):
        translated = json.loads(path.read_text())["antibot"]["settings"]["ANTIBOT_JAVASCRIPT_DIFFICULTY"]
        assert translated["label"] and translated["help"], path
