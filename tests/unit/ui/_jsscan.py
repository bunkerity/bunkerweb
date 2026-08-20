"""A source walker for the UI's own JavaScript, shared by the tests that read it statically.

Not a parser and not trying to be one. It walks the file once and answers the two questions the
tests ask — how deeply nested is each line, and what is passed to each `t(...)` call — while
skipping the places where those questions have no meaning: strings, comments, regex literals, and
the *text* of a template literal. `return` inside a template literal is text, and `t(` inside a
comment is not a call site.

A template literal's `${...}` substitutions are code, though, and are walked as such. Skipping them
whole hid 120 `t()` call sites across 10 files from the key-existence and placeholder checks — every
`${t("button.export", "Export")}` in a DataTables button definition, which is most of them.

Static reading rather than execution is deliberate. These files need a DOM, jQuery, DataTables and
a live page to run at all, so anything that only shows up at runtime shows up in a browser or not
at all; reading the source covers every branch, including the ones no fixture reaches.
"""

import re

# `t(` only counts when `t` is its own identifier — `Event(`, `parseInt(`, `.at(` are not calls to
# the translation helper and there are far more of them than of the real thing.
#
# The test is on the character *immediately* before `t`, not on the last non-whitespace one. Those
# differ exactly where a keyword precedes the call, and that difference hid six live call sites:
# `return t(...)`, `await t(...)`, `typeof t(...)`, `void t(...)` all read as `n`, `t`, `f`, `d` —
# alphanumeric — so the call was silently not a call. `window.t(` and `obj.t(` stay skipped, on the
# separate and still-correct ground that `.` continues an identifier.
_IDENTIFIER_TAIL = "_$."
# A `/` starts a regex only where a value may start; after a name or a closing paren it is division.
_REGEX_MAY_START = "(,=:[!&|?{};+-*%~^<>\n"
# ...and after a keyword, which is a value position that looks like a name. `return /:/.test(v)` is
# the same shape as `return t(...)`: the character before the `/` is a letter, so the literal read as
# division, its closing `/` opened a second "regex", and that ran to the end of the line — consuming
# the newline without counting it. Every line after it in the file was then numbered one too low,
# which is `test_page_script_reachability` reading the wrong lines of `bans.js`.
# A translator does not have to arrive as the global `t`. `setting_controls.js` takes one in its
# constructor — `this.translate = translate || ((_, fallback) => fallback || "")` — and calls it as
# `this.translate(key, fallback, options)`: the same signature, reached through a property. Those
# calls are recognised by the dotted name, which is why the rule is written on `.translate(` and not
# on `translate`. `.t(` deliberately stays out: `obj.t(` in general is not this function. The
# vendored `buttons.js` used to be the standing proof of that — its line 10 was `t = window.Math`,
# so a `.t(` there was arithmetic — but it was deleted when its widget became a server-rendered
# link. The rule does not rest on that file: `.` continues an identifier, so the name in `window.t`
# is `window.t`, not `t`.
_INJECTED_HELPER = ".translate("
_VALUE_KEYWORDS = frozenset(("return", "typeof", "case", "void", "await", "delete", "in", "of", "new", "instanceof", "yield", "do", "else"))


def _template_text(text, index, line):
    """Through a template literal's text from `index`, stopping at the first `${` or its end.

    Returns `(index, line, opened)`; `opened` is True when it stopped at a substitution, with
    `index` past the `${`, and False when the literal ended, with `index` past the backtick.
    """
    while index < len(text):
        char = text[index]
        if char == "\\":
            line += text[index + 1 : index + 2] == "\n"  # noqa: E203
            index += 2
            continue
        if char == "`":
            return index + 1, line, False
        if char == "$" and text[index + 1 : index + 2] == "{":  # noqa: E203
            return index + 2, line, True
        line += char == "\n"
        index += 1
    return index, line, False


def track_substitutions(substitutions, char):
    """Note a brace seen in code. True when it closed the innermost open `${...}`.

    Each entry counts the braces opened inside that substitution, so the `}` that ends it is the
    one seen while its count is zero. Kept independent of any walker's own brace depth: two of the
    three walkers that need this do not track depth at all.
    """
    if not substitutions:
        return False
    if char == "{":
        substitutions[-1] += 1
    elif substitutions[-1]:
        substitutions[-1] -= 1
    else:
        substitutions.pop()
        return True
    return False


class Source:
    """One JavaScript file, walked once.

    `depth_by_line` maps a 1-based line number to the brace depth of its first significant
    character; a closing brace is reported at the depth of the block it closes, so `}` and the
    statements it encloses do not read as different levels.

    `t_calls` is a list of `(line, arguments)` — the raw text between the parentheses, with nesting
    and strings balanced, ready to be split on top-level commas. It holds the bare `t(...)` calls
    and the injected `.translate(...)` ones, which take the same arguments.
    """

    def __init__(self, text):
        self.depth_by_line = {}
        self.t_calls = []
        self._walk(text)

    def _walk(self, text):
        index, size, depth, line, previous = 0, len(text), 0, 1, "\n"
        substitutions = []  # one entry per open `${`, innermost last
        while index < size:
            char = text[index]
            if char == "\n":
                line += 1
                index += 1
                continue
            if char == "/" and text[index + 1 : index + 2] == "/":  # noqa: E203
                while index < size and text[index] != "\n":
                    index += 1
                continue
            if char == "/" and text[index + 1 : index + 2] == "*":  # noqa: E203
                index += 2
                while index + 1 < size and not (text[index] == "*" and text[index + 1] == "/"):
                    line += text[index] == "\n"
                    index += 1
                index += 2
                continue
            if char == "`":
                index, line, previous = self._resume(text, index + 1, line, substitutions)
                continue
            if char in "\"'":
                index, line = _skip_quoted(text, index, line)
                previous = char
                continue
            if char in "{}" and track_substitutions(substitutions, char):
                # Not a block brace: it closes a `${...}`, so the literal's text resumes after it
                # and neither the depth nor this line's entry may move.
                index, line, previous = self._resume(text, index + 1, line, substitutions)
                continue
            if char == "/" and (previous in _REGEX_MAY_START or _follows_a_keyword(text, index)):
                index = _skip_regex(text, index)
                previous = "/"
                continue
            if char == "t" and text[index + 1 : index + 2] == "(" and _starts_an_identifier(text, index):  # noqa: E203
                self.t_calls.append((line, _balanced(text, index + 2)))
            if char == "." and text.startswith(_INJECTED_HELPER, index):
                self.t_calls.append((line, _balanced(text, index + len(_INJECTED_HELPER))))
            if not char.isspace():
                self.depth_by_line.setdefault(line, depth + 1 if char == "}" else depth)
                previous = char
            depth += (char == "{") - (char == "}")
            index += 1

    def _resume(self, text, index, line, substitutions):
        """Read template text from `index`, then report where code picks up again."""
        index, line, opened = _template_text(text, index, line)
        if opened:
            substitutions.append(0)
        # A substitution opens a value position (`${/re/}` is a regex); the end of a literal is a
        # value, so a `/` after it divides.
        return index, line, "{" if opened else "`"


def _starts_an_identifier(text, index):
    """True when the name at `index` begins there, rather than continuing something."""
    before = text[index - 1] if index else "\n"
    return not (before.isalnum() or before in _IDENTIFIER_TAIL)


def _follows_a_keyword(text, index):
    """True when the token immediately before `index` is a keyword a value may follow."""
    end = index
    while end and text[end - 1] in " \t":
        end -= 1
    start = end
    while start and (text[start - 1].isalpha() or text[start - 1] == "_"):
        start -= 1
    return text[start:end] in _VALUE_KEYWORDS


def _skip_quoted(text, index, line):
    """Past one string literal. A template is skipped whole, substitutions included.

    Callers that balance parentheses (`_balanced`, `split_arguments`) want the whole literal gone;
    only the walkers descend. Nesting has to be honoured either way: in `` `a${`b`}c` `` the second
    backtick opens an inner literal rather than closing the outer one, and stopping there would
    hand the caller a half-literal and an unbalanced count.
    """
    if text[index] == "`":
        return _skip_template(text, index, line)
    quote, index = text[index], index + 1
    while index < len(text) and text[index] != quote:
        if text[index] == "\\":
            index += 1
        elif text[index] == "\n":
            line += 1
        index += 1
    return index + 1, line


def _skip_template(text, index, line):
    """Past a whole template literal — its substitutions, and any literal nested in them."""
    substitutions = []
    index, line, opened = _template_text(text, index + 1, line)
    substitutions += [0] * opened
    while substitutions and index < len(text):
        char = text[index]
        if char == "\n":
            line += 1
        elif char in "\"'`":
            index, line = _skip_quoted(text, index, line)
            continue
        elif char in "{}" and track_substitutions(substitutions, char):
            index, line, opened = _template_text(text, index + 1, line)
            substitutions += [0] * opened
            continue
        index += 1
    return index, line


def _skip_regex(text, index):
    index += 1
    while index < len(text) and text[index] not in "/\n":
        if text[index] == "\\":
            index += 1
        elif text[index] == "[":  # `/` inside a character class does not close the literal
            while index < len(text) and text[index] != "]":
                index += 1 + (text[index] == "\\")
        index += 1
    # Step past the closing `/`, but never past a newline: a regex literal cannot contain one, so
    # reaching one means this was not a regex at all. Consuming it here would lose a line and
    # renumber the whole rest of the file.
    return index + 1 if index < len(text) and text[index] == "/" else index


def _balanced(text, start):
    """The text up to the paren that closes the one just opened, ignoring quoted content."""
    index, depth = start, 1
    while index < len(text) and depth:
        char = text[index]
        if char in "\"'`":
            index, _ = _skip_quoted(text, index, 0)
            continue
        depth += char in "([{"
        depth -= char in ")]}"
        index += 1
    return text[start : index - 1]  # noqa: E203


def split_arguments(text):
    """Split an argument list on its top-level commas."""
    parts, depth, current, index = [], 0, [], 0
    while index < len(text):
        char = text[index]
        if char in "\"'`":
            end, _ = _skip_quoted(text, index, 0)
            current.append(text[index:end])
            index = end
            continue
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            index += 1
            continue
        depth += char in "([{"
        depth -= char in ")]}"
        current.append(char)
        index += 1
    if "".join(current).strip():
        parts.append("".join(current).strip())
    return parts


_STRING = re.compile(r'^"((?:[^"\\]|\\.)*)"$|^\'((?:[^\'\\]|\\.)*)\'$', re.DOTALL)
_KEYED = re.compile(r'^["\']?([\w.]+)["\']?\s*:')
_SHORTHAND = re.compile(r"^([\w$]+)$")


def string_value(text):
    """The contents of a quoted string literal, or None if this is not one."""
    match = _STRING.match(text.strip())
    if not match:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


def object_keys(text):
    """Top-level keys of an object literal, or None when they cannot be read.

    None means "unknown", never "none" — a spread or a computed key could supply anything, and a
    caller that treats unknown as empty would invent failures rather than find them.
    """
    text = text.strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    keys = set()
    for part in split_arguments(text[1:-1]):
        part = part.strip()
        if not part:
            continue
        if part.startswith(("...", "[")):
            return None
        for pattern in (_KEYED, _SHORTHAND):
            match = pattern.match(part)
            if match:
                keys.add(match.group(1))
                break
        else:
            return None
    return keys
