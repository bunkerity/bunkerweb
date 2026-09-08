"""Newline-safe reader for the `KEY=value` files BunkerWeb passes between its components.

`variables.env` is written one `KEY=value` line per setting, but settings of type "file"
hold PEM or base64 blocks that contain newlines. A reader that splits on physical lines
truncates such a value at its first line, and the config saver then writes the truncation
back to the database, destroying the certificate and taking the setting away from the UI
in the same pass.

This module is the one folding rule for the Python side, shared by every component that
reads one of these files. The UI does not go through it: its raw editor folds continuation
lines under a multiline setting in JavaScript and ignores stray lines
(src/ui/app/static/js/plugins-settings.js), and its .env import refuses a line without `=`
loudly (src/ui/app/routes/services.py), so neither truncates silently.

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

# What a continuation line of an UNMARKED (non-PEM) folded value must look like: wrapped
# base64, alphabet only, optional padding at the end. Both alphabets are accepted, standard
# (`+/`) and urlsafe (`-_`), because a payload encoded either way is one value that must come
# back whole. `TZ=Europe/Paris` fails this, `MIIBkTCB+wIJAK==` and `ab-_cd==` pass. Without the
# shape check, any env var the caller's settings universe does not know (TZ, HOSTNAME, anything
# compose injects) that follows a `file`-type setting in a dumped environment is swallowed into
# that setting's value -- which is exactly how a valid base64 certificate became
# `<b64>\nTZ=Europe/Paris` and failed Python 3.14's strict decode with "Excess data after
# padding". Only lines that could be read as a declaration are tested against it; see
# `parse_env_lines`.
B64_LINE_RX = re_compile(r"^[A-Za-z0-9+/_-]+={0,2}$")


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
    current value can span lines, and `is_known_key` to know where the next value starts. Only a
    line that could be read as a declaration and is NOT shaped like wrapped base64 (`B64_LINE_RX`)
    ends such a value, so env vars outside the settings universe (`TZ=Europe/Paris`,
    `HOSTNAME=abc`) are kept as their own entries instead of being swallowed into a certificate.
    A line that cannot be a declaration at all still continues the value whatever it looks like,
    so nothing is ever dropped. A `NAME=` line with no value declares, unless its name would land
    the folded payload on a multiple of four: that is where a base64 pad has to fall, so off the
    boundary the line cannot be the last chunk of a wrapped value and can only be a declaration.
    Wrapped base64 is a supported shape for `file`-type settings, the readers join on whitespace
    before decoding, so reading its padded last chunk as a declaration would truncate the value
    and write the truncation back. The ceiling that leaves is a bare declaration whose own name
    lands on the boundary, which is one empty declaration in four at any name length: nothing in
    the file tells those apart from a last chunk. Both outcomes destroy the value, so the choice is
    which trigger is rarer, and this one needs an adjacent empty foreign variable where the other
    fires on every wrapped payload.
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
        # A bare `NAME=` carries no payload, so reading it as a chunk of the value being folded
        # can only corrupt that value and lose the variable. It is ambiguous with exactly one
        # thing, the LAST chunk of a wrapped base64 payload, whose "=" is padding: that pad exists
        # to bring the whole payload to a multiple of four, so a line that does not land the value
        # on that boundary cannot be it and declares. Wrapped base64 is a supported input shape
        # for `file`-type settings (the readers join on whitespace before decoding), so this
        # boundary is the difference between keeping such a value whole and truncating it. One
        # empty declaration in four does land on the boundary and is still folded; that is the
        # rarer of the two triggers, see `parse_env_lines`.
        declares_empty = looks_like_key and not line.split("=", 1)[1].strip()
        if declares_empty and parts:
            # Whitespace is not payload: the readers join on it before decoding, so a value
            # wrapped with spaces rather than newlines has to be counted the same way.
            payload = "".join("".join(part.split()) for part in parts) + "".join(line.split())
            declares_empty = len(payload) % 4 != 0

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

        folding = (
            fold_unmarked
            and key is not None
            and not pem_closed
            and not declares_known
            and not declares_empty
            # The shape check only has to disambiguate a line that COULD be read as a declaration.
            # A line without a `KEY=` shape cannot end a value, so it always continues one --
            # dropping it (which requiring the shape unconditionally does) is the truncation this
            # module exists to prevent, for a urlsafe-base64 or header-stripped payload.
            and (B64_LINE_RX.match(stripped) is not None or not looks_like_key)
            and is_multiline_key(key)  # type: ignore[misc]
        )

        # Wrapped base64 can produce a token that looks like a key. Only a key the caller
        # recognises ends the value being folded.
        declares = looks_like_key and (not folding or declares_known)

        if not declares:
            if folding or in_pem:
                parts.append(line)
            elif key is not None and stripped.startswith(PEM_BEGIN):
                # A new BEGIN right after a closed block is the next certificate of a chain
                # (fullchain.pem is the default ACME layout), not junk: reopen the block for the
                # same key. Dropping it would be a silent write-back the config_save
                # truncated-PEM guard cannot see -- both markers stay present.
                parts.append(line)
                in_pem = PEM_END not in line
                pem_closed = not in_pem
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
