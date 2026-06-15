"""UIPreferencesMethodsMixin — per-user column preferences (JSON-backed)."""

from fixtures.seed import add_ui_user


class TestColumnsPreferences:
    def test_update_missing_user(self, ui_db):
        assert ui_db.update_ui_user_columns_preferences("ghost", "t", {"c": True}) == "User ghost doesn't exist"

    def test_get_creates_default_then_update_roundtrips(self, ui_db):
        add_ui_user(ui_db, "bob")
        # First read of an unknown table returns the (empty) default AND lazily creates the row.
        assert ui_db.get_ui_user_columns_preferences("bob", "mytable") == {}
        # Row now exists -> update succeeds and round-trips through the JSONText column.
        assert ui_db.update_ui_user_columns_preferences("bob", "mytable", {"col1": True, "col2": False}) == ""
        assert ui_db.get_ui_user_columns_preferences("bob", "mytable") == {"col1": True, "col2": False}

    def test_update_table_never_fetched(self, ui_db):
        add_ui_user(ui_db, "bob")
        assert ui_db.update_ui_user_columns_preferences("bob", "never_fetched", {"c": True}) == "Table never_fetched doesn't exist"
