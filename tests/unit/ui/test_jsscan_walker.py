"""The walker the JavaScript guards are built on, tested on sources written to break it.

`_jsscan.py` is shared infrastructure: `test_page_script_reachability.py` and
`test_t_placeholders.py` both read the tree through it, and both would pass silently if it stopped
recognising anything. Testing it by reintroducing a defect into a real page script only proves it
still works on that one file — these cases aim at the four constructs that make naive scanning wrong.

The manager's independent review of the walker used exactly this approach and found it sound; the
cases are written down here so the next change to the walker has to survive them too.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _jsscan import Source, object_keys, split_arguments, string_value  # noqa: E402


def _returns_at_top_level(source):
    depths = Source(source).depth_by_line
    return [number for number, text in enumerate(source.splitlines(), 1) if depths.get(number) == 1 and text.strip().startswith("return")]


def test_a_top_level_return_is_found_at_its_own_line():
    source = "$(document).ready(function () {\n  const dt = init();\n  return dt;\n  bind();\n});\n"

    assert _returns_at_top_level(source) == [3]


def test_a_return_inside_a_nested_function_is_not_top_level():
    """The distinction the whole reachability guard rests on: `return` in a helper is how helpers
    work, `return` in the callback body is what kills the statements after it."""
    source = "$(document).ready(function () {\n  function helper() {\n    return 1;\n  }\n  bind();\n});\n"

    assert _returns_at_top_level(source) == []
    assert Source(source).depth_by_line[3] == 2


def test_a_return_written_inside_quotes_or_comments_is_text():
    source = (
        "$(document).ready(function () {\n"
        "  const template = `\n"
        "  return dt;\n"
        "`;\n"
        '  const quoted = "  return dt;";\n'
        "  // return dt;\n"
        "  /*\n"
        "  return dt;\n"
        "  */\n"
        "  bind();\n"
        "});\n"
    )

    assert _returns_at_top_level(source) == []


def test_a_regex_literal_full_of_braces_does_not_skew_the_depth():
    """`/{.*}/` is three braces to a scanner that does not know it is inside a regex, and every
    depth after it would be wrong — which would silently disarm the guard rather than fail it."""
    source = "$(document).ready(function () {\n  const re = /^{.*}$/g;\n  return dt;\n});\n"

    assert _returns_at_top_level(source) == [3]


def test_division_is_not_mistaken_for_a_regex():
    """The other direction: treating `/` after a value as opening a regex would swallow the rest of
    the line, and with it any call site on it."""
    source = '$(document).ready(function () {\n  const half = total / 2;\n  const label = t("x.y");\n});\n'

    assert [line for line, _ in Source(source).t_calls] == [3]


def test_a_keyword_before_the_call_does_not_hide_it():
    """The gap that hid six live call sites, and the reason it hid them.

    Recognition used to test the last *non-whitespace* character before `t`. After a keyword that is
    `n`, `t`, `f`, `d`, `e` — alphanumeric — so `return t(...)` read as a continuation of an
    identifier and the call was silently not a call. `test_t_placeholders.py` therefore never
    checked `dataTableInit.js:271`, `:276`, `reports-overview.js:50`, `reports.js:1686`, or
    `service-resources.js:147`, `:155`: a missing interpolation variable in any of them would have
    shipped exactly the way the unban tooltip did.

    A `return` inside a nested function was already covered and did not catch this — that case tests
    the depth path, not the call-recognition path.
    """
    for keyword in ("return", "await", "typeof", "void"):
        source = f'function f() {{ {keyword} t("some.key", "fallback"); }}'

        assert len(Source(source).t_calls) == 1, f"`{keyword} t(...)` is not recognised as a call"

    assert len(Source('switch (x) { case t("some.key"): break; }').t_calls) == 1


def test_a_dotted_call_is_still_skipped_and_for_a_different_reason():
    """`window.t(...)` and `obj.t(...)` really are out of scope: `.` continues an identifier, so the
    name there is `window.t`, not `t`. Widening for keywords must not widen for these. The vendored
    `buttons.js` was the concrete reason — its own `t` was `window.Math` — and although that file is
    gone, the identifier rule is what the assertion actually rests on."""
    for source in ('window.t("some.key");', 'obj.t("some.key");', 'this.t("some.key", "f");'):
        assert Source(source).t_calls == [], f"{source} must not be read as a bare t() call"


def test_an_injected_translator_is_a_call_site_when_it_is_named_translate():
    """`setting_controls.js` takes its translator in the constructor and calls
    `this.translate(key, fallback, options)` — same signature as `t()`, reached through a property.
    Recognising it is what let those call sites be migrated normally instead of allowlisted.

    The name is the whole rule: `.translate(` is recognised, `.t(` is not. They are not the same
    decision — the vendored `buttons.js` had `t = window.Math` at line 10, so a `.t(` there was
    arithmetic. That file has since been deleted; the distinction it illustrated has not."""
    assert Source('this.translate("some.key", "f");').t_calls == [(1, '"some.key", "f"')]
    assert Source('this.t("some.key", "f");').t_calls == []


def test_only_the_translation_helper_counts_as_a_call_site():
    """`Event(`, `parseInt(`, `.at(` all end in `t(` and there are far more of them in these files
    than there are real calls."""
    source = 'el.dispatchEvent(new Event("change"));\nconst n = parseInt("3");\nconst s = t("a.b");\nconst u = obj.t("c.d");\n'

    lines = [line for line, _ in Source(source).t_calls]

    assert lines == [3], f"expected only the bare `t(` call, got lines {lines}"


# --------------------------------------------------------------------------------------
# Adversarial audit, 2026-08-19. Everything below is here because the walker is load-bearing for
# four guards and the one hole we found — `return t(...)` — was found by accident rather than by
# looking. The cases that pass are kept alongside the ones that found bugs: a case is worth as much
# for pinning behaviour as for having caught something.
# --------------------------------------------------------------------------------------


def test_a_regex_after_a_keyword_is_a_regex_and_not_division():
    """`bans.js:1450` is `return /:/.test(v)`, and it corrupted the rest of the file.

    The `/` follows a letter, so it read as division; its closing `/` then followed a `:`, which
    *is* a value position, so that one opened a "regex" — which ran to the end of the line and
    consumed the newline without counting it. Every line after it was numbered one too low, which
    means `test_page_script_reachability` was reading the wrong lines of the very file it was
    written for.

    The check is equivalence with a regex-free control rather than absolute depths: what matters is
    that a regex costs the walker nothing, not what the numbers happen to be.
    """
    control = "function f(v) {\n  return v;\n}\nfunction g() {\n  return 1;\n}\n"
    with_regex = "function f(v) {\n  return /:/.test(v);\n}\nfunction g() {\n  return 1;\n}\n"

    assert Source(with_regex).depth_by_line == Source(control).depth_by_line
    assert max(Source(with_regex).depth_by_line) == 6, "a line was consumed without being counted"

    # The assertion above is satisfied by the newline fix alone, so it does not pin *this* rule.
    # These do: read as division, the brace and the quote inside the pattern become code, and both
    # corrupt everything after them — a brace shifts every later depth, a quote swallows the file.
    # `/['"]/` and `/[{}]/` are ordinary things to write.
    brace = "function f(x) {\n  return /{/.test(x);\n}\nconst after = 1;\n"
    quote = "function f(x) {\n  return /'/.test(x);\n}\nconst after = 1;\n"

    assert Source(brace).depth_by_line[4] == 0, "a brace inside the pattern was counted as a block"
    assert Source(quote).depth_by_line.get(4) == 0, "a quote inside the pattern opened a string"


def test_a_regex_never_consumes_the_newline_that_ends_its_line():
    """The safety net under the case above: even when the heuristic guesses wrong, losing a line is
    what turns a local mis-parse into a whole-file renumbering."""
    # `= /` really does enter the regex scanner, so this exercises it; `x / y` would not, and a
    # test that never reaches the code it names is not a test.
    source = "const a = /x;\nconst b = 1;\nconst c = 2;\n"

    assert max(Source(source).depth_by_line) == 3, "the unterminated pattern ate the line that ended it"


def test_division_is_still_division_after_a_value():
    for source in ("const a = b / c / d;", "x = y/2/z;", "const r = (a) / 2;"):
        assert Source(source).depth_by_line == {1: 0}, source


def test_a_string_boundary_survives_escapes():
    for source in ('const a = "x\\\\"; t("k", "f");', 'const a = "x\\"y"; t("k", "f");', 'const a = \'it\\\'s\'; t("k", "f");'):
        assert len(Source(source).t_calls) == 1, source


def test_a_regex_holding_a_slash_in_a_character_class_is_not_cut_short():
    assert len(Source('const re = /[/]{2}/; t("k", "f");').t_calls) == 1


# --------------------------------------------------------------------------------------
# Template substitutions are code. Added when the walker learned to descend into `${...}`:
# skipping them whole hid 120 `t()` call sites across 10 files from the key and placeholder
# checks, and hid two live defects — an untranslated read-only tooltip on `/services`, and a
# `/plugins` tooltip rendering `{{action}}` literally.
# --------------------------------------------------------------------------------------


def test_a_call_inside_a_substitution_is_a_call():
    assert Source('const s = `a ${t("k", "f")} b`;').t_calls == [(1, '"k", "f"')]


def test_the_text_around_a_substitution_is_still_text():
    """The point of descending is the code in `${}`, not the prose around it: a `t(` written in
    the literal's text is characters in a string, and a `{` there must not move the depth."""
    source = Source('const s = `t("no") { ${t("yes", "F")} } t("no")`;')

    assert source.t_calls == [(1, '"yes", "F"')]
    assert source.depth_by_line == {1: 0}


def test_a_substitution_brace_neither_opens_a_block_nor_takes_a_line_with_it():
    """`${` and its `}` are delimiters, not braces. Counting them would shift the depth of every
    line after the literal, which is what `test_page_script_reachability` reads."""
    control = "function f() {\n  const a = 1;\n  return a;\n}\nconst after = 2;\n"
    with_template = "function f() {\n  const a = `x ${1 + 1} y`;\n  return a;\n}\nconst after = 2;\n"

    assert Source(with_template).depth_by_line == Source(control).depth_by_line


def test_a_block_inside_a_substitution_still_counts():
    """The opposite error: treating everything up to the *first* `}` as the substitution. An object
    literal or a function body inside `${}` closes its own braces first."""
    source = Source('const s = `${JSON.stringify({ a: 1 })} ${t("k", "F")}`;\nconst after = 1;\n')

    assert source.t_calls == [(1, '"k", "F"')]
    assert source.depth_by_line == {1: 0, 2: 0}


def test_a_template_nested_in_a_substitution_is_walked_too():
    """`` `a${`b${t("k")}`}c` `` — the inner literal opens inside the outer one's substitution."""
    source = Source('const s = `a ${cond ? `b ${t("k", "F")}` : ""} c`;')

    assert source.t_calls == [(1, '"k", "F"')]


def test_a_nested_template_does_not_end_the_outer_one():
    """The defect this fixed, and it was live: `helpers.js:21` is

        throw new Error(`Parameter required${name ? `: \\`${name}\\`` : ""}`);

    a nested literal *containing escaped backticks*. Stopping the outer literal at the inner
    backtick desynchronised the rest of the file: three literals at lines 165, 191 and 661 were
    invisible to `test_untranslated_js_literals` because the walker thought they were inside a
    string. Every character after such a literal is at stake, not just the literal itself.
    """
    source = Source('const s = `a${name ? `: \\`t("no", "F")\\`` : ""}`;\nt("after", "F");\n')

    assert source.t_calls == [(2, '"after", "F"')], "an escaped backtick ended the inner literal"
    assert source.depth_by_line == {1: 0, 2: 0}


def test_an_unbalanced_brace_in_template_text_does_not_open_a_substitution():
    """Only `${` opens one. A lone `{` in the text — CSS in a style block, a JSON example — must
    not put the walker into code mode for the rest of the file."""
    source = Source('const s = `.a { content: t("no", "F"); }`;\nt("yes", "F");\n')

    assert source.t_calls == [(2, '"yes", "F"')], "a lone brace put the walker into code mode"
    assert source.depth_by_line == {1: 0, 2: 0}


def test_a_backtick_in_a_substitution_keeps_the_argument_list_balanced():
    """`_balanced` and `split_arguments` skip a template whole rather than descending, so they need
    the same nesting rule: the inner backtick must not be read as the outer literal's end."""
    call = Source('t("k", `a ${x ? `y (z` : ""} b`, {count: 1});').t_calls[0]

    assert split_arguments(call[1]) == ['"k"', '`a ${x ? `y (z` : ""} b`', "{count: 1}"]


# --------------------------------------------------------------------------------------
# Known limitations. These assert what the walker *does*, not what a parser would do, so that
# changing any of them has to be a decision rather than a side effect. Each was checked against the
# tree: none hides a defect today.
# --------------------------------------------------------------------------------------


def test_a_comment_inside_an_argument_list_truncates_it():
    """`_balanced` skips strings but not comments, so a `)` in a comment closes the call early.

    Scanned the tree: no `t(...)` call has a comment between its parentheses today.
    """
    call = Source('t(\n  "k", // note )\n  "f",\n);')

    assert split_arguments(call.t_calls[0][1]) == ['"k"', "// note"]


def test_modern_call_forms_are_not_recognised():
    """`t?.("k")`, `(0, t)("k")` and `t.call(null, "k")` are all real ways to call the helper and
    none is seen. None appears in the tree. The only `t.apply` sites were in the vendored
    `buttons.js`, and were that library's own `t` (`window.Math`) rather than a translator; that
    file has since been deleted, so the tree now has none at all."""
    for source in ('const a = t?.("k", "f");', 'const a = (0, t)("k", "f");', 'const a = t.call(null, "k");'):
        assert Source(source).t_calls == [], source


def test_a_literal_with_an_escaped_quote_is_returned_raw():
    """`string_value` does not unescape, so such a key or fallback would not match the catalog.
    No `t()` argument in the tree contains an escaped quote."""
    assert string_value('"a\\"b"') == 'a\\"b'


def test_object_keys_refuses_what_it_cannot_read():
    """Shorthand methods and accessors are `None` — unknown, never empty — so a call using them is
    skipped rather than reported as passing no variables."""
    assert object_keys("{ foo() { return 1 } }") is None
    assert object_keys("{ get x() { return 1 } }") is None
    assert object_keys("{ a: 1, }") == {"a"}
    assert object_keys('{ "a.b": 1 }') == {"a.b"}
    assert object_keys("{ a: b ? 1 : 2 }") == {"a"}
    assert object_keys("{ a: `x,y` }") == {"a"}


def test_arguments_are_split_on_top_level_commas_only():
    assert split_arguments('"a.b", { x: 1, y: f(2, 3) }, opts') == ['"a.b"', "{ x: 1, y: f(2, 3) }", "opts"]
    assert split_arguments('"a, b"') == ['"a, b"'], "a comma inside a string is not a separator"


def test_string_values_are_read_and_non_strings_refused():
    assert string_value('"some.key"') == "some.key"
    assert string_value("'some.key'") == "some.key"
    assert string_value("`template`") is None
    assert string_value("variableName") is None


def test_unknown_object_keys_are_none_and_never_an_empty_set():
    """The distinction that decides whether the placeholder guard reports or stays quiet: an empty
    set means "this call passes nothing" and produces a finding, `None` means "cannot tell" and
    skips. A spread could supply anything, so reading it as empty would invent failures."""
    assert object_keys("{ start, end }") == {"start", "end"}
    assert object_keys('{ "count": 3, defaultValue: "x" }') == {"count", "defaultValue"}
    assert object_keys("{}") == set()
    assert object_keys("{ ...values }") is None, "a spread supplies unknown keys"
    assert object_keys("{ [computed]: 1 }") is None, "a computed key is unknown"
    assert object_keys("someVariable") is None, "not an object literal at all"
