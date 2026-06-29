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


def _select_setting(id_, options, *, case_insensitive=None):
    s = {
        "id": id_,
        "context": "global",
        "default": options[0],
        "help": "h",
        "label": "L",
        "regex": "^(" + "|".join(options) + ")$",
        "type": "select",
        "select": options,
    }
    if case_insensitive is not None:
        s["case_insensitive"] = case_insensitive
    return s


class TestCaseInsensitiveFlag:
    """A3: the per-setting ``case_insensitive`` column round-trips through plugin sync (new +
    update-diff) and is serialized back by get_plugins for select/multiselect."""

    def test_flag_round_trips_on_insert(self, db):
        p = make_external_plugin("ciplug")
        p["settings"] = {"CIPLUG_PICK": _select_setting("ciplug-pick", ["modern", "old"], case_insensitive=True)}
        assert db.update_external_plugins([p], _type="external") == ""
        sd = next(pl for pl in db.get_plugins(_type="external") if pl["id"] == "ciplug")["settings"]["CIPLUG_PICK"]
        assert sd["case_insensitive"] is True
        assert sd["select"] == ["modern", "old"]

    def test_absent_flag_defaults_false(self, db):
        p = make_external_plugin("plainplug")
        p["settings"] = {"PLAINPLUG_PICK": _select_setting("plainplug-pick", ["a", "b"])}  # no flag declared
        assert db.update_external_plugins([p], _type="external") == ""
        sd = next(pl for pl in db.get_plugins(_type="external") if pl["id"] == "plainplug")["settings"]["PLAINPLUG_PICK"]
        assert sd["case_insensitive"] is False

    def test_flag_update_diff_applies(self, db):
        # v1 without the flag -> False; v2 flips it on -> the sync update-diff must persist it.
        p1 = make_external_plugin("evolve", version="1.0")
        p1["settings"] = {"EVOLVE_PICK": _select_setting("evolve-pick", ["modern", "old"])}
        db.update_external_plugins([p1], _type="external")
        assert next(pl for pl in db.get_plugins(_type="external") if pl["id"] == "evolve")["settings"]["EVOLVE_PICK"]["case_insensitive"] is False

        p2 = make_external_plugin("evolve", version="2.0")
        p2["settings"] = {"EVOLVE_PICK": _select_setting("evolve-pick", ["modern", "old"], case_insensitive=True)}
        db.update_external_plugins([p2], _type="external")
        assert next(pl for pl in db.get_plugins(_type="external") if pl["id"] == "evolve")["settings"]["EVOLVE_PICK"]["case_insensitive"] is True
