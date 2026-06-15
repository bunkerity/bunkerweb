"""DatabasePluginsMixin — plugin reads, deletion, pages and error counting."""

from datetime import datetime, timezone

from fixtures.seed import add_plugin, add_plugin_page, seed_minimal

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestGetPlugins:
    def test_empty(self, db):
        assert db.get_plugins() == []

    def test_returns_seeded_with_settings(self, db):
        seed_minimal(db)  # plugin 'general' (core) + settings
        plugins = db.get_plugins()
        assert [p["id"] for p in plugins] == ["general"]
        general = plugins[0]
        assert general["type"] == "core"
        assert general["page"] is False
        assert "MULTISITE" in general["settings"]

    def test_type_filter(self, db):
        seed_minimal(db)
        add_plugin(db, "extplug", type="external", method="ui")
        add_plugin(db, "proplug", type="pro", method="manual")  # 'method' must be a METHODS_ENUM value; 'pro' is a type
        assert {p["id"] for p in db.get_plugins()} == {"general", "extplug", "proplug"}
        assert [p["id"] for p in db.get_plugins(_type="external")] == ["extplug"]  # external+ui bucket
        assert [p["id"] for p in db.get_plugins(_type="pro")] == ["proplug"]


class TestDeletePlugin:
    def test_delete_cascades(self, db):
        seed_minimal(db)
        assert db.delete_plugin("general", "manual") == ""
        assert db.get_plugins() == []  # plugin and its settings/jobs are gone

    def test_delete_not_found(self, db):
        seed_minimal(db)
        assert db.delete_plugin("general", "ui") == "Plugin with id general and method ui not found"


class TestPluginPageAndErrors:
    def test_get_plugin_page(self, db):
        seed_minimal(db)
        assert db.get_plugin_page("general") is None
        add_plugin_page(db, "general", data=b"<html>")
        assert db.get_plugin_page("general") == b"<html>"

    def test_plugins_errors_counts_latest_failed_runs(self, db):
        seed_minimal(db)  # job 'testjob'
        assert db.get_plugins_errors() == 0
        db.add_job_run("testjob", False, DT)
        assert db.get_plugins_errors() == 1
