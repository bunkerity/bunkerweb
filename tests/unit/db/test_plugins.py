"""DatabasePluginsMixin — plugin reads, deletion, pages and error counting."""

from datetime import datetime, timezone

from fixtures.seed import add_plugin_page, seed_minimal

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


class TestDeletePlugin:
    def test_delete_cascades(self, db):
        seed_minimal(db)
        assert db.delete_plugin("general", "manual") == ""
        assert db.get_plugins() == []  # plugin and its settings/jobs are gone

    def test_delete_not_found(self, db):
        seed_minimal(db)
        assert db.delete_plugin("general", "ui") == "Plugin with id general and method ui not found"

    def test_a_core_plugin_deletion_raises_no_plugin_change_flag(self, db):
        seed_minimal(db)
        assert db.delete_plugin("general", "manual") == ""
        after = db.get_metadata()
        assert after["external_plugins_changed"] is False and after["pro_plugins_changed"] is False


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
