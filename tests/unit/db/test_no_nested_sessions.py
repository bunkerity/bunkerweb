"""`_db_session` is not reentrant, so nesting it is a latent data-loss bug.

The context manager yields the shared scoped session and its `finally` calls `session.remove()`.
A nested `with self._db_session()` therefore closes the session the outer block is still using:
everything it loaded is detached (the next lazy load raises `DetachedInstanceError`) and
anything pending in it is discarded.

`renew_self_signed_certificate` did exactly that by resolving the encryption keyring inside its
own session -- harmless while the keyring came from the environment, fatal on a stock install
where reading it opens a session -- and `deploy-certificates` failed on every run, leaving
`certificates_changed` set forever. A reviewer cannot see this in a diff, so it is checked here.
"""

from pathlib import Path
from re import findall, match, search

DB_METHODS = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "db_methods"


def _session_opening_methods() -> set:
    """Methods that open a session, directly or through anything they call.

    The closure matters: `_keyring_values` opens none of its own, it calls
    `_load_or_create_db_keyring` which does. Stopping at direct openers misses exactly the
    call that broke certificate renewal.
    """
    openers = set()
    calls = {}
    for source in DB_METHODS.glob("*.py"):
        current = None
        for line in source.read_text().splitlines():
            found = match(r"\s{4}def (\w+)\(", line)
            if found:
                current = found.group(1)
                calls.setdefault(current, set())
            if not current:
                continue
            if "self._db_session()" in line:
                openers.add(current)
            calls[current].update(findall(r"self\.(\w+)\(", line))

    while True:
        grown = {method for method, callees in calls.items() if method not in openers and callees & openers}
        if not grown:
            return openers
        openers |= grown


def _arguments_of(expression: str, call: str) -> str:
    """The balanced argument list of `self.<call>(...)`.

    Stopping at the first `)` is wrong: a nested call in an earlier argument closes first, so
    `self._reconcile_credential_columns(host, instance.get("env"), token, keyring)` would be
    cut before `keyring` and reported as unsafe.
    """
    remainder = expression.split(f"self.{call}(", 1)[1]
    depth = 1
    for index, character in enumerate(remainder):
        depth += (character == "(") - (character == ")")
        if depth == 0:
            return remainder[:index]
    return remainder


def _nested_call_sites() -> list:
    openers = _session_opening_methods()
    hits = []
    for source in DB_METHODS.glob("*.py"):
        lines = source.read_text().splitlines()
        current, block_indent = None, None
        for number, line in enumerate(lines, 1):
            found = match(r"\s{4}def (\w+)\(", line)
            if found:
                current, block_indent = found.group(1), None
            if "with self._db_session()" in line:
                block_indent = len(line) - len(line.lstrip())
                continue
            if block_indent is None:
                continue
            stripped = line.strip()
            if stripped and (len(line) - len(line.lstrip())) <= block_indent and not stripped.startswith(("#", ")", "]", "}")):
                block_indent = None
                continue
            for call in findall(r"self\.(\w+)\(", line):
                if call not in openers or call == current:
                    continue
                # Two ways a call is already safe: it is handed the open session (positionally
                # or by keyword) and reuses it, or it is handed the `keyring` it would
                # otherwise have opened a session to read. The argument often sits several
                # lines down, so read the whole call expression, not its first line.
                expression = "".join(lines[number - 1 : number + 9])  # noqa: E203
                if search(r"\b(session|keyring)\b", _arguments_of(expression, call)):
                    continue
                hits.append(f"{source.name}:{number} {current}() calls self.{call}() inside a session")
    return hits


def test_the_db_methods_never_nest_a_session():
    assert _session_opening_methods(), "the scan found no session-opening methods, so it is not scanning anything"
    assert _nested_call_sites() == []
