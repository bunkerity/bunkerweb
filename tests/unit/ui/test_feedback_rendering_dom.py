"""Template feedback must pass scalar and list messages through safe DOM insertion.

Execute the complete editor module and utils helper, including the text-only fallback.
"""

import pytest
from _u2_helpers import node_runs_es_modules, run_dom

pytestmark = pytest.mark.skipif(not node_runs_es_modules(), reason="node 22.7 or newer is required")

PAYLOAD = '<img src=x onerror="alert(1)"><script>alert(2)</script>'

DRIVER = r"""
import fs from 'node:fs';
import vm from 'node:vm';
const feedback = makeNode('div');
registry['#template-form-feedback'] = [feedback];
const calls = [];
const context = vm.createContext({
  $: () => ({ ready() {} }), document,
  ...(scenario.sanitizer ? { DOMPurify: { sanitize(html, options) {
    calls.push({ html, options });
    return '<strong>sanitized</strong>';
  } } } : {}),
});
// Run the whole classic script; its unrelated document-ready callback remains queued.
vm.runInContext(fs.readFileSync(process.argv[2] + '/utils.js', 'utf8'), context);
globalThis.setInlineHtml = vm.runInContext('setInlineHtml', context);
// Expose the private entry point; preserve the full module body and resolve its dependency.
const source = fs.readFileSync(process.argv[2] + '/pages/template_edit.js', 'utf8')
  .replace('../modules/setting_controls.js', pathToFileURL(process.argv[2] + '/modules/setting_controls.js').href);
const moduleFile = new URL('./editor-under-test.mjs', import.meta.url);
fs.writeFileSync(moduleFile, source + '\nexport { showFeedback };\n');
const { showFeedback } = await import(moduleFile.href);
showFeedback('danger', scenario.list ? [scenario.payload, '<code>second</code>'] : scenario.payload);
console.log(JSON.stringify({ html: feedback.innerHTML, text: feedback.textContent, className: feedback.className, calls }));
"""


@pytest.mark.parametrize("as_list", [False, True])
@pytest.mark.parametrize("sanitizer", [False, True])
def test_feedback_scalar_and_list_use_safe_insertion(tmp_path, as_list, sanitizer):
    out = run_dom(tmp_path, DRIVER, {"payload": PAYLOAD, "list": as_list, "sanitizer": sanitizer})
    assert out["className"] == "alert alert-danger"
    if sanitizer:
        assert out["html"] == "<strong>sanitized</strong>"
        assert len(out["calls"]) == 1
        assert PAYLOAD in out["calls"][0]["html"]
        assert out["calls"][0]["options"]["ALLOWED_ATTR"] == ["class"]
        assert set(out["calls"][0]["options"]["ALLOWED_TAGS"]) == {"b", "br", "code", "em", "i", "li", "p", "span", "strong", "ul"}
    else:
        assert out["html"] == ""
        assert PAYLOAD in out["text"]
    if as_list:
        message = out["calls"][0]["html"] if sanitizer else out["text"]
        assert message == f'<ul class="mb-0"><li>{PAYLOAD}</li><li><code>second</code></li></ul>'
