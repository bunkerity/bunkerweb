"""A source walker for the UI's own JavaScript, shared by the tests that read it statically.

Not a parser and not trying to be one. It walks the file once and answers the two questions the
tests ask — how deeply nested is each line, and what is passed to each `t(...)` call — while
skipping the four places where those questions have no meaning: strings, template literals,
comments, and regex literals. `return` inside a template literal is text, and `t(` inside a comment
is not a call site.

Static reading rather than execution is deliberate. These files need a DOM, jQuery, DataTables and
a live page to run at all, so anything that only shows up at runtime shows up in a browser or not
at all; reading the source covers every branch, including the ones no fixture reaches.
"""

import re

# `t(` only counts when `t` is its own identifier — `Event(`, `parseInt(`, `.at(` are not calls to
# the translation helper and there are far more of them than of the real thing.
_IDENTIFIER_TAIL = "_$."
# A `/` starts a regex only where a value may start; after a name or a closing paren it is division.
_REGEX_MAY_START = "(,=:[!&|?{};+-*%~^<>\n"


class Source:
    """One JavaScript file, walked once.

    `depth_by_line` maps a 1-based line number to the brace depth of its first significant
    character; a closing brace is reported at the depth of the block it closes, so `}` and the
    statements it encloses do not read as different levels.

    `t_calls` is a list of `(line, arguments)` — the raw text between the parentheses, with nesting
    and strings balanced, ready to be split on top-level commas.
    """

    def __init__(self, text):
        self.depth_by_line = {}
        self.t_calls = []
        self._walk(text)

    def _walk(self, text):
        index, size, depth, line, previous = 0, len(text), 0, 1, "\n"
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
            if char in "\"'`":
                index, line = _skip_quoted(text, index, line)
                previous = char
                continue
            if char == "/" and previous in _REGEX_MAY_START:
                index = _skip_regex(text, index)
                previous = "/"
                continue
            if char == "t" and text[index + 1 : index + 2] == "(" and not (previous.isalnum() or previous in _IDENTIFIER_TAIL):  # noqa: E203
                self.t_calls.append((line, _balanced(text, index + 2)))
            if not char.isspace():
                self.depth_by_line.setdefault(line, depth + 1 if char == "}" else depth)
                previous = char
            depth += (char == "{") - (char == "}")
            index += 1


def _skip_quoted(text, index, line):
    quote, index = text[index], index + 1
    while index < len(text) and text[index] != quote:
        if text[index] == "\\":
            index += 1
        elif text[index] == "\n":
            line += 1
        index += 1
    return index + 1, line


def _skip_regex(text, index):
    index += 1
    while index < len(text) and text[index] not in "/\n":
        if text[index] == "\\":
            index += 1
        elif text[index] == "[":  # `/` inside a character class does not close the literal
            while index < len(text) and text[index] != "]":
                index += 1 + (text[index] == "\\")
        index += 1
    return index + 1


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
