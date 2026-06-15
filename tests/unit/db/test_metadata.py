"""DatabaseMetadataMixin — versioning, the singleton metadata row, change flags.

Runs against every selected engine via the ``db`` fixture.
"""

from fixtures.seed import seed_minimal


class TestInitializeDb:
    def test_creates_singleton(self, db):
        assert db.initialize_db("1.7.0", "Docker") == ""
        md = db.get_metadata()
        assert md["is_initialized"] is True
        assert md["version"] == "1.7.0"
        assert md["integration"] == "Docker"
        assert md["default"] is False

    def test_idempotent_updates_not_duplicates(self, db):
        db.initialize_db("1.7.0", "Docker")
        assert db.initialize_db("1.7.1", "Kubernetes") == ""
        md = db.get_metadata()
        assert md["version"] == "1.7.1"
        assert md["integration"] == "Kubernetes"
        # get_version reads row id=1 — proves we updated rather than inserted a 2nd row.
        assert db.get_version() == "1.7.1"


class TestGetVersion:
    def test_default_when_empty(self, db):
        assert db.get_version() == "1.6.12~rc1"

    def test_after_init(self, db):
        db.initialize_db("9.9.9", "Docker")
        assert db.get_version() == "9.9.9"


class TestGetMetadata:
    def test_default_when_empty(self, db):
        md = db.get_metadata()
        assert md["default"] is True
        assert md["is_initialized"] is False
        # database_version is read live from the engine even with no metadata row.
        assert isinstance(md["database_version"], str) and md["database_version"]
        assert md["database_version"] != "Unknown"

    def test_populated(self, db):
        db.initialize_db("1.7.0", "Docker")
        md = db.get_metadata()
        assert md["default"] is False
        assert md["scheduler_first_start"] is True


class TestSetMetadata:
    def test_empty_db_message(self, db):
        assert db.set_metadata({"is_pro": True}) == "The metadata are not set yet, try again"

    def test_sets_known_and_skips_unknown_keys(self, db):
        db.initialize_db("1.7.0", "Docker")
        # an unknown key is warned about and skipped, not an error.
        assert db.set_metadata({"is_pro": True, "does_not_exist": 123}) == ""
        assert db.get_metadata()["is_pro"] is True


class TestCheckedChanges:
    def test_empty_db_message(self, db):
        assert db.checked_changes(["custom_configs"], value=True) == "The metadata are not set yet, try again"

    def test_sets_custom_configs_flag(self, db):
        db.initialize_db("1.7.0", "Docker")
        assert db.checked_changes(["custom_configs"], value=True) == ""
        assert db.get_metadata()["custom_configs_changed"] is True

    def test_first_config_saved_latches_true(self, db):
        db.initialize_db("1.7.0", "Docker")
        assert db.get_metadata()["first_config_saved"] is False
        assert db.checked_changes(["config"]) == ""
        assert db.get_metadata()["first_config_saved"] is True

    def test_plugins_changes_all(self, db):
        seed_minimal(db)  # creates plugin 'general' + Metadata row
        assert db.checked_changes(plugins_changes="all", value=True) == ""
        assert "general" in db.get_metadata()["plugins_config_changed"]

    def test_plugins_changes_subset(self, db):
        seed_minimal(db)
        assert db.checked_changes(plugins_changes={"general"}, value=True) == ""
        assert "general" in db.get_metadata()["plugins_config_changed"]
