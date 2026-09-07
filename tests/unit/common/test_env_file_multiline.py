"""Multi-line values survive a round trip through a `variables.env` file (`1218fd9df`).

`variables.env` is written one `KEY=value` line per setting, but settings of type `file` hold
PEM blocks that contain newlines. Every reader used to split on physical lines, so a certificate
arrived truncated to its `-----BEGIN CERTIFICATE-----` header -- and `save_config` then wrote
that truncation back to the database as the operator's declared value, destroying the stored
certificate in the same pass.

The parser is the fix; `Database.save_config`'s truncated-PEM guard is the belt to its braces,
for a file an older writer already flattened. Both are pinned here.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "common" / "utils"))

from env_file import make_key_predicate, parse_env_file, parse_env_lines  # noqa: E402

CERT = "\n".join(
    (
        "-----BEGIN CERTIFICATE-----",
        "MIIBkTCB+wIJAK==",
        "wrapped/base64+line",
        "-----END CERTIFICATE-----",
    )
)


def test_a_pem_block_is_reassembled_without_any_predicate():
    """No caller knows the settings universe here, and the block still comes back whole.

    `-----BEGIN` opens the value and `-----END` closes it, so the bare reader used by the CLI,
    `gen/main.py` and the scheduler is safe on its own.
    """
    lines = ["SERVER_NAME=app.example.com", f"CUSTOM_SSL_CERT_DATA={CERT}", "USE_ANTIBOT=captcha"]
    parsed = parse_env_lines("\n".join(lines).splitlines())
    assert parsed["CUSTOM_SSL_CERT_DATA"] == CERT
    # The settings on either side of the block must not be swallowed by it.
    assert parsed["SERVER_NAME"] == "app.example.com"
    assert parsed["USE_ANTIBOT"] == "captcha"


def test_a_base64_line_ending_in_padding_is_not_read_as_a_key():
    """`MIIBkTCB+wIJAK==` splits on "=" into a token that a naive reader treats as a declaration."""
    parsed = parse_env_lines(f"CUSTOM_SSL_CERT_DATA={CERT}".splitlines())
    assert list(parsed) == ["CUSTOM_SSL_CERT_DATA"]
    assert parsed["CUSTOM_SSL_CERT_DATA"] == CERT


def test_a_known_key_still_ends_a_block_an_older_writer_left_open():
    """Belt: a file already flattened by an older writer must not swallow what follows it."""
    known = make_key_predicate({"USE_ANTIBOT"})
    parsed = parse_env_lines(
        ["CUSTOM_SSL_CERT_DATA=-----BEGIN CERTIFICATE-----", "USE_ANTIBOT=captcha"],
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        known,
    )
    assert parsed["USE_ANTIBOT"] == "captcha"


def test_wrapped_base64_needs_both_predicates():
    """Base64 carries no end marker, so folding it takes knowing the key can span lines."""
    wrapped = "AAAA+BBBB/CCCC\nDDDD+EEEE/FFFF"
    lines = [f"CUSTOM_SSL_CERT_DATA={wrapped}", "USE_ANTIBOT=captcha"]
    body = "\n".join(lines).splitlines()

    bare = parse_env_lines(body)
    assert bare["CUSTOM_SSL_CERT_DATA"] == "AAAA+BBBB/CCCC", "no predicates: historical single-line behaviour"

    folded = parse_env_lines(
        body,
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == wrapped
    assert folded["USE_ANTIBOT"] == "captcha"


def test_an_unknown_env_var_after_a_file_setting_stays_its_own_entry():
    """The 2026-09-01 customcert regression, pinned.

    The scheduler dumps its whole environment into a variables file (`scheduler/main.py`), so a
    `file`-type setting can be followed by env vars that are not settings at all — `TZ`,
    `HOSTNAME`, anything compose injects. Folding those into the value turned a valid single-line
    base64 certificate into `<b64>\\nTZ=Europe/Paris`, which Python 3.14's strict decoder refuses
    with "Excess data after padding" — and the fleet fell back to the internal 10-year cert.
    A `KEY=value` line is a continuation only when it actually looks like wrapped base64.
    """
    value = "QUFBQUFB QkJCQkJC Q0NDQ0ND"
    lines = [f"CUSTOM_SSL_CERT_DATA={value}", "TZ=Europe/Paris", "USE_ANTIBOT=captcha"]
    folded = parse_env_lines(
        lines,
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == value
    assert folded["TZ"] == "Europe/Paris"
    assert folded["USE_ANTIBOT"] == "captcha"


def test_a_pem_chain_keeps_every_certificate():
    """fullchain.pem is the default ACME layout: leaf + intermediate(s) in one value. The first
    `-----END` must not end the value when another `-----BEGIN` follows — dropping the
    intermediates is a silent write-back the config_save truncated-PEM guard cannot see (both
    markers are present, so the mutilated chain looks whole)."""
    chain = "\n".join(
        (
            "-----BEGIN CERTIFICATE-----",
            "AAAAleaf",
            "-----END CERTIFICATE-----",
            "-----BEGIN CERTIFICATE-----",
            "AAAAintermediate",
            "-----END CERTIFICATE-----",
        )
    )
    lines = [f"CUSTOM_SSL_CERT_DATA={chain}", "USE_ANTIBOT=captcha"]
    parsed = parse_env_lines("\n".join(lines).splitlines())
    assert parsed["CUSTOM_SSL_CERT_DATA"] == chain
    assert parsed["USE_ANTIBOT"] == "captcha"


def test_wrapped_base64_with_final_padding_still_folds():
    """The fix must not break what the folding exists for: a wrapped value whose last line ends
    in padding still comes back whole, and the known key after it still ends the block."""
    wrapped = "MIIBkTCB+wIJAK\nQUFBQkJCQ0ND\nZm9vYmFy=="
    lines = [f"CUSTOM_SSL_CERT_DATA={wrapped}", "USE_ANTIBOT=captcha"]
    folded = parse_env_lines(
        "\n".join(lines).splitlines(),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == wrapped
    assert folded["USE_ANTIBOT"] == "captcha"


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("CUSTOM_SSL_CERT_DATA", True),
        # A variables file carries the service prefix ...
        ("www.example.com_CUSTOM_SSL_CERT_DATA", True),
        # ... and the "multiple" numeric suffix.
        ("REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA_2", True),
        ("www.example.com_REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA_2", True),
        ("NOT_A_SETTING", False),
    ],
)
def test_key_predicate_sees_through_prefix_and_suffix(token, expected):
    matches = make_key_predicate({"CUSTOM_SSL_CERT_DATA", "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA"})
    assert matches(token) is expected


def test_comments_and_blank_lines_are_still_skipped(tmp_path):
    path = tmp_path / "variables.env"
    path.write_text(f"# a comment\n\nSERVER_NAME=app.example.com\nCUSTOM_SSL_CERT_DATA={CERT}\n", encoding="utf-8")
    parsed = parse_env_file(path)
    assert sorted(parsed) == ["CUSTOM_SSL_CERT_DATA", "SERVER_NAME"]
    assert parsed["CUSTOM_SSL_CERT_DATA"] == CERT


def test_a_urlsafe_base64_continuation_line_is_not_dropped():
    """#3835 again (port of dev `41f487146` + the fold-in addendum's owed fix).

    Two halves, and only the SECOND block below isolates the alphabet: a continuation line with no
    `KEY=` shape is now kept by the escape clause whatever its alphabet, so the first block passes
    under either regex (it is here as the shape an operator actually writes). The padded last chunk
    in the second block IS declaration-shaped, so it reaches the shape check and pins the urlsafe
    alphabet on its own. The escape clause itself is pinned by
    `test_a_continuation_line_that_could_never_be_a_declaration_is_kept`.
    """
    wrapped = "AAAA-BBBB_CCCC\nDDDD-EEEE_FFFF"
    folded = parse_env_lines(
        "\n".join([f"CUSTOM_SSL_CERT_DATA={wrapped}", "USE_ANTIBOT=captcha"]).splitlines(),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == wrapped
    assert folded["USE_ANTIBOT"] == "captcha"

    # A urlsafe LAST chunk is declaration-shaped (its `==` padding splits into a valid key name),
    # so it is the shape check itself, not the escape above, that has to accept the alphabet.
    padded = "AAAA\nDDD-EEE_FF=="
    folded = parse_env_lines(
        "\n".join([f"CUSTOM_SSL_CERT_DATA={padded}", "USE_ANTIBOT=captcha"]).splitlines(),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == padded
    assert folded["USE_ANTIBOT"] == "captcha"


def test_a_bare_declaration_off_the_base64_boundary_ends_the_value():
    """A `NAME=` line with no payload can only be a declaration unless it lands the folded value
    on a multiple of four -- where a base64 pad has to fall. Off that boundary it declares, so an
    empty foreign variable after a `file` setting is kept instead of corrupting the certificate."""
    folded = parse_env_lines(
        ["CUSTOM_SSL_CERT_DATA=AAAA", "TZ=", "USE_ANTIBOT=captcha"],
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == "AAAA"
    assert folded["TZ"] == ""
    assert folded["USE_ANTIBOT"] == "captcha"


def test_the_last_chunk_of_a_wrapped_payload_still_folds():
    """The other side of the same rule, and the documented ceiling: a padded last chunk lands the
    payload on the boundary, so it is folded -- which also folds the one bare declaration in four
    whose own name lands there (here `CCC=`: 8 payload chars + a 4-char chunk = 12, a multiple of
    four). Keeping a wrapped value whole is the rarer-trigger choice."""
    folded = parse_env_lines(
        ["CUSTOM_SSL_CERT_DATA=AAAABBBB", "CCC=", "USE_ANTIBOT=captcha"],
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == "AAAABBBB\nCCC="
    assert "CCC" not in folded
    assert folded["USE_ANTIBOT"] == "captcha"


def test_a_continuation_line_that_could_never_be_a_declaration_is_kept():
    """The shape check has one job: disambiguate a line that COULD be read as a declaration.

    A chunk with no `KEY=` shape cannot end a value, so requiring the base64 shape of it only ever
    drops payload. `variables.env` writers wrap on whitespace as well as on newlines, so a chunk
    that carries an inner space fails `B64_LINE_RX` while still being pure payload.
    """
    wrapped = "QUFB QkJD\nQ0ND RERF"
    folded = parse_env_lines(
        "\n".join([f"CUSTOM_SSL_CERT_DATA={wrapped}", "USE_ANTIBOT=captcha"]).splitlines(),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA"}),
        make_key_predicate({"CUSTOM_SSL_CERT_DATA", "USE_ANTIBOT"}),
    )
    assert folded["CUSTOM_SSL_CERT_DATA"] == wrapped
    assert folded["USE_ANTIBOT"] == "captcha"
