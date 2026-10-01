"""Turn a plugin setting's Python regex into an HTML `pattern` the browser really checks.

Browsers compile `pattern` with the `v` flag, which refuses syntax Python takes as a literal
(a bare `-`, `{`, `/` or `;` in a class, `\\"` or `\\-` outside one, ...). A refused pattern is
ignored silently, so the field is never checked. `v_safe_pattern` rewrites only how literals
are spelled, never what the regex accepts; a construct it does not know gives "" (no pattern,
the server check still holds).

Keep in step with `vSafePattern` in static/js/modules/setting_controls.js: both are compared
output for output by tests/unit/ui/test_setting_patterns_v_flag.py.
"""

from re import compile as re_compile, error as RegexError

# Escaped outside a class: the v flag allows an identity escape only for these.
_SYNTAX = frozenset("^$\\.*+?()[]{}|/")
# Escaped inside a class: v class syntax characters, reserved (double) punctuators, and the
# syntax characters, all of which the v flag accepts escaped.
_CLASS_ESCAPED = frozenset("()[]{}/-\\|&!#%,:;<=>@`~^$.*+?")
_CLASS_SETS = frozenset("dDwWsS")
_KEPT = re_compile(r"[dDwWsSbBnrtfv]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}")
_BACKREF = re_compile(r"[1-9][0-9]?")
_QUANTIFIER = re_compile(r"\{([0-9]*)(,([0-9]*))?\}")
_GROUP_NAME = re_compile(r"P<([A-Za-z_][A-Za-z0-9_]*)>")
_GROUP_OPENERS = ("(?:", "(?=", "(?!", "(?<=", "(?<!")


class _Unsupported(Exception):
    pass


def _class_literal(char: str) -> str:
    return "\\" + char if char in _CLASS_ESCAPED else char


def _escape(regex: str, index: int, in_class: bool) -> tuple[str, int, str]:
    """Spell the escape at regex[index] (a backslash). Returns (text, next index, "char" or "set")."""
    char = regex[index + 1 : index + 2]
    if not char:
        raise _Unsupported
    if not (char.isascii() and char.isalnum()):  # Python's identity escape: a literal
        if in_class:
            return _class_literal(char), index + 2, "char"
        return ("\\" + char if char in _SYNTAX else char), index + 2, "char"
    kept = _KEPT.match(regex, index + 1)
    if kept and not (in_class and char == "B"):
        return "\\" + kept.group(), kept.end(), "set" if char in _CLASS_SETS else "char"
    backref = None if in_class else _BACKREF.match(regex, index + 1)
    if backref:
        return "\\" + backref.group(), backref.end(), "char"
    raise _Unsupported


def _class(regex: str, index: int) -> tuple[str, int]:
    """Spell the class opening at regex[index]. Returns (text, index after its `]`)."""
    out, index = ["["], index + 1
    if regex[index : index + 1] == "^":
        out.append("^")
        index += 1
    first, last = True, ""  # last item: "char" (can open a range), "set" (\w, \d...) or "range"
    while True:
        if index >= len(regex):
            raise _Unsupported
        char = regex[index]
        if char == "]" and not first:  # Python takes a leading `]` as a literal
            out.append("]")
            return "".join(out), index + 1
        first = False
        if char == "-" and last in ("char", "set") and regex[index + 1 : index + 2] not in ("", "]"):
            if last == "set":
                raise _Unsupported  # Python refuses `[\w-a]`
            if regex[index + 1] == "\\":
                end, index, kind = _escape(regex, index + 1, True)
                if kind != "char":
                    raise _Unsupported
            else:
                end, index = _class_literal(regex[index + 1]), index + 2
            out.append("-" + end)
            last = "range"
        elif char == "\\":
            text, index, last = _escape(regex, index, True)
            out.append(text)
        else:
            out.append(_class_literal(char))
            last = "char"
            index += 1


def v_safe_pattern(regex) -> str:
    """The `pattern` attribute for `regex`, or "" when it cannot be spelled the same under `v`."""
    # Past U+FFFF the JS twin, which walks UTF-16 units, would split characters: no pattern.
    if not isinstance(regex, str) or not regex or any(ord(char) > 0xFFFF for char in regex):
        return ""
    try:
        re_compile(regex)
    except RegexError:
        return ""  # the server skips the check of a regex it cannot compile
    out, index, quantified = [], 0, False
    try:
        while index < len(regex):
            char, was_quantified, quantified = regex[index], quantified, False
            if char == "\\":
                text, index, _ = _escape(regex, index, False)
                out.append(text)
            elif char == "[":
                text, index = _class(regex, index)
                out.append(text)
            elif char == "(" and regex[index + 1 : index + 2] == "?":
                name = _GROUP_NAME.match(regex, index + 2)
                opener = f"(?<{name.group(1)}>" if name else next((o for o in _GROUP_OPENERS if regex.startswith(o, index)), None)
                if not opener:
                    raise _Unsupported  # inline flags, atomic groups, conditionals, comments...
                out.append(opener)
                index = name.end() if name else index + len(opener)
            elif char == "{":
                bounds = _QUANTIFIER.match(regex, index)
                if bounds and bounds.group() != "{}":
                    out.append("{" + (bounds.group(1) or "0") + ("," + bounds.group(3) if bounds.group(2) else "") + "}")
                    index, quantified = bounds.end(), True
                else:
                    out.append("\\{")
                    index += 1
            elif char in "}]":
                out.append("\\" + char)
                index += 1
            else:
                if char == "+" and was_quantified:
                    raise _Unsupported  # Python 3.11 possessive quantifier (`a*+`)
                out.append(char)
                quantified = char in "*+?"
                index += 1
    except _Unsupported:
        return ""
    return "".join(out)
