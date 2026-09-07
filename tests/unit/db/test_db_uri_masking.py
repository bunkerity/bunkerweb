"""`mask_db_uri` and `scrub_db_secret` — the two halves of keeping the DB password out of the logs.

`Database.py` logged `DATABASE_URI` verbatim at three sites, so the password reached every log sink
the scheduler, worker and UI write to. Masking the URI is the obvious half.

The second half is not obvious and is the reason `scrub_db_secret` exists. With an **unencoded `@`**
in the password, SQLAlchemy splits the authority at the *first* `@`: everything after it becomes the
host. The driver is then handed the tail of the password as a hostname and echoes it back in its own
error text --

    (2003, "Can't connect to MySQL server on 'ssw0rd!@127.0.0.1' (-2)")

-- which `mask_db_uri` never sees, because that string is not a URI and never passed through it. So
the scrub matches **suffixes** of the secret, not just the whole thing.

These tests exist because a mutation showed the gap: neutering `scrub_db_secret` to `return text`
left every marker in the staleness guard present and the whole `tests/unit/db` selection green. A
call site that is asserted to exist, calling a function whose behaviour is asserted nowhere, is not
coverage.
"""

import sys
from pathlib import Path

import pytest

_DB = str(Path(__file__).resolve().parents[3] / "src" / "common" / "db")
if _DB not in sys.path:
    sys.path.insert(0, _DB)

from Database import mask_db_uri, scrub_db_secret  # noqa: E402

SECRET = "P@ssw0rd!"
URI = f"mariadb+pymysql://bunkerweb:{SECRET}@127.0.0.1:3306/db"


class TestMaskDbUri:
    def test_a_plain_password_is_replaced(self):
        masked = mask_db_uri("postgresql://bunkerweb:hunter2@db:5432/bunkerweb")

        assert "hunter2" not in masked
        assert masked.startswith("postgresql://bunkerweb:")
        assert masked.endswith("@db:5432/bunkerweb")

    def test_an_unencoded_at_sign_does_not_leak_the_tail(self):
        """The case the second pass exists for: `make_url` hides only up to the first `@`."""
        masked = mask_db_uri(URI)

        assert SECRET not in masked, masked
        assert "ssw0rd" not in masked, f"the tail of the password survived masking: {masked}"
        assert "127.0.0.1:3306/db" in masked, f"masking ate the host: {masked}"

    def test_a_uri_that_does_not_parse_is_still_masked(self):
        """`make_url` raises on a bad port; the regex pass must still run."""
        masked = mask_db_uri("mysql://user:s3cret@host:not-a-port/db")

        assert "s3cret" not in masked, masked

    def test_a_uri_without_a_password_is_left_alone(self):
        assert mask_db_uri("sqlite:////var/lib/bunkerweb/db.sqlite3") == "sqlite:////var/lib/bunkerweb/db.sqlite3"

    @pytest.mark.parametrize("value", ["", None])
    def test_empty_input_is_returned_unchanged(self, value):
        assert mask_db_uri(value) == value

    def test_an_at_sign_in_the_path_does_not_drag_the_host_into_the_mask(self):
        masked = mask_db_uri("postgresql://bunkerweb:hunter2@db:5432/weird@name")

        assert "hunter2" not in masked
        assert "db:5432" in masked, f"the host was masked away: {masked}"


class TestScrubDbSecret:
    def test_the_whole_secret_is_removed_from_driver_text(self):
        text = f"could not connect using password {SECRET} to 127.0.0.1"

        scrubbed = scrub_db_secret(text, URI)

        assert SECRET not in scrubbed
        assert "***" in scrubbed

    def test_a_suffix_of_the_secret_is_removed(self):
        """The real shape: the driver was handed the tail of the password as a hostname."""
        text = "(2003, \"Can't connect to MySQL server on 'ssw0rd!@127.0.0.1' (-2)\")"

        scrubbed = scrub_db_secret(text, URI)

        assert "ssw0rd" not in scrubbed, f"the echoed password tail survived: {scrubbed}"
        assert "2003" in scrubbed, "the scrub destroyed the diagnostic instead of the secret"

    def test_text_without_the_secret_is_untouched(self):
        text = "(2005, \"Unknown server host 'db' (-2)\")"

        assert scrub_db_secret(text, URI) == text

    def test_a_short_fragment_is_not_scrubbed_away(self):
        """Four characters is the floor: scrubbing 2-3 character runs would redact ordinary words."""
        scrubbed = scrub_db_secret("connection refused", "postgresql://u:abc@h/db")

        assert scrubbed == "connection refused"

    @pytest.mark.parametrize(
        "text,uri",
        [("", URI), ("some error", ""), ("", "")],
    )
    def test_empty_inputs_are_safe(self, text, uri):
        assert scrub_db_secret(text, uri) == text

    def test_a_uri_with_no_password_scrubs_nothing(self):
        text = "connection to server at 'db' failed"

        assert scrub_db_secret(text, "postgresql://bunkerweb@db:5432/bunkerweb") == text


class TestMaskDbUriCredentialShapes:
    """Port of dev `dfa3273eb`: three shapes the original pair could not mask."""

    def test_a_password_containing_a_slash_is_masked(self):
        """`openssl rand -base64` produces "/" routinely. Such a password is percent-encoded by
        `render_as_string`, so the rendered string differs from the input and the round-trip guard
        falls through to the authority regex — whose class must be wide enough to hold it."""
        masked = mask_db_uri("postgresql://bunkerweb:ab/cd?ef@db:5432/bunkerweb")

        assert "ab/cd" not in masked, f"the password survived masking: {masked}"
        assert "db:5432" in masked, f"masking ate the host: {masked}"

    def test_a_password_in_the_query_string_is_masked(self):
        """`?password=` is where several drivers take the credential, and
        `render_as_string(hide_password=True)` leaves it untouched."""
        masked = mask_db_uri("mariadb+pymysql://bunkerweb@db:3306/bunkerweb?password=hunter2&charset=utf8mb4")

        assert "hunter2" not in masked, f"the query-string credential survived: {masked}"
        assert "charset=utf8mb4" in masked, f"masking ate the rest of the query: {masked}"

    @pytest.mark.parametrize("param", ("password", "sslpassword", "PWD", "api_key", "token"))
    def test_every_credential_parameter_spelling_is_masked(self, param):
        masked = mask_db_uri(f"postgresql://bunkerweb@db/bunkerweb?{param}=s3cret")

        assert "s3cret" not in masked, f"{param} survived: {masked}"

    def test_an_ordinary_query_parameter_is_left_alone(self):
        uri = "postgresql://bunkerweb@db/bunkerweb?sslmode=require&connect_timeout=5"

        assert mask_db_uri(uri) == uri

    def test_a_username_holding_an_at_sign_still_gets_its_password_masked(self):
        """The username class is SQLAlchemy's own on purpose: a narrower one makes the whole match
        fail on a DSN that parses, and the password then reaches the log in cleartext."""
        masked = mask_db_uri("postgresql://user@corp:hunter2@db:5432/bunkerweb")

        assert "hunter2" not in masked, f"the password survived: {masked}"


def test_a_username_holding_an_at_sign_still_scrubs_the_drivers_echo():
    """`scrub_db_secret` extracts the secret with the same authority span as the mask. A username
    class narrower than SQLAlchemy's (Azure hands out `user@server` logins) makes the extraction
    match nothing, and the driver's echo of the password then reaches the log untouched."""
    uri = "postgresql://bunkerweb@corp:hunter2@db:5432/bunkerweb"

    scrubbed = scrub_db_secret("FATAL: password authentication failed, tried hunter2", uri)

    assert "hunter2" not in scrubbed, f"the echoed password survived: {scrubbed}"
