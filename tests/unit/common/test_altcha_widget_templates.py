"""Exercise the rendered ALTCHA templates without a provider or an NGINX instance."""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from _t2_helpers import LUA, ROOT, SRC, lua_str

FILES = SRC / "common/core/antibot/files"
TEMPLATE_ENGINE = ROOT / "src/deps/src/lua-resty-template/lib/resty/template.lua"
pytestmark = pytest.mark.skipif(LUA is None, reason="Lua is required to render Antibot templates")


def render(name):
    path = FILES / name
    assert path.is_file(), f"Missing ALTCHA template {name}"
    result = subprocess.run(
        [LUA, "-"],
        input=f"""
local template = dofile({lua_str(TEMPLATE_ENGINE)})
io.write(template.process_file({lua_str(path)}, {{
    antibot_uri = '/verify-human', next = '/private?label="sale"&view=all',
    nonce_script = 'script-nonce', nonce_style = 'style-nonce',
    altcha_url = 'https://proof.example.test', altcha_sitekey = 'site-key',
}}))
""",
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return result.stdout


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.setdefault(tag, []).append(dict(attrs))


def test_parent_posts_only_the_proof_and_return_target():
    parent = Tags(render("altcha.html")).tags
    assert parent["form"] == [{"id": "form", "method": "post", "action": "/verify-human"}]
    assert {item["name"]: item.get("value") for item in parent["input"]} == {"altcha": None, "next": '/private?label="sale"&view=all'}
    assert parent["iframe"][0]["src"] == "/verify-human?altcha_frame=1"
    assert all("src" not in script for script in parent["script"])


def test_frame_loads_the_pinned_module_and_requires_interaction():
    frame = Tags(render("altcha_frame.html")).tags
    [module] = [item for item in frame["script"] if "src" in item]
    assert module["src"] == "https://proof.example.test/assets/altcha.min.js"
    assert module["nonce"] == "script-nonce"
    assert module["type"] == "module"
    assert module["crossorigin"] == "anonymous"
    assert module["integrity"] == "sha256-e69QzdV705NYI0HMtHvYK8CKR874cT1CNi8XN6O/LmY="
    [widget] = frame["altcha-widget"]
    assert widget["auto"] == "off"
    assert "disablerefetchonexpire" in widget


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required to execute the parent JavaScript")
def test_parent_rejects_untrusted_duplicate_and_late_proofs():
    [script] = re.findall(r"<script\b[^>]*>(.*?)</script>", render("altcha.html"), re.S)
    driver = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const script = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const origin = 'https://app.example.test';
const handlers = {};
const frameWindow = {};
const button = { addEventListener() {} };
const input = {};
const submissions = [];
const frame = { contentWindow: frameWindow, remove() { this.removed = true; } };
const elements = {
  'altcha-frame': frame,
  'challenge-error': {},
  'challenge-status': {},
  'challenge-retry': button,
  altcha: input,
  form: { submit() { submissions.push(input.value); } },
};
const window = { location: { origin }, addEventListener(name, handler) { handlers[name] = handler; } };
const document = { body: { dataset: {} }, getElementById(id) { return elements[id]; } };
let timeout;
const mount = () => vm.runInNewContext(script, { document, window, setTimeout(fn) { timeout = fn; }, clearTimeout() {} });
const message = (type, payload, overrides = {}) => handlers.message({
  origin, source: frameWindow, data: { channel: 'bw-altcha', type, payload }, ...overrides,
});
mount();
message('ready');
message('verified', 'early-proof');
message('solving');
message('verified', 'forged', { origin: 'https://other.example.test' });
message('verified', 'forged', { source: {} });
message('verified', 'forged', { data: { channel: 'unrelated', type: 'verified', payload: 'forged' } });
message('verified', '');
message('verified', 42);
assert.deepEqual(submissions, []);
message('verified', 'first-proof');
message('verified', 'duplicate-proof');
assert.deepEqual(submissions, ['first-proof']);

mount();
message('ready');
message('solving');
timeout();
assert.equal(frame.removed, true, 'A timed-out frame must stop its pending work');
assert.equal(button.hidden, false);
message('verified', 'late-proof');
assert.deepEqual(submissions, ['first-proof']);
"""
    subprocess.run(["node", "-e", driver], input=json.dumps(script), text=True, check=True, timeout=10)
