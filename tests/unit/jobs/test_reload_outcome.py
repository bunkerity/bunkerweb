"""reload_outcome: what a reload answer means for the failover banner, and how the banner text is stored.

`classify_reload_responses` decides refused / accepted / ignored per host. The stored
`failover_message` is a per-host map rendered so that it parses back without guessing: a block starts
at a non-indented `"<host> - <first line>"` line and every continuation line is indented by two
spaces. Whatever does not parse cleanly (rows written by 1.6.x or by the old push-configs, which
joined multi-line NGINX output unindented) is kept as one opaque `(earlier)` entry.
"""

from unittest.mock import Mock

import pytest

from reload_outcome import (
    BUSY_REPLIES,
    LEGACY_HOST,
    classify_reload_responses,
    parse_failover_message,
    record_reload_responses,
    render_failover_message,
)

OK = {"status": "success", "msg": "reloaded"}
REFUSED = {"status": "error", "msg": 'nginx: [emerg] unknown directive "bogus" in /etc/nginx/x.conf:3'}


class TestClassify:
    def test_success_is_accepted_and_anything_else_is_refused_with_its_message(self):
        assert classify_reload_responses({"a": OK, "b": REFUSED}) == {"a": None, "b": REFUSED["msg"]}

    def test_a_refusal_without_a_message_still_counts(self):
        assert classify_reload_responses({"a": {"status": "error"}}) == {"a": "reload refused"}

    @pytest.mark.parametrize("reply", BUSY_REPLIES)
    def test_a_busy_instance_is_ignored_not_refused(self, reply):
        """The 503 an instance answers while a configuration swap holds its lock is a transient
        condition, never a rejected configuration."""
        assert classify_reload_responses({"a": {"status": "error", "msg": reply}}) == {}

    def test_the_busy_prefix_with_a_detail_is_ignored_too(self):
        assert classify_reload_responses({"a": {"status": "error", "msg": "cannot take the swap lock: no memory"}}) == {}

    def test_an_unanswered_host_is_dropped(self):
        assert classify_reload_responses({"a": None, "b": {}, "c": "garbage"}) == {}
        assert classify_reload_responses(None) == {}
        assert classify_reload_responses({}) == {}

    def test_a_host_with_whitespace_cannot_break_the_storage_format(self):
        (host,) = classify_reload_responses({"bad host\nname": OK})
        assert not any(c.isspace() for c in host)


MESSAGES = [
    "single line",
    "first\nsecond\nthird",
    "  already indented\n    deeper",
    "trailing newline\n",
    "blank\n\nline between",
    "mentions another host:\nbw-2 - not a block start\nbw-9 - neither",
    "bw-2 - looks like a block at the very start",
    "windows\r\nline endings",
]


class TestRoundTrip:
    @pytest.mark.parametrize("message", MESSAGES)
    def test_a_single_entry_round_trips(self, message):
        text = render_failover_message({"bw-1": message})
        assert parse_failover_message(text) == {"bw-1": message}

    def test_several_hosts_round_trip_in_a_stable_order(self):
        entries = {"bw-3": "c\nc2", "bw-1": "a", "bw-2": "bw-1 - b\nb2"}
        text = render_failover_message(entries)
        assert parse_failover_message(text) == entries
        assert render_failover_message(dict(reversed(entries.items()))) == text

    @pytest.mark.parametrize("gone", ["bw-1", "bw-2", "bw-3"])
    def test_removing_the_first_middle_or_last_host_leaves_the_others_intact(self, gone):
        entries = {"bw-1": "a\n  a2", "bw-2": "b\nbw-3 - fake", "bw-3": "c"}
        parsed = parse_failover_message(render_failover_message(entries))
        del parsed[gone]
        expected = {h: m for h, m in entries.items() if h != gone}
        assert parse_failover_message(render_failover_message(parsed)) == expected

    def test_empty_means_no_entry(self):
        assert render_failover_message({}) == ""
        assert parse_failover_message("") == {}
        assert parse_failover_message("  \n ") == {}

    def test_the_banner_reads_naturally_for_a_single_line_message(self):
        assert render_failover_message({"bw-1": "bad"}) == "bw-1 - bad"


class TestLegacyText:
    LEGACY = "bw-1 - nginx: [emerg] bad directive\nin /etc/nginx/a.conf:3\nbw-2 - nginx: [emerg] other\nin /etc/nginx/b.conf:7"

    def test_the_unindented_multi_line_text_of_the_old_format_does_not_parse(self):
        assert parse_failover_message(self.LEGACY) is None

    @pytest.mark.parametrize("text", ["free text", "  starts indented", "bw-1 - a\nbw-1 - duplicate host", "bw-1 - a\n\nblank line unindented"])
    def test_text_that_is_not_the_new_format_is_opaque(self, text):
        assert parse_failover_message(text) is None

    def test_the_old_single_line_per_host_format_is_the_new_format(self):
        assert parse_failover_message("bw-1 - a\nbw-2 - b") == {"bw-1": "a", "bw-2": "b"}

    def test_an_opaque_entry_round_trips_byte_for_byte(self):
        text = render_failover_message({LEGACY_HOST: self.LEGACY, "bw-3": "new"})
        assert parse_failover_message(text) == {LEGACY_HOST: self.LEGACY, "bw-3": "new"}


class TestRecordWrapper:
    def test_it_hands_the_classified_results_to_the_database(self):
        db = Mock()
        db.record_reload_outcome.return_value = ""
        record_reload_responses(db, {"a": OK, "b": REFUSED, "c": {"status": "error", "msg": BUSY_REPLIES[0]}}, fleet=True)
        db.record_reload_outcome.assert_called_once_with({"a": None, "b": REFUSED["msg"]}, fleet=True)

    def test_nothing_that_answered_means_no_write(self):
        db = Mock()
        record_reload_responses(db, {}, fleet=True)
        record_reload_responses(db, {"a": {"status": "error", "msg": BUSY_REPLIES[0]}}, fleet=True)
        db.record_reload_outcome.assert_not_called()

    def test_no_database_is_a_no_op(self):
        record_reload_responses(None, {"a": OK})

    def test_a_recording_error_is_logged_and_never_raised(self):
        db, logger = Mock(), Mock()
        db.record_reload_outcome.return_value = "boom"
        record_reload_responses(db, {"a": OK}, logger=logger)
        logger.error.assert_called_once()

        db.record_reload_outcome.side_effect = RuntimeError("down")
        record_reload_responses(db, {"a": OK}, logger=logger)
        assert logger.error.call_count == 2

    def test_a_read_only_database_is_a_quiet_no_op(self):
        db, logger = Mock(), Mock()
        db.record_reload_outcome.return_value = "The database is read-only, the changes will not be saved"
        record_reload_responses(db, {"a": OK}, logger=logger)
        logger.error.assert_not_called()
        logger.debug.assert_called()
