"""Newline-safe reader for the `KEY=value` files BunkerWeb passes between its components.

`variables.env` is written one `KEY=value` line per setting, but settings of type "file"
hold PEM or base64 blocks that contain newlines. A reader that splits on physical lines
truncates such a value at its first line, and the config saver then writes the truncation
back to the database, destroying the certificate and taking the setting away from the UI
in the same pass.

The UI's raw editor already folds continuation lines back into the value it is editing.
This module is that rule for the Python side, shared by every component that reads one of
these files:

  - src/common/gen/Configurator.py (config saver, the one that writes back to the database)
  - src/common/gen/save_config.py
  - src/common/gen/main.py
  - src/scheduler/main.py
  - src/common/cli/CLI.py

Callers that know the settings universe pass both predicates so any multi-line value is
reassembled, PEM or wrapped base64. Callers that do not still get PEM blocks reassembled,
because a value that opens `-----BEGIN` is followed to its `-----END` whatever the key is.
"""

from pathlib import Path
from re import compile as re_compile
from typing import Callable, Dict, Iterable, Optional

# The token before the first "=" on a line that genuinely declares a setting. Service
# prefixes make the key `www.example.com_CUSTOM_SSL_CERT_DATA`, hence the dot and dash.
# Base64 lines carry "+" and "/" and fail this, so they cannot be mistaken for a key.
KEY_RX = re_compile(r"^[A-Za-z0-9_.-]+$")

PEM_BEGIN = "-----BEGIN"
PEM_END = "-----END"


def parse_env_lines(
    lines: Iterable[str],
    is_multiline_key: Optional[Callable[[str], bool]] = None,
    is_known_key: Optional[Callable[[str], bool]] = None,
) -> Dict[str, str]:
    """Parse `KEY=value` lines into a dict, keeping multi-line values intact.

    A physical line starts a new pair only when the token before its first "=" looks like a
    setting key. Anything else continues the value being built. Single-line values keep the
    historical strip(); multi-line values are preserved verbatim because PEM and base64 are
    byte-sensitive.

    A value inside a PEM block is always followed to its `-----END`, since a base64 line that
    ends on its "=" padding is otherwise indistinguishable from a declaration. Wrapped base64
    carries no such marker, so folding it needs both predicates: `is_multiline_key` to know the
    current value can span lines, and `is_known_key` to know where the next value starts.
    """
    fold_unmarked = is_multiline_key is not None and is_known_key is not None
    variables: Dict[str, str] = {}
    key: Optional[str] = None
    parts: list = []
    in_pem = False
    pem_closed = False

    def flush() -> None:
        if key is None:
            return
        variables[key] = "\n".join(parts) if len(parts) > 1 else parts[0].strip()

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")

        candidate = line.split("=", 1)[0].strip() if "=" in line else None
        looks_like_key = candidate is not None and KEY_RX.match(candidate) is not None
        declares_known = looks_like_key and is_known_key is not None and is_known_key(candidate)  # type: ignore[misc]

        # Inside a PEM block every line belongs to the value, including one that happens to look
        # like `KEY=value` because a base64 line ended on its "=" padding. A key the caller
        # recognises still ends it, so a value already truncated by an older writer cannot
        # swallow the settings that follow it.
        if in_pem and not declares_known:
            parts.append(line)
            if PEM_END in line:
                in_pem = False
                # The block is complete, so nothing after it belongs to this value.
                pem_closed = True
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        folding = fold_unmarked and key is not None and not pem_closed and is_multiline_key(key)  # type: ignore[misc]

        # Wrapped base64 can produce a token that looks like a key. Only a key the caller
        # recognises ends the value being folded.
        declares = looks_like_key and (not folding or declares_known)

        if not declares:
            if folding or in_pem:
                parts.append(line)
            continue

        flush()
        key = candidate
        value = line.split("=", 1)[1]
        parts = [value]
        in_pem = PEM_BEGIN in value and PEM_END not in value
        pem_closed = False

    flush()
    return variables


def parse_env_file(
    path: Path,
    is_multiline_key: Optional[Callable[[str], bool]] = None,
    is_known_key: Optional[Callable[[str], bool]] = None,
) -> Dict[str, str]:
    """Read `path` and parse it with `parse_env_lines`."""
    return parse_env_lines(path.read_text(encoding="utf-8").splitlines(), is_multiline_key, is_known_key)


def make_key_predicate(setting_names: Iterable[str]) -> Callable[[str], bool]:
    """Build a predicate matching a set of setting names as they appear in a variables file.

    A key in a variables file carries the service prefix and the "multiple" suffix, so
    `CUSTOM_SSL_CERT_DATA` also arrives as `www.example.com_CUSTOM_SSL_CERT_DATA` and
    `REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA_2`.
    """
    names = frozenset(setting_names)

    def matches(token: str) -> bool:
        if token in names:
            return True

        base, _, suffix = token.rpartition("_")
        if suffix.isdigit():
            token = base
            if token in names:
                return True

        # Drop the service prefix one component at a time rather than scanning every name.
        while "_" in token:
            token = token.split("_", 1)[1]
            if token in names:
                return True
        return False

    return matches
