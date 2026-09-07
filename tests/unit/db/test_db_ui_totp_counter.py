"""The TOTP replay counter lives in the database, and spending one is a single UPDATE.

`use_ui_user_totp` is the whole replay defence for two-factor logins: the UPDATE only matches a
row whose stored counter is still older than the one being spent, so of two requests carrying the
same six digits exactly one updates a row. Before the counter moved here it was a JSON file local
to one gunicorn worker, which every other worker -- and every other UI replica -- ignored.

The seeding half is `update_ui_user`: storing a new secret restarts the counter at the current
period, so the code the user typed to enrol cannot be replayed as a login for the rest of its
window, and clearing the secret clears the counter with it.
"""

from time import time


def _counter_now() -> int:
    return int((time() + 3) // 30)


class TestUseUiUserTotp:
    def test_a_counter_is_spent_once(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "SEC", 100) is True
        # The replay: same code, same counter, a second time.
        assert db.use_ui_user_totp("alice", "SEC", 100) is False

    def test_an_older_counter_is_refused_and_a_newer_one_accepted(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "SEC", 100) is True
        assert db.use_ui_user_totp("alice", "SEC", 99) is False
        assert db.use_ui_user_totp("alice", "SEC", 101) is True

    def test_counters_are_per_user(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        db.create_ui_user("bob", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "SEC", 100) is True
        assert db.use_ui_user_totp("bob", "SEC", 100) is True
        assert db.use_ui_user_totp("bob", "SEC", 100) is False

    def test_a_counter_minted_against_another_secret_spends_nothing(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "OTHER", 100) is False
        # The real secret is untouched by the refusal above.
        assert db.use_ui_user_totp("alice", "SEC", 100) is True

    def test_unknown_user_and_malformed_input_are_refused(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("ghost", "SEC", 100) is False
        assert db.use_ui_user_totp("alice", "", 100) is False
        assert db.use_ui_user_totp("alice", "SEC", -1) is False
        # `True` is an int to Python; it must not pass as counter 1.
        assert db.use_ui_user_totp("alice", "SEC", True) is False
        assert db.use_ui_user_totp("alice", "SEC", "100") is False

    def test_readonly_refuses_instead_of_pretending_to_consume(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        db.readonly = True
        try:
            assert db.use_ui_user_totp("alice", "SEC", 100) is False
        finally:
            db.readonly = False
        # Nothing was written, so the counter is still free afterwards.
        assert db.use_ui_user_totp("alice", "SEC", 100) is True


class TestCounterSeeding:
    def test_storing_a_new_secret_restarts_the_counter_at_the_current_period(self, db):
        db.create_ui_user("alice", b"h", [])
        assert db.update_ui_user("alice", b"h", "SEC") == ""
        # The enrolment code -- and every other code still inside its window -- is already spent.
        assert db.use_ui_user_totp("alice", "SEC", _counter_now() - 3) is False
        assert db.use_ui_user_totp("alice", "SEC", _counter_now() + 1) is True

    def test_clearing_the_secret_clears_the_counter(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "SEC", 10**9) is True
        assert db.update_ui_user("alice", b"h", None) == ""
        # Re-enrolling with the same secret must not inherit the old, far-future counter.
        assert db.update_ui_user("alice", b"h", "SEC") == ""
        assert db.use_ui_user_totp("alice", "SEC", _counter_now() + 1) is True

    def test_an_unchanged_secret_leaves_the_counter_alone(self, db):
        db.create_ui_user("alice", b"h", [], totp_secret="SEC")
        assert db.use_ui_user_totp("alice", "SEC", 10**9) is True
        assert db.update_ui_user("alice", b"h", "SEC", theme="dark") == ""
        # A profile edit that does not touch 2FA must not hand a replayed code a fresh window.
        assert db.use_ui_user_totp("alice", "SEC", 10**9) is False
