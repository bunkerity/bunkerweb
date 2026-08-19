"""The browser-side translation runtime, after the client library was removed.

Until Lot D the page shipped in English and i18next rewrote it: a full-document `data-i18n` scan
once its catalog arrived, a `window.i18nextReady` flag every table had to poll before drawing, and
a re-translation pass for anything built afterwards. Templates are rendered translated now, so all
of that is gone and what is left is a `t()` over a catalog that is already in the document.

These tests pin the three properties that made the removal safe: the catalog really is loaded
first, the gate cannot come back, and `t()` still behaves the way the ~800 remaining call sites
expect it to — including the escaping, which is the one place where getting it wrong is a security
bug rather than a cosmetic one.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
STATIC_JS = ROOT / "src" / "ui" / "app" / "static" / "js"
I18N_JS = STATIC_JS / "i18n.js"
BASE_HTML = ROOT / "src" / "ui" / "app" / "templates" / "base.html"

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _runtime():
    """`i18n.js` down to the end of `t()` — everything above the parts that need jQuery and a DOM.

    Sliced rather than stubbed: the alternative is faking `$`, `document` and `localStorage` well
    enough for the file's `$(document).ready` tail to run, which tests the stubs more than the code.
    """
    source = I18N_JS.read_text(encoding="utf-8")
    return source[: source.index("// Plugin front-ends call")]


def _translate(catalog, call, language="en"):
    """Run one `t(...)` call in node against `catalog`, and return what the page would receive."""
    from json import dumps

    script = f"const window = {{ BW_I18N: {dumps(catalog)}, BW_LANG: {dumps(language)} }};\n{_runtime()}\nprocess.stdout.write(String({call}));"
    result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


@needs_node
def test_i18n_runtime_parses():
    assert subprocess.run(["node", "--check", str(I18N_JS)], capture_output=True).returncode == 0


def test_the_catalog_is_loaded_before_the_runtime_that_reads_it():
    """`t()` is synchronous, which is only true because the catalog is already a global by the
    time any script asks. Reorder these two tags and every lookup silently answers with its key."""
    markup = BASE_HTML.read_text(encoding="utf-8")

    catalog = markup.index("url_for('i18n_catalog'")
    runtime = markup.index("filename='js/i18n.js'")
    page_scripts = markup.index("{% block scripts %}")

    assert catalog < runtime < page_scripts


def test_the_client_side_library_is_gone():
    """Three scripts, 57 KB, fetching a catalog the server can hand over in the page's own
    document order. Nothing should reintroduce them."""
    markup = BASE_HTML.read_text(encoding="utf-8")

    assert "libs/i18next" not in markup
    assert not (ROOT / "src" / "ui" / "app" / "static" / "libs" / "i18next").exists()


def test_no_script_waits_on_a_readiness_flag_any_more():
    """`window.i18nextReady` existed because the catalog arrived over XHR. Nine page scripts
    polled it every 50 ms before initialising their table; one more added would be a table that
    never draws, since nothing sets the flag now."""
    offenders = sorted(path.relative_to(ROOT).as_posix() for path in STATIC_JS.rglob("*.js") if "i18nextReady" in path.read_text(encoding="utf-8"))

    assert not offenders, f"still polling a flag nothing sets: {offenders}"


def test_the_compatibility_shim_covers_what_the_call_sites_still_use():
    """`i18next.t` is a plugin-facing surface — core `letsencrypt` calls it, external plugins may —
    and a dozen call sites in this tree still guard on `isInitialized` or subscribe to
    `languageChanged`. Dropping any of these from the shim breaks them silently: the guard just
    takes its English-fallback branch."""
    source = I18N_JS.read_text(encoding="utf-8")

    for member in ("t: t", "language: currentLanguage", "isInitialized: true", "on: () => {}", "off: () => {}"):
        assert member in source, f"the i18next shim no longer exposes `{member}`"


@needs_node
def test_a_known_key_resolves_through_the_nested_catalog():
    """The catalog is served nested, exactly as the JSON is stored, so `t()` walks the dots."""
    assert _translate({"button": {"save": "Save"}}, 't("button.save")') == "Save"


@needs_node
def test_a_missing_key_falls_back_the_way_gettext_does():
    """First `defaultValue`, then the key itself. A raw dotted key in the page is the signal that
    the catalog is missing it — the same signal the server side gives."""
    assert _translate({}, 't("button.save", "Save")') == "Save"
    assert _translate({}, 't("button.save", { defaultValue: "Save" })') == "Save"
    assert _translate({}, 't("button.save")') == "button.save"


@needs_node
def test_interpolated_values_are_escaped_by_default():
    """i18next escaped interpolated values and several call sites drop the result straight into
    HTML — `redirects.js` interpolates service names, `settings-raw.js` a setting method. Losing
    the escaping here turns a service name into stored XSS."""
    rendered = _translate({"msg": "Attached to {{services}}"}, 't("msg", { services: "<img src=x onerror=alert(1)>" })')

    assert "<img" not in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered


@needs_node
def test_escaping_can_be_waived_the_way_i18next_waived_it():
    """`{ interpolation: { escapeValue: false } }` is i18next's own opt-out, used where the value
    is markup the caller built itself."""
    rendered = _translate(
        {"msg": "See {{link}}"},
        't("msg", { link: "<a href=\\"/x\\">x</a>", interpolation: { escapeValue: false } })',
    )

    assert rendered == 'See <a href="/x">x</a>'


@needs_node
def test_the_three_argument_form_still_interpolates():
    """`t(key, fallback, options)` is i18next's third signature and the one the DataTables
    `infoCallback` uses to pass start/end/total. Treat the third argument as noise and every
    table's footer reads "Showing {{start}} to {{end}} of {{total}}" — with no error anywhere."""
    rendered = _translate(
        {"datatable": {"info_services": "Showing {{start}} to {{end}} of {{total}} Services"}},
        't("datatable.info_services", "Showing 1 to 10 of 501 entries", { start: 1, end: 10, total: 501 })',
    )

    assert rendered == "Showing 1 to 10 of 501 Services"


@needs_node
def test_the_three_argument_form_falls_back_with_its_variables():
    """A missing key has to interpolate the *fallback*, not hand back a string full of braces."""
    rendered = _translate({}, 't("datatable.info_x", "Showing {{start}} of {{total}}", { start: 1, total: 9 })')

    assert rendered == "Showing 1 of 9"


@needs_node
def test_a_placeholder_with_no_value_is_left_alone():
    """Blanking it would silently drop a sentence's subject; leaving `{{name}}` visible at least
    names the variable that was not passed."""
    assert _translate({"msg": "Hello {{name}}"}, 't("msg")') == "Hello {{name}}"


def test_every_data_i18n_scan_skips_an_empty_key():
    """`[data-i18n]` matches an element whose key is the empty string, and translating one blanks
    whatever text is already there.

    That is not hypothetical: DataTables' `colvis` builds each item as
    `${idx + 1}. <span data-i18n="${i18nKey || ""}">${title}</span>`, and since Lot B/C the table
    headers are rendered translated and carry no key to read back — so the attribute is always
    empty. The collection re-translation pass then replaced every label with `t("")`, leaving the
    Columns dropdown showing "4." "5." "6." and nothing else, on every page with a table. Silent:
    the control still opened, and nothing reached the console.

    Static rather than a render because these three scans live inside `$(document).ready` behind
    jQuery, a DOM and DataTables; what needs pinning is one line of policy, and a scan that grows a
    fourth call site is exactly the case a test should catch.
    """
    lines = I18N_JS.read_text(encoding="utf-8").splitlines()
    # Comments stripped first: the check is about the code that follows a read, and one of these
    # sites carries a five-line comment that would otherwise push the guard out of the window.
    code = [line for line in lines if not line.strip().startswith("//")]
    source = "\n".join(code)
    reads = [index for index in range(len(source)) if source.startswith('.attr("data-i18n")', index)]

    assert len(reads) >= 3, "the scans moved; this test is looking at the wrong thing"

    unguarded = [source[:index].count("\n") + 1 for index in reads if "if (!key) return;" not in source[index : index + 200]]  # noqa: E203

    assert not unguarded, f"a `data-i18n` scan (comment-stripped line {unguarded}) would blank an element whose key is empty"
