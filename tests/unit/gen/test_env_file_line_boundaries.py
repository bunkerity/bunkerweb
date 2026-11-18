"""``variables.env`` readers and writers must agree on what a record is (Criticos review of SEC-03).

Three ways the first encoder disagreed with its readers:

1. the Python reader decoded ``bw-b64:`` in any file, so an operator's file holding that text as data
   changed, and it decoded a whitespace-prefixed literal the writer had written raw;
2. an encoded record that sat before an empty ``NAME=`` line was folded into it by the legacy rules
   and came back undecoded;
3. ``str.splitlines()`` splits on ``\\r``, ``\\v``, ``\\f``, ``\\x1c``-``\\x1e``, ``\\x85``, ``\\u2028`` and
   ``\\u2029``, which Lua's ``io.lines`` and the shell readers do not, so a value holding one changed bytes
   and could start a ``KEY=`` line in Python only.

A file written by ``format_env_lines`` carries a marker first line and is read one record per line, with
decoding. Any other file is read by the legacy folding rules and is never decoded.
"""

import re
from base64 import b64encode

import pytest

import env_file
from env_file import format_env_lines, make_key_predicate, parse_env_file, parse_env_lines

PREFIX = getattr(env_file, "ENV_B64_PREFIX", "bw-b64:")
PEM = "-----BEGIN CERTIFICATE-----\nQUJDRA==\nREVGRw==\n-----END CERTIFICATE-----\n"
SPLITLINES_BREAKS = ["\n", "\r", "\r\n", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " "]


def _encoded(text):
    return PREFIX + b64encode(text.encode()).decode()


def _write(tmp_path, text, name="variables.env"):
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path


# --- 1. decode only a file the writer generated ---------------------------------------------------


def test_an_unmarked_file_is_never_decoded(tmp_path):
    """An operator or rc4 file may hold ``bw-b64:`` text as data, whatever it looks like."""
    path = _write(tmp_path, f"MY_TOKEN={_encoded('secret')}\nOTHER={PREFIX}\n")
    assert parse_env_file(path) == {"MY_TOKEN": _encoded("secret"), "OTHER": PREFIX}
    assert parse_env_lines([f"MY_TOKEN={_encoded('secret')}"]) == {"MY_TOKEN": _encoded("secret")}


def test_a_generated_file_decodes_its_records(tmp_path):
    path = _write(tmp_path, format_env_lines({"CERT": PEM, "PLAIN": "yes", "LITERAL": _encoded("x")}))
    assert parse_env_file(path) == {"CERT": PEM, "PLAIN": "yes", "LITERAL": _encoded("x")}


@pytest.mark.parametrize("value", [" " + _encoded("x"), "\t" + _encoded("x")])
def test_a_whitespace_prefixed_literal_is_data_not_an_encoding(tmp_path, value):
    """The writer tests the prefix on the raw value, so the reader must too: this is written raw."""
    path = _write(tmp_path, format_env_lines({"K": value}))
    assert parse_env_file(path)["K"] == value.strip()


def test_the_marker_is_ignored_by_a_line_reader_that_matches_key_equals_value():
    """init-lua.conf, init-stream-lua.conf and api.lua match ``^([^=]+)=(.*)$`` per line."""
    first = format_env_lines({}).split("\n")[0]
    assert first == env_file.ENV_FORMAT_MARKER
    assert re.match(r"^([^=]+)=(.*)$", first) is None


# --- 2. an encoded record is complete on its own line ---------------------------------------------


def _empty_name_landing_on_a_base64_boundary(encoded):
    """The `NAME=` the legacy folding reads as the last chunk of a wrapped value (payload % 4 == 0)."""
    for length in range(1, 5):
        if (len(encoded) + length + 1) % 4 == 0:
            return "E" * length
    raise AssertionError("no length found")


def test_an_encoded_record_is_not_folded_into_a_following_empty_variable(tmp_path):
    name = _empty_name_landing_on_a_base64_boundary(_encoded(PEM))
    path = _write(tmp_path, format_env_lines({"CUSTOM_SSL_CERT_DATA": PEM, name: "", "AFTER": "1"}))
    parsed = parse_env_file(path, make_key_predicate({"CUSTOM_SSL_CERT_DATA"}), make_key_predicate({"CUSTOM_SSL_CERT_DATA", "AFTER"}))
    assert parsed == {"CUSTOM_SSL_CERT_DATA": PEM, name: "", "AFTER": "1"}


def test_an_encoded_record_is_never_the_target_of_a_fold(tmp_path):
    """A line without a `KEY=` shape after an encoded record is ignored, not appended to it as a chunk."""
    text = f"{env_file.ENV_FORMAT_MARKER}\nCUSTOM_SSL_CERT_DATA={_encoded(PEM)}\nQUJDRA\nAFTER=1\n"
    path = _write(tmp_path, text)
    parsed = parse_env_file(path, make_key_predicate({"CUSTOM_SSL_CERT_DATA"}), make_key_predicate({"CUSTOM_SSL_CERT_DATA", "AFTER"}))
    assert parsed == {"CUSTOM_SSL_CERT_DATA": PEM, "AFTER": "1"}


# --- 3. one definition of a physical line ---------------------------------------------------------


@pytest.mark.parametrize("sep", SPLITLINES_BREAKS)
def test_a_value_with_any_splitlines_break_round_trips_and_injects_nothing(tmp_path, sep):
    value = f"-----BEGIN CERTIFICATE-----{sep}API_TOKEN=evil{sep}-----END CERTIFICATE-----"
    written = format_env_lines({"CUSTOM_SSL_CERT_DATA": value, "API_TOKEN": "real"})
    path = _write(tmp_path, written)
    assert parse_env_file(path) == {"CUSTOM_SSL_CERT_DATA": value, "API_TOKEN": "real"}
    # What a "\n"-only reader (Lua io.lines, grep) sees: one declaration per key, no value line among them.
    seen = [m.group(1) for m in map(lambda line: re.match(r"^([^=]+)=(.*)$", line), written.split("\n")) if m]
    assert seen == ["CUSTOM_SSL_CERT_DATA", "API_TOKEN"]


@pytest.mark.parametrize("sep", SPLITLINES_BREAKS[1:])
def test_a_break_at_the_edge_of_a_value_keeps_its_bytes(tmp_path, sep):
    """``str.strip()`` would eat a leading or trailing ``\\v``, ``\\u2028`` and the like: they are encoded."""
    for value in (f"{sep}x", f"x{sep}y{sep}"):
        path = _write(tmp_path, format_env_lines({"K": value}))
        assert parse_env_file(path)["K"] == value


@pytest.mark.parametrize("sep", [b for b in SPLITLINES_BREAKS if b not in ("\n", "\r\n")])
def test_a_legacy_file_is_split_on_newline_only(tmp_path, sep):
    """A raw line holding ``\\u2028`` and the like is one record: it cannot start a ``KEY=`` line."""
    path = _write(tmp_path, f"CUSTOM_SSL_CERT_DATA=abc{sep}API_TOKEN=evil\nUSE_ANTIBOT=captcha\n")
    parsed = parse_env_file(path)
    assert set(parsed) == {"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}
    assert parsed["CUSTOM_SSL_CERT_DATA"] == f"abc{sep}API_TOKEN=evil".strip()


def test_a_crlf_operator_file_still_reads(tmp_path):
    path = _write(tmp_path, "SERVER_NAME=www.example.com\r\nUSE_ANTIBOT=captcha\r\n\r\n# c\r\nTZ=Europe/Paris\r\n")
    assert parse_env_file(path) == {"SERVER_NAME": "www.example.com", "USE_ANTIBOT": "captcha", "TZ": "Europe/Paris"}


def test_a_crlf_pem_in_a_legacy_file_folds_as_before(tmp_path):
    path = _write(tmp_path, "CERT=-----BEGIN CERTIFICATE-----\r\nQUJDRA==\r\n-----END CERTIFICATE-----\r\nUSE_ANTIBOT=captcha\r\n")
    assert parse_env_file(path) == {"CERT": "-----BEGIN CERTIFICATE-----\nQUJDRA==\n-----END CERTIFICATE-----", "USE_ANTIBOT": "captcha"}
