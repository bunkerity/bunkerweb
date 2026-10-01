"""M21: the multivalue helper's separator note must not always be English.

`setting_controls.js:renderMultivalue` used to splice a hard-coded English fragment
(`' Will be joined with "${separator}".'`) into the (correctly translated) outer sentence, so a
French page read "Une valeur par ligne. Will be joined with...". The fix routes the fragment
through its own catalog key (`template.editor.multivalue_helper_joined`) first, then
interpolates the *translated* result into the outer sentence -- both calls run with
`interpolation: { escapeValue: false }`, since the target is `textContent`, not HTML, and
escaping the `"` around the separator produced a literal `&quot;` on screen (a pre-existing
defect on the same two lines, fixed alongside).

Runs the real module end to end (import, not a source-text scan): the defect is in the runtime
composition of two translate() calls, which only a real call proves.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js"
MODULE = JS / "modules" / "setting_controls.js"
I18N_JS = JS / "i18n.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

# The two keys this fix touches, minimally reproduced -- not the full catalog.
CATALOGS = {
    "en": {
        "template": {
            "editor": {
                "multivalue_helper": "One value per line.",
                "multivalue_helper_joined": 'One value per line. Will be joined with "{{separator}}".',
            }
        }
    },
    "fr": {
        "template": {
            "editor": {
                "multivalue_helper": "Une valeur par ligne.",
                "multivalue_helper_joined": "Une valeur par ligne. Sera joint avec « {{separator}} ».",
            }
        }
    },
}


def _fake_dom_prelude():
    """A generic no-op element: `renderMultivalue` calls a couple dozen DOM methods this test
    does not care about (append, addEventListener, querySelector, ...); only `textContent` and
    `className` are read back, as plain settable properties like the real DOM gives them."""
    return """
      function makeElement() {
        return {
          _attrs: {},
          children: [],
          setAttribute(k, v) { this._attrs[k] = v; },
          removeAttribute(k) { delete this._attrs[k]; },
          append() {},
          appendChild() {},
          addEventListener() {},
          querySelector() { return null; },
          querySelectorAll() { return []; },
          remove() {},
          focus() {},
        };
      }
      globalThis.document = { createElement: () => makeElement() };
    """


def _render_helper_text(lang, separator):
    """Build a real `SettingControl` for a `multivalue` entry with the given separator, backed by
    the real `t()` (sliced from `i18n.js`, same technique as `test_i18n_attributes.py`), and
    return the rendered helper `<small>`'s `textContent`."""
    i18n_runtime = I18N_JS.read_text(encoding="utf-8")
    i18n_runtime = i18n_runtime[: i18n_runtime.index("// Plugin front-ends call")]

    # `renderMultivalue` appends [list, addButton, helper] to `this.root` via one `.append(...)`
    # call -- the fake `append` above is a no-op, so capture the helper element directly instead
    # of walking a tree the fake never builds. Simplest correct hook: intercept `root.append`.
    script = f"""
    const window = {{ BW_I18N: {json.dumps(CATALOGS[lang])}, BW_LANG: {json.dumps(lang)} }};
    {i18n_runtime}
    {_fake_dom_prelude()}
    const {{ createSettingControl }} = await import({json.dumps(MODULE.as_uri())});
    let captured = null;
    const control = createSettingControl({{
      entry: {{ type: "multivalue", separator: {json.dumps(separator)} }},
      value: "a{separator}b",
      translate: t,
    }});
    control.root.append = (...children) => {{ captured = children; }};
    control.renderMultivalue("a{separator}b");
    process.stdout.write(JSON.stringify(captured[2].textContent));
    """
    result = subprocess.run(["node", "--input-type=module"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_english_separator_note_has_no_escaped_quotes():
    text = _render_helper_text("en", ",")

    assert text == 'One value per line. Will be joined with ",".'
    assert "&quot;" not in text


@needs_node
def test_french_page_gets_a_fully_french_sentence():
    """The bug: the note used to stay English here regardless of locale."""
    text = _render_helper_text("fr", ",")

    assert text == "Une valeur par ligne. Sera joint avec « , »."
    assert "Will be joined with" not in text


@needs_node
def test_the_default_space_separator_still_gets_a_note():
    """`renderMultivalue` falls back to `" "` for an unset `entry.separator`
    (`this.entry?.separator || " "`), which is always truthy -- so the note is not skippable
    through the public entry shape this control is built from, only through a falsy `separator`
    reaching the ternary directly, which never happens here. Pinned so a future refactor that
    changes that fallback default notices this note along with it."""
    text = _render_helper_text("en", " ")

    assert text == 'One value per line. Will be joined with " ".'
