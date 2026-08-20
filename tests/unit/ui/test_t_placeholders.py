"""A `t()` call must pass every variable its message interpolates, or the placeholder ships as text.

`test_gettext_placeholders.py` guards the same rule on the Jinja side, where breaking it raises
`KeyError` and returns a 500. JavaScript has the identical exposure and the opposite symptom, which
is why it needed its own guard: `t()` leaves an unsupplied placeholder **exactly as written** —

    settings[name] === undefined ? placeholder : escapeValue(settings[name])

No exception, no console line, nothing in the logs. The user simply reads `Unban {{ip}}` on a
button, and every automated check stays green because nothing failed.

The i18n conversion is what makes this worth a scan rather than a code review. ~2300 strings moved
from a catalog nobody interpolated into one where the message carries the variables, and a call
site written against the old message still compiles, still runs, and still renders — wrong. It has
already happened twice: the DataTables `infoCallback`, which showed `Showing {{start}} to {{end}}
of {{total}}` in every table footer, and the `/bans` unban tooltip this scan found.

**Known blind spot, stated rather than hidden**: of 565 `t()` calls, 505 are written with a
literal key and **60 with a variable**. 18 of those 60 are resolvable — the key is a choice between
two literals, written either in the call or in a declaration the file makes exactly once — and are
now checked. The remaining **42 stay unchecked**: `dataTableInit.js` dispatching on an action name,
a key built by concatenation, a name the file declares more than once. That is a real limit, not a
temporary one, and the resolution below refuses everything it is not certain of rather than guess.
`test_the_scan_still_reaches_the_call_sites_it_is_meant_to_check` exists so that a scanner that
quietly stops matching anything fails instead of passing.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _jsscan import (  # noqa: E402
    _REGEX_MAY_START,
    _skip_quoted,
    _skip_regex,
    Source,
    object_keys,
    split_arguments,
    string_value,
)

REPO = Path(__file__).resolve().parents[3]
JS = REPO / "src" / "ui" / "app" / "static" / "js"
CATALOG = REPO / "src" / "ui" / "app" / "static" / "locales" / "en.json"

PLACEHOLDER = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
# `t()` reads these out of the same options object the variables live in; they are settings, not
# interpolation values, so a message must never expect them to be supplied as one.
RESERVED = {"defaultValue", "interpolation", "count"}


def _messages():
    def flatten(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flatten(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}", value

    return dict(flatten(json.loads(CATALOG.read_text(encoding="utf-8"))))


def _scripts():
    return sorted(path for path in JS.rglob("*.js") if "libs" not in path.parts)


# --------------------------------------------------------------------------------------
# Keys that are written as a variable but only ever hold one of two literals.
#
# `alertTextKey` / `titleKey` — the read-only messaging — is written as
# `const k = userReadOnly ? "a" : "b"` and then passed to `t(k, ...)`. That is the same family as
# `plugins.js:518`, which shipped `action '{{action}}'` to users because nothing checked it. The
# resolution below is deliberately narrow and **fails closed**: anything it is not certain about
# stays in the unchecked blind spot, exactly as before. A wrong resolution would report a missing
# key that is not missing, which is worse than resolving nothing at all.
# --------------------------------------------------------------------------------------

IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def _code_only(text):
    """`text` with strings, template literals, comments and regex literals blanked out.

    Offsets and line breaks are preserved, so a match here can be read back out of the original.
    Searching raw source instead would find a declaration written in a comment or quoted in a
    string, and resolve a key from it.
    """
    out = list(text)

    def blank(start, end):
        for index in range(start, min(end, len(text))):
            if text[index] != "\n":
                out[index] = " "

    index, size, previous = 0, len(text), "\n"
    while index < size:
        char = text[index]
        if char == "\n":
            index += 1
            continue
        if char == "/" and text[index + 1 : index + 2] == "/":  # noqa: E203
            end = text.find("\n", index)
            end = size if end < 0 else end
            blank(index, end)
            index = end
            continue
        if char == "/" and text[index + 1 : index + 2] == "*":  # noqa: E203
            end = text.find("*/", index + 2)
            end = size if end < 0 else end + 2
            blank(index, end)
            index = end
            continue
        if char in "\"'`":
            end, _ = _skip_quoted(text, index, 0)
            blank(index, end)
            index = end
            continue
        if char == "/" and previous in _REGEX_MAY_START:
            end = _skip_regex(text, index)
            blank(index, end)
            index = end
            previous = "/"
            continue
        if not char.isspace():
            previous = char
        index += 1
    return "".join(out)


def _statement_at(text, start):
    """The text from `start` up to the `;` that ends that statement, or None.

    A semicolon, never a newline: prettier writes these ternaries across three lines, and a
    statement that ends at the first newline would read `const k = cond` and resolve nothing.
    Source without the semicolon runs on to the next one and produces an expression that is not a
    literal or a two-literal ternary, so it is refused there instead.
    """
    index, depth = start, 0
    while index < len(text):
        char = text[index]
        if char in "\"'`":
            index, _ = _skip_quoted(text, index, 0)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if not depth:
                return None
            depth -= 1
        elif char == ";" and not depth:
            return text[start:index]
        index += 1
    return None


def _ternary_branches(expression):
    """`(then, else)` of a top-level ternary, or None when there is not exactly one.

    `?.` and `??` are not conditionals and are stepped over. A nested ternary needs no rule of its
    own: whichever branch carries the extra `?` is then not a plain string literal, and
    `_literal_keys` refuses it there. A rule here as well would be unreachable, and unreachable
    code cannot be shown to work.
    """
    index, depth, question = 0, 0, None
    while index < len(expression):
        char = expression[index]
        if char in "\"'`":
            index, _ = _skip_quoted(expression, index, 0)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif not depth and char == "?":
            if expression[index + 1 : index + 2] in (".", "?"):  # noqa: E203
                index += 2  # `?.` and `??` are not conditionals
                continue
            question = index if question is None else question
        elif not depth and char == ":" and question is not None:
            return expression[question + 1 : index], expression[index + 1 :]  # noqa: E203
        index += 1
    return None


def _literal_keys(expression):
    """Every key `expression` can evaluate to, or None when that cannot be known for certain."""
    value = string_value(expression)
    if value is not None:
        return [value]
    branches = _ternary_branches(expression)
    if branches is None:
        return None
    keys = [string_value(branch) for branch in branches]
    return None if any(key is None for key in keys) else keys


def _resolve_variable_key(code, text, name):
    """The keys a `t(name)` can use, read from `name`'s declaration, or None.

    Requires that the file writes the name exactly once, and that the single write is this
    declaration. That one rule covers both ways the answer could be wrong: a second declaration
    means the name is shadowed and the value at the call site may be the other one, and an
    assignment or mutation means it is neither. Both give up rather than pick.
    """
    if not IDENTIFIER.match(name):
        return None
    declarations = list(re.finditer(rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=", code))
    if not declarations:
        return None
    writes = list(re.finditer(rf"\b{re.escape(name)}\s*(?:\*\*|<<|>>>?|[-+*/%|&^]|\?\?|\|\||&&)?=(?!=)|\b{re.escape(name)}\s*(?:\+\+|--)", code))
    if len(writes) != 1 or writes[0].end() != declarations[0].end():
        return None  # reassigned, mutated, or the sole write is not this declaration
    statement = _statement_at(text, declarations[0].end())
    return None if statement is None else _literal_keys(statement.strip())


def _default_value(argument):
    """The second argument read as a default string, or None when it is not one."""
    value = string_value(argument)
    return argument if value is None and argument.strip().startswith("`") else value


def _resolved_calls():
    """Every `t()` call whose key can be read from the source.

    Yields `(where, key, needed, provided)`, with `provided` set to None when the options object
    cannot be read (a spread, a computed property, a variable). Calls with a computed key are
    skipped rather than guessed at.
    """
    messages = _messages()
    for path in _scripts():
        text = path.read_text(encoding="utf-8")
        code = _code_only(text)
        for line, arguments in Source(text).t_calls:
            parts = split_arguments(arguments)
            if not parts:
                continue
            keys = _literal_keys(parts[0].strip())
            if keys is None:
                keys = _resolve_variable_key(code, text, parts[0].strip())
            if keys is None:  # computed key — the blind spot named in the docstring
                continue

            # i18next's three signatures, all of which are in use here:
            #   t(key) / t(key, options) / t(key, default) / t(key, default, options)
            #
            # With three arguments the shape is not in doubt — second is the default, third the
            # options — whatever the second one is written as. Deciding by whether the second
            # argument *reads* as a literal made `t(titleKey, defaultTitle, {...})` look like
            # `t(key, options)`, so `defaultTitle` was handed to `object_keys`, came back
            # unreadable, and the call was dropped. That is the read-only tooltip family, the same
            # one `plugins.js:518` shipped broken.
            default, options = None, None
            if len(parts) > 2:
                default, options = _default_value(parts[1]), parts[2]
            elif len(parts) == 2:
                default = _default_value(parts[1])
                options = None if default is not None else parts[1]

            # `None` means the options could not be read, which is not the same as "no variables
            # supplied". The key still gets checked; the placeholder rule sits this one out rather
            # than accuse a call of missing what it may well pass.
            provided = set() if options is None else object_keys(options)

            for key in keys:
                needed = set(PLACEHOLDER.findall(messages.get(key, "")))
                if default:
                    needed |= set(PLACEHOLDER.findall(default))
                yield f"{path.relative_to(JS)}:{line}", key, needed - RESERVED, provided


def test_every_t_call_passes_the_variables_its_message_interpolates():
    offenders = [
        f'{where} t("{key}") is missing {sorted(needed - provided)} — it will render them literally'
        for where, key, needed, provided in _resolved_calls()
        if provided is not None and needed - provided
    ]

    assert not offenders, "\n".join(offenders)


def test_every_t_key_exists_in_the_catalog():
    """A key that is not in the catalog is indistinguishable from a working one at runtime.

    `t()` falls back to the `defaultValue` when a lookup misses, so a mistyped key renders perfectly
    good English and logs nothing — while every other locale silently shows English too. That is how
    `t("placeholder.multivalue_enter_value")` survived: the real key is
    `form.placeholder.multivalue_enter_value`, the translation existed in all 18 locales, and it was
    never once used.

    The check above cannot catch it, and the way it fails is worth naming: a missing key resolves to
    `""`, `""` has no placeholders, so `needed - provided` is empty and the assertion passes. It
    reads as though it covers this and it cannot.

    Same blind spot as the placeholder rule, and for the same reason: a computed key (`t(msgKey)`)
    is not resolvable here.
    """
    messages = _messages()
    offenders = [
        f'{where} t("{key}") is not in en.json — the lookup misses and the fallback ships in every locale'
        for where, key, _, _ in _resolved_calls()
        if key not in messages
    ]

    assert not offenders, "\n".join(offenders)


def test_the_scan_still_reaches_the_call_sites_it_is_meant_to_check():
    """A scanner that matches nothing passes every assertion above it.

    The floor is deliberately far below the ~220 calls resolved today: it is here to catch a walker
    that broke, not to be edited every time a page gains or loses a string.
    """
    resolved = list(_resolved_calls())

    assert len(resolved) > 150, f"only {len(resolved)} t() calls resolved; the walker is not reading the sources"
    assert any(needed for _, _, needed, _ in resolved), "no resolved call has a placeholder at all — the catalog lookup is not working"


# --------------------------------------------------------------------------------------
# The resolution itself. Every case here is a way it could resolve something wrong, which is the
# failure that matters: a key reported missing that is not missing sends someone hunting a bug in
# the catalog. Resolving nothing is the safe direction and several of these assert exactly that.
# --------------------------------------------------------------------------------------


def test_a_two_literal_ternary_resolves_to_both_keys():
    assert _literal_keys('cond ? "a.one" : "a.two"') == ["a.one", "a.two"]
    assert _literal_keys('"a.only"') == ["a.only"]


def test_a_ternary_written_across_lines_resolves():
    """prettier writes every one of these on three lines. A resolver that ended the statement at
    the first newline would read `const k = cond` and quietly resolve nothing at all — which looks
    exactly like success, because the site simply stays in the blind spot."""
    source = 'const k = cond\n  ? "a.one"\n  : "a.two";\nt(k);\n'

    assert _resolve_variable_key(_code_only(source), source, "k") == ["a.one", "a.two"]


def test_a_name_the_file_declares_twice_is_refused():
    """`bans.js` declares `alertTextKey` in two functions. Picking the nearest one is a guess about
    scope, and the value it resolves to would be attributed to the wrong call.

    Refused by the write count — a second declaration is a second write — which is why there is no
    separate declaration-count rule to test.
    """
    source = 'const k = a ? "x.one" : "x.two";\nfunction f() { const k = b ? "y.one" : "y.two"; t(k); }\n'

    assert _resolve_variable_key(_code_only(source), source, "k") is None


def test_a_reassigned_or_mutated_name_is_refused():
    """The declaration is no longer what the call sees."""
    for source in (
        'const k = a ? "x.one" : "x.two";\nk = "other.key";\nt(k);\n',
        'let k = a ? "x.one" : "x.two";\nk += ".suffix";\nt(k);\n',
    ):
        assert _resolve_variable_key(_code_only(source), source, "k") is None, source


def test_a_three_way_ternary_is_refused():
    """`bans.js:257` is `filteredState ? A : bans.length > 1 ? B : C`. Three outcomes is not a
    two-literal choice, and reading only two of them would check the wrong set."""
    source = 'const k = a ? "x.one" : b ? "x.two" : "x.three";\nt(k);\n'

    assert _literal_keys('a ? "x.one" : b ? "x.two" : "x.three"') is None
    assert _resolve_variable_key(_code_only(source), source, "k") is None


def test_a_non_literal_branch_is_refused():
    assert _literal_keys('cond ? "a.one" : someKey') is None
    assert _literal_keys('cond ? prefix + "a.one" : "a.two"') is None


def test_optional_chaining_and_nullish_are_not_conditionals():
    """`a?.b`, `a ?? b` and `a ? b : c` all contain a `?`. Only the last one is a choice.

    Reading `?.` as the start of a conditional does not resolve the wrong key — it stops resolving
    at all, because the branch then begins with `.`. That is the safe direction, so what pins the
    rule is the coverage it buys: a condition that uses optional chaining still resolves.
    """
    assert _literal_keys('state?.flag ? "a.one" : "a.two"') == ["a.one", "a.two"]
    assert _literal_keys('(state ?? fallback) ? "a.one" : "a.two"') == ["a.one", "a.two"]
    assert _literal_keys("state?.key") is None
    assert _literal_keys('maybe ?? "a.two"') is None


def test_a_declaration_written_in_a_comment_or_a_string_does_not_resolve():
    """Searching raw source would resolve a key out of prose.

    The real declaration here is destructured, which the pattern cannot see — so raw source offers
    exactly one candidate, the one written in a comment or quoted in a string, and a resolver
    reading it would report those keys with total confidence. Two visible declarations would be
    refused by the write count instead, which is why these cases are written this way: they are the
    ones where `_code_only` is the only thing standing between the scan and a fabricated answer.
    """
    commented = 'const { k } = lookup(name);\n// const k = a ? "x.one" : "x.two";\nt(k);\n'
    quoted = 'const [k] = lookup(name);\nconst hint = \'const k = a ? "x.one" : "x.two";\';\nt(k);\n'

    for source in (commented, quoted):
        assert _resolve_variable_key(_code_only(source), source, "k") is None, source
        assert _resolve_variable_key(source, source, "k") == ["x.one", "x.two"], "the case no longer distinguishes anything"


def test_the_code_only_view_keeps_offsets_and_lines():
    """It is searched, then read back out of the original at the same offset."""
    source = 'const a = "text";\n// comment\nconst b = 1;\n'
    code = _code_only(source)

    assert len(code) == len(source)
    assert code.count("\n") == source.count("\n")
    assert code.index("const b") == source.index("const b")


def test_a_declaration_with_no_semicolon_resolves_nothing_rather_than_something_wrong():
    source = 'const k = a ? "x.one" : "x.two"\nt(k, "fallback")\n'

    assert _resolve_variable_key(_code_only(source), source, "k") is None


def test_the_resolution_reaches_the_sites_it_was_built_for():
    """Anti-vacuity, same reason as the scan floor above: a resolver that stopped resolving would
    make every assertion that uses it pass."""
    resolved = [(where, key) for where, key, _, _ in _resolved_calls()]
    keys = {key for _, key in resolved}

    assert "tooltip.readonly_user_action_disabled" in keys, "the read-only messaging family is not being resolved"
    assert "tooltip.readonly_db_action_disabled" in keys
    assert len(resolved) > 240, f"only {len(resolved)} keys resolved; the variable-key resolution has stopped working"
