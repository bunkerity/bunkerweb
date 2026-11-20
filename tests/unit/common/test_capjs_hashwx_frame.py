"""Cap.js iframe must configure self-hosted hashwx before loading its widget.

Render through antibot's real template boundary and pair the widget URL with its CSP.
"""

import json
import re
import shutil
import subprocess

import pytest
from _lua_state_helpers import last_json, run_lua
from _t2_helpers import LUA, ROOT, SRC, lua_str, plugin_script

pytestmark = pytest.mark.skipif(LUA is None or shutil.which("node") is None, reason="lua and node are required")

CAP_URL = "https://proof.example.com/cap"


def test_frame_configures_self_hosted_wasm_before_widget_loading():
    header = f"""
local template = dofile({lua_str(ROOT / 'src/deps/src/lua-resty-template/lib/resty/template.lua')})
local frame_root = {lua_str(SRC / 'common/core/antibot/files')}
RENDERED = {{}}
function render_frame(name, variables)
    RENDERED = {{ name = name, html = template.process_file(frame_root .. '/' .. name, variables) }}
end
VARIABLES = {{ USE_ANTIBOT = "capjs", ANTIBOT_URI = "/challenge",
    ANTIBOT_CAPJS_FRONTEND_URL = {json.dumps(CAP_URL)}, ANTIBOT_CAPJS_SITEKEY = "site-key" }}
"""
    script = plugin_script(
        "antibot",
        r"""
ngx.var.arg_capjs_frame = "1"
local session = { prepared = true, type = "capjs", original_uri = "/page" }
local a = PLUGIN:new({ bw = { uri = "/challenge", scheme = "https",
    antibot_nonce_script = "script-nonce", antibot_nonce_style = "style-nonce",
    antibot_session_data = session, antibot_display_content = true } })
a.session_data = session
local ok, msg = a:display_challenge()
local result = a:header()
emit({ ok = ok, msg = msg, header_ok = result.ret, name = RENDERED.name,
    html = RENDERED.html, csp = ngx.header["Content-Security-Policy"] })
""",
        header=header,
    ).replace('package.loaded["resty.template"] = { render = function() end }', 'package.loaded["resty.template"] = { render = render_frame }')
    out = last_json(run_lua(script))
    assert out["ok"] is True and out["header_ok"] is True
    assert out["name"] == "capjs_frame.html"
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", out["html"], re.S)
    # Observe globals when the external widget loads, not after the document finished.
    driver = r"""
const vm = require('node:vm');
const scripts = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const window = {};
const context = vm.createContext({ window });
for (const [attrs, body] of scripts) {
  const src = attrs.match(/src="([^"]+)"/);
  if (src) {
    console.log(JSON.stringify({ src: src[1], globals: window, attrs }));
    break;
  }
  vm.runInContext(body, context);
}
"""
    done = subprocess.run(["node", "-e", driver], input=json.dumps(scripts), capture_output=True, text=True, timeout=10, check=True)
    widget = json.loads(done.stdout)
    assert widget["globals"].get("CAP_CUSTOM_HASHWX_URL") == CAP_URL + "/assets/hashwx.wasm"
    assert widget["globals"]["CAP_CUSTOM_WASM_URL"] == CAP_URL + "/assets/cap_wasm_bg.wasm"
    assert widget["src"] == CAP_URL + "/assets/widget.js"
    assert widget["globals"]["CAP_CSS_NONCE"] == "style-nonce"
    assert widget["globals"]["CAP_SCRIPT_NONCE"] == "script-nonce"
    assert 'nonce="script-nonce"' in widget["attrs"]
    csp = dict(part.strip().split(" ", 1) for part in out["csp"].split(";") if " " in part.strip())
    assert csp["connect-src"] == CAP_URL
    assert csp["script-src"] == f"'nonce-script-nonce' {CAP_URL} 'wasm-unsafe-eval' 'unsafe-eval'"
