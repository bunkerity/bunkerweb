"""User data must reach the settings editors and the template editor as text, never as markup.

Port of the client-side half of dev acb6b8804. The server half already exists: `app.utils.flash()`
escapes every message that is not `Markup` (`test_flash_escaping.py`). What was left:

* `|safe` on values a user controls -- a custom config body in a `<textarea>` (a `</textarea>`
  inside it closes the element and the rest runs as page markup), the session's user-agent
  fields on the profile page;
* `template_edit.js` writing config and file names, and server messages that echo a template id,
  into `innerHTML`.

The JS cannot run here without a DOM (`template_edit.js` is an ES module that needs the whole
editor page), so the page script is read statically, as `_jsscan.py` documents, and the one new
helper in `utils.js` is executed through node with a stub `DOMPurify`.
"""

import re
from json import loads
from pathlib import Path
from shutil import which
from subprocess import run

import pytest
from jinja2 import Environment, nodes

ROOT = Path(__file__).resolve().parents[3]
UI = ROOT / "src" / "ui" / "app"
TEMPLATES = UI / "templates"
UTILS_JS = UI / "static" / "js" / "utils.js"
TEMPLATE_EDIT_JS = UI / "static" / "js" / "pages" / "template_edit.js"
PAYLOAD = "<img src=x onerror=alert(1)>"

# `plugins_settings_easy.html` of dev is `template_steps_body.html` in 1.7 (no separate file).
# template -> names whose value a user controls and which therefore may never go through `|safe`.
USER_DATA = {
    "models/template_steps_body.html": {"step_config_value"},
    "models/plugins_settings_raw.html": {"raw_config"},
    "profile.html": {"browser", "os", "device"},
}


def _safe_filter_operands(template: str):
    """Every `<expr>|safe` in the template, as the source of what it marks safe."""
    tree = Environment().parse((TEMPLATES / template).read_text(encoding="utf-8"))
    for node in tree.find_all(nodes.Filter):
        if node.name != "safe" or node.node is None:
            continue
        operand = node.node
        if isinstance(operand, nodes.Name):
            yield operand.name
        elif isinstance(operand, nodes.Getitem) and isinstance(operand.arg, nodes.Const):
            yield str(operand.arg.value)
        else:
            yield type(operand).__name__


@pytest.mark.parametrize("template", sorted(USER_DATA))
def test_user_controlled_values_are_not_marked_safe(template):
    marked = set(_safe_filter_operands(template)) & USER_DATA[template]
    assert marked == set(), f"{template}: |safe on user data {sorted(marked)}"


def test_a_textarea_cannot_be_closed_by_the_config_it_holds():
    """What dropping `|safe` buys: the stored body is entity-escaped inside the textarea."""
    body = f"</textarea>{PAYLOAD}"
    env = Environment(autoescape=True)
    html = env.from_string("<textarea>{{- value -}}</textarea>").render(value=body)
    assert PAYLOAD not in html
    assert "&lt;/textarea&gt;&lt;img" in html
    unsafe = env.from_string("<textarea>{{- value|safe -}}</textarea>").render(value=body)
    assert PAYLOAD in unsafe  # the pre-fix rendering the tests above forbid


# ---- template_edit.js ----------------------------------------------------------------------------

_INNERHTML_WITH_DATA = re.compile(r"\.innerHTML\s*=\s*`[^`]*\$\{\s*(name|type|config)\s*\}", re.DOTALL)


def test_template_editor_builds_name_and_type_rows_with_text_nodes():
    source = TEMPLATE_EDIT_JS.read_text(encoding="utf-8")
    hits = [source.count("\n", 0, m.start()) + 1 for m in _INNERHTML_WITH_DATA.finditer(source)]
    assert hits == [], f"template_edit.js writes file or config names into innerHTML at lines {hits}"


def test_template_editor_feedback_goes_through_the_sanitiser():
    source = TEMPLATE_EDIT_JS.read_text(encoding="utf-8")
    body = source[source.index("const showFeedback = ") :]
    body = body[: body.index("\n};")]
    assert ".innerHTML" not in body, "showFeedback assigns server and user text to innerHTML directly"
    assert "setInlineHtml(" in body


# ---- utils.js helper -----------------------------------------------------------------------------

HARNESS = r"""
const fs = require("fs");
const source = fs.readFileSync(process.argv[2], "utf8");
const start = source.indexOf("const INLINE_ALLOWED_TAGS");
if (start === -1) { process.stdout.write(JSON.stringify({ missing: true })); process.exit(0); }
const end = source.indexOf("\nfunction throttle");
const seen = {};
globalThis.DOMPurify = process.argv[3] === "absent" ? undefined : {
  sanitize(html, config) { seen.config = config; return html; },
};
eval(source.slice(start, end) + "; globalThis.setInlineHtml = setInlineHtml; globalThis.tags = INLINE_ALLOWED_TAGS;");
const element = {};
setInlineHtml(element, process.argv[4]);
process.stdout.write(JSON.stringify({ element, seen, tags: globalThis.tags }));
"""


def _run_helper(mode: str, tmp_path):
    node = which("node")
    if node is None:
        pytest.skip("node is not installed")
    script = tmp_path / "harness.js"
    script.write_text(HARNESS, encoding="utf-8")
    out = run([node, str(script), str(UTILS_JS), mode, PAYLOAD], capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    return loads(out.stdout)


def test_helper_exists_and_never_allows_active_or_embedding_tags(tmp_path):
    result = _run_helper("present", tmp_path)
    assert not result.get("missing"), "utils.js has no setInlineHtml helper"
    assert result["element"]["innerHTML"] == PAYLOAD  # stub sanitiser is the identity
    allowed = set(result["seen"]["config"]["ALLOWED_TAGS"])
    assert not allowed & {"img", "script", "iframe", "svg", "object", "form", "style"}
    assert "on" not in "".join(result["seen"]["config"].get("ALLOWED_ATTR", []))


def test_helper_falls_back_to_text_when_dompurify_is_missing(tmp_path):
    result = _run_helper("absent", tmp_path)
    assert result["element"] == {"textContent": PAYLOAD}
