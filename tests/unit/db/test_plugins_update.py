"""Integration tier — DatabasePluginsUpdateMixin.update_external_plugins (plugin tarball sync).

Syncs external/pro plugin payloads (row + settings + jobs) into the DB. Exercised end-to-end
on every engine: create -> idempotent -> version update -> delete-missing prune. Page sync is
skipped (page=False) so no real tar extraction is needed. Marked `slow`.
"""

import pytest

from fixtures.seed import make_external_plugin

pytestmark = pytest.mark.slow


class TestUpdateExternalPlugins:
    def test_creates_external_plugin_with_settings(self, db):
        assert db.update_external_plugins([make_external_plugin("extplug")], _type="external") == ""
        ext = db.get_plugins(_type="external")
        plug = next(p for p in ext if p["id"] == "extplug")
        assert plug["type"] == "external"
        assert "EXTPLUG_GLOBAL" in plug["settings"]

    def test_idempotent(self, db):
        db.update_external_plugins([make_external_plugin("extplug")], _type="external")
        db.update_external_plugins([make_external_plugin("extplug")], _type="external")
        assert len([p for p in db.get_plugins(_type="external") if p["id"] == "extplug"]) == 1

    def test_version_update(self, db):
        db.update_external_plugins([make_external_plugin("extplug", version="1.0")], _type="external")
        db.update_external_plugins([make_external_plugin("extplug", version="2.0")], _type="external")
        assert next(p for p in db.get_plugins(_type="external") if p["id"] == "extplug")["version"] == "2.0"

    def test_delete_missing_prunes(self, db):
        db.update_external_plugins([make_external_plugin("e1"), make_external_plugin("e2")], _type="external")
        assert {"e1", "e2"} <= {p["id"] for p in db.get_plugins(_type="external")}
        db.update_external_plugins([make_external_plugin("e1")], _type="external", delete_missing=True)
        ids = {p["id"] for p in db.get_plugins(_type="external")}
        assert "e1" in ids and "e2" not in ids
