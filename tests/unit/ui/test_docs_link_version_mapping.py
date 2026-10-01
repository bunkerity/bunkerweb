"""M26 (FIX-D addendum): pre-release version strings must never reach a docs.bunkerweb.io link.

`templates/macros/docs_link.html`'s `docs_url` macro (FIX-H) maps a falsy, "dev", "testing" or
`~`-containing `bw_version` to "latest" instead of building a 404 -- alpha/rc docs are hidden by
design and a beta/dev build has usually not been through the release pipeline yet. `i18n.js`'s
`updateDocumentationLinks()` rewrites the same `.docs-link` hrefs client-side on every language
switch, from `window.bw_version` directly, with no such mapping: switching language while running
a pre-release build silently changed every "Documentation" link right back to a 404, undoing the
macro's server-side fix on the very first client-side rewrite.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

I18N_JS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "i18n.js"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _runtime():
    """`i18n.js` up to (not including) the DOM-ready tail, which would execute immediately and
    needs a real document. `updateDocumentationLinks` sits above that line; the one module-load
    DOM access above it (`document.getElementById` for the supported-languages textarea) is
    already wrapped in its own try/catch and degrades to an empty list without a `document`."""
    source = I18N_JS.read_text(encoding="utf-8")
    return source[: source.index("$(document).ready(function () {")]


def _update_links(bw_version, links):
    """Run the real `updateDocumentationLinks("en")` in node against a minimal jQuery stub, and
    return each link's rewritten href."""
    fake_jquery = """
      const __links = %s.map((l) => ({ data: { ...l }, href: null }));
      // The real code does `$(".docs-link").each(function () { const $link = $(this); ... })`
      // -- `this` inside the callback is the raw element, re-wrapped by a second `$()` call, so
      // this fake has to handle both the selector form and the single-element form.
      function $(selector) {
        if (selector === "body") return { data: () => undefined };
        if (selector === ".docs-link") {
          return {
            each(cb) {
              __links.forEach((link, i) => cb.call(link, i, link));
            },
          };
        }
        const element = selector;
        return {
          data: (key) => element.data[key],
          attr: (key, value) => { element.href = value; return this; },
        };
      }
    """ % json.dumps(links)
    script = (
        f"const window = {{ bw_version: {json.dumps(bw_version)} }};\n"
        f"{fake_jquery}\n{_runtime()}\n"
        'updateDocumentationLinks("en");\n'
        "process.stdout.write(JSON.stringify(__links.map((l) => l.href)));"
    )
    result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
@pytest.mark.parametrize("bw_version", ["1.7.0~beta", "1.7.0~alpha", "dev", "testing", "", None])
def test_a_pre_release_or_unresolved_version_falls_back_to_latest(bw_version):
    hrefs = _update_links(bw_version, [{"endpoint": "/troubleshooting", "fragment": ""}])

    assert hrefs == ["https://docs.bunkerweb.io/latest/troubleshooting/?utm_campaign=self&utm_source=ui"]


@needs_node
def test_a_real_released_version_is_used_as_is():
    hrefs = _update_links("1.6.14", [{"endpoint": "/troubleshooting", "fragment": ""}])

    assert hrefs == ["https://docs.bunkerweb.io/1.6.14/troubleshooting/?utm_campaign=self&utm_source=ui"]
