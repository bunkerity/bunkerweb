"""UIPreferencesMethodsMixin — the per-user key/value store (JSON-backed).

`key` is a shared namespace: DataTables ids and feature keys live in the same rows, which
is why the setter upserts and the getter takes an explicit default.
"""

from sqlalchemy import select

from model import UserPreferences  # type: ignore

from fixtures.seed import add_ui_user, session


class TestUserPreferences:
    def test_set_missing_user(self, ui_db):
        assert ui_db.set_ui_user_preference("ghost", "t", {"c": True}) == "User ghost doesn't exist"

    def test_get_creates_default_then_set_roundtrips(self, ui_db):
        add_ui_user(ui_db, "bob")
        # First read of an unknown key returns the (empty) default AND lazily creates the row.
        assert ui_db.get_ui_user_preference("bob", "mytable") == {}
        assert ui_db.set_ui_user_preference("bob", "mytable", {"col1": True, "col2": False}) == ""
        assert ui_db.get_ui_user_preference("bob", "mytable") == {"col1": True, "col2": False}

    def test_set_upserts_a_key_that_was_never_read(self, ui_db):
        """A feature key has no seeded row, so refusing to create one made the store unusable
        for anything but DataTables. The API-side mixin has always upserted here."""
        add_ui_user(ui_db, "bob")
        assert ui_db.set_ui_user_preference("bob", "never_fetched", {"c": True}) == ""
        assert ui_db.get_ui_user_preference("bob", "never_fetched") == {"c": True}

    def test_explicit_default_is_returned_and_stored_for_a_non_table_key(self, ui_db):
        add_ui_user(ui_db, "bob")
        blob = {"opened_at": 1785396767, "dismissed_at": None, "acked_hints": ["home"]}
        assert ui_db.get_ui_user_preference("bob", "onboarding", default=blob) == blob
        # Seeded, so a later read no longer needs the caller to pass the default back in.
        assert ui_db.get_ui_user_preference("bob", "onboarding") == blob

    def test_a_table_id_still_falls_back_to_its_datatables_defaults(self, ui_db):
        """`COLUMNS_PREFERENCES_DEFAULTS` remains the fallback when no default is passed."""
        from app.utils import COLUMNS_PREFERENCES_DEFAULTS

        add_ui_user(ui_db, "bob")
        table = next(iter(COLUMNS_PREFERENCES_DEFAULTS))
        assert ui_db.get_ui_user_preference("bob", table) == COLUMNS_PREFERENCES_DEFAULTS[table]

    def test_a_non_dict_value_survives_the_json_column(self, ui_db):
        """Feature keys are not bool maps; the store must not coerce them."""
        add_ui_user(ui_db, "bob")
        assert ui_db.set_ui_user_preference("bob", "seen_versions", ["1.6.13", "1.7.0"]) == ""
        assert ui_db.get_ui_user_preference("bob", "seen_versions") == ["1.6.13", "1.7.0"]


def _stored_keys(ui_db, username):
    """Read the rows directly. `get_ui_user_preference` lazily creates and returns a default
    on miss, so going through the getter cannot tell a seeded row from a fallback -- an
    earlier version of these tests did exactly that and passed against the broken guard."""
    with session(ui_db) as s:
        return {row.key for row in s.scalars(select(UserPreferences).filter_by(user_name=username))}


class TestDefaultSeeding:
    """`get_ui_user` tops up the DataTables defaults. Once `key` became a shared namespace,
    "does this user have any preferences at all?" stopped being a safe proxy for "have the
    table defaults been seeded?"."""

    def test_defaults_are_seeded_on_first_read(self, ui_db):
        from app.utils import COLUMNS_PREFERENCES_DEFAULTS

        add_ui_user(ui_db, "bob")
        assert _stored_keys(ui_db, "bob") == set()

        ui_db.get_ui_user(username="bob")

        assert _stored_keys(ui_db, "bob") == set(COLUMNS_PREFERENCES_DEFAULTS)

    def test_a_feature_key_written_first_does_not_suppress_the_seeding(self, ui_db):
        """The bug an `if not user.preferences` guard reintroduces: onboarding writes its key
        before the user ever opens a table, so the row set is no longer empty and every
        DataTables default is skipped for good."""
        from app.utils import COLUMNS_PREFERENCES_DEFAULTS

        add_ui_user(ui_db, "bob")
        assert ui_db.set_ui_user_preference("bob", "onboarding", {"opened_at": 1}) == ""

        ui_db.get_ui_user(username="bob")

        assert _stored_keys(ui_db, "bob") == set(COLUMNS_PREFERENCES_DEFAULTS) | {"onboarding"}
        # ... and the feature key it was written alongside is untouched.
        assert ui_db.get_ui_user_preference("bob", "onboarding") == {"opened_at": 1}
