"""Integration tier — DatabasePluginsUpdateMixin.update_external_plugins (plugin tarball sync).

Syncs external/pro plugin payloads (row + settings + jobs) into the DB. Exercised end-to-end
on every engine: create -> idempotent -> version update -> delete-missing prune. Page sync is
skipped (page=False) so no real tar extraction is needed. Marked `slow`.
"""

import tempfile
from pathlib import Path

import pytest

from common_utils import create_plugin_tar_gz  # type: ignore
from fixtures.seed import make_external_plugin

pytestmark = pytest.mark.slow


def _ext_plugin_with_archive(plugin_id, *, files=None, icon=None, version="1.0"):
    """External plugin dict carrying a REAL tar.gz ``data`` blob built from ``files``
    ({relpath: bytes}), so the icon-file detection path runs for real."""
    d = Path(tempfile.mkdtemp()) / plugin_id
    d.mkdir(parents=True)
    (d / "plugin.json").write_text(f'{{"id":"{plugin_id}"}}')
    for name, content in (files or {}).items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    blob = create_plugin_tar_gz(d, arc_root=d.name).getvalue()
    plugin = make_external_plugin(plugin_id, version=version, data=blob, checksum=f"sum-{version}-{bool(files)}-{icon}")
    if icon is not None:
        plugin["icon"] = icon
    return plugin


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

    def test_disabled_plugin_absent_from_list_is_retained(self, db):
        # A disabled plugin is intentionally not on the filesystem, so it is legitimately absent
        # from the incoming (FS-derived) list. delete_missing must NOT cascade-delete it — the row
        # AND its settings survive so re-enabling restores the plugin fully.
        db.update_external_plugins([make_external_plugin("e1"), make_external_plugin("e2")], _type="external")
        assert db.set_plugin_enabled("e2", False) == ""
        db.update_external_plugins([make_external_plugin("e1")], _type="external", delete_missing=True)
        ext = {p["id"]: p for p in db.get_plugins(_type="external")}
        assert "e2" in ext  # retained despite being absent from the list
        assert "E2_GLOBAL" in ext["e2"]["settings"]  # its settings survived too
        assert ext["e2"]["enabled"] is False

    def test_enabled_plugin_absent_from_list_still_deleted(self, db):
        # Control for the disabled-retention guard: an ENABLED plugin missing from the list is
        # still pruned (the guard only spares disabled ids).
        db.update_external_plugins([make_external_plugin("e1"), make_external_plugin("e2")], _type="external")
        db.update_external_plugins([make_external_plugin("e1")], _type="external", delete_missing=True)
        assert "e2" not in {p["id"] for p in db.get_plugins(_type="external")}


class TestPluginIcon:
    """The Plugins.icon column round-trips through update_external_plugins: a shipped
    allowlisted archive icon becomes an ``@file/<name>`` marker (winning over the plugin.json
    ``icon`` string), and a changed icon propagates on update. get_plugin_icon serves it."""

    def _icon(self, db, pid):
        return next(p for p in db.get_plugins(_type="external") if p["id"] == pid)["icon"]

    def test_shipped_icon_file_recorded_as_marker(self, db):
        p = _ext_plugin_with_archive("shipplug", files={"icon.svg": b"<svg/>"}, icon="bx-shield")
        assert db.update_external_plugins([p], _type="external") == ""
        # shipped file wins over the plugin.json "icon" string
        assert self._icon(db, "shipplug") == "@file/icon.svg"

    def test_json_icon_string_when_no_file(self, db):
        p = _ext_plugin_with_archive("boxplug", files={"readme.md": b"x"}, icon="bx-shield")
        assert db.update_external_plugins([p], _type="external") == ""
        assert self._icon(db, "boxplug") == "bx-shield"

    def test_no_icon_at_all_is_none(self, db):
        p = _ext_plugin_with_archive("plainplug", files={"readme.md": b"x"})
        assert db.update_external_plugins([p], _type="external") == ""
        assert self._icon(db, "plainplug") is None

    def test_undelivered_allowlisted_name_not_promoted_to_marker(self, db):
        # plugin.json declares icon="icon.svg" but the archive doesn't actually ship it: must
        # NOT become an "@file/icon.svg" marker (that would point the UI at a 404) - the string
        # is stored verbatim instead.
        p = _ext_plugin_with_archive("ghostplug", files={"readme.md": b"x"}, icon="icon.svg")
        assert db.update_external_plugins([p], _type="external") == ""
        assert self._icon(db, "ghostplug") == "icon.svg"

    def test_icon_change_propagates_on_update(self, db):
        # v1 ships icon.svg -> @file marker; v2 drops the file and declares a boxicon -> the
        # sync update-diff must overwrite the stored icon (a reboot/re-ingest can't be stale).
        v1 = _ext_plugin_with_archive("evolveicon", files={"icon.svg": b"<svg/>"}, version="1.0")
        assert db.update_external_plugins([v1], _type="external") == ""
        assert self._icon(db, "evolveicon") == "@file/icon.svg"

        v2 = _ext_plugin_with_archive("evolveicon", files={"readme.md": b"x"}, icon="bx-cog", version="2.0")
        assert db.update_external_plugins([v2], _type="external") == ""
        assert self._icon(db, "evolveicon") == "bx-cog"

    def test_get_plugin_icon_returns_type_marker_and_blob(self, db):
        p = _ext_plugin_with_archive("blobplug", files={"logo.png": b"\x89PNG-bytes"})
        assert db.update_external_plugins([p], _type="external") == ""
        plugin_type, icon, data = db.get_plugin_icon("blobplug")
        assert plugin_type == "external"
        assert icon == "@file/logo.png"
        assert isinstance(data, (bytes, bytearray)) and len(data) > 0

    def test_get_plugin_icon_missing_plugin_is_none(self, db):
        assert db.get_plugin_icon("nope") is None


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
