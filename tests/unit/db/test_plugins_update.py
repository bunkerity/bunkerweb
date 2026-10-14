"""Integration tier — DatabasePluginsUpdateMixin.update_external_plugins (plugin tarball sync).

Syncs external/pro plugin payloads (row + settings + jobs) into the DB. Exercised end-to-end
on every engine: create -> idempotent -> version update -> delete-missing prune. Page sync is
skipped (page=False) so no real tar extraction is needed. Marked `slow`.
"""

import tempfile
from datetime import datetime
from json import dumps
from pathlib import Path

import pytest

from common_utils import create_plugin_tar_gz  # type: ignore
from fixtures.seed import make_external_plugin, session
from model import ResourceGroups, Templates  # type: ignore

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

    def test_job_schedule_update_uses_current_jobs_schema(self, db):
        first = make_external_plugin("jobplug", version="1.0", checksum="sum-1")
        first["jobs"] = [{"name": "jobplug-sync", "file": "sync.py", "every": "hour", "reload": False}]
        assert db.update_external_plugins([first], _type="external") == ""

        updated = make_external_plugin("jobplug", version="2.0", checksum="sum-2")
        updated["jobs"] = [{"name": "jobplug-sync", "file": "sync.py", "every": "day", "reload": False}]
        assert db.update_external_plugins([updated], _type="external") == ""
        assert db.get_jobs()["jobplug-sync"]["every"] == "day"

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

    def test_disk_template_defaults_are_canonicalized(self, db, monkeypatch, tmp_path):
        plugin = make_external_plugin("extplug")
        plugin["settings"] = {
            "EXTPLUG_FLAG": {
                "id": "extplug-flag",
                "context": "multisite",
                "default": "no",
                "help": "h",
                "label": "L",
                "regex": "^(yes|no)$",
                "type": "check",
            }
        }
        monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path)
        assert db.update_external_plugins([plugin], _type="external") == ""
        templates = tmp_path / "templates"
        templates.mkdir()
        (templates / "flag.json").write_text(
            dumps(
                {
                    "name": "Flag",
                    "settings": {"EXTPLUG_FLAG": "on"},
                    "steps": [{"title": "S", "subtitle": "", "settings": ["EXTPLUG_FLAG"]}],
                }
            )
        )

        assert db.update_external_plugins([plugin], _type="external") == ""
        assert db.get_template_settings("flag") == {"EXTPLUG_FLAG": "yes"}

    @staticmethod
    def _flag_setting(pid_up, context="multisite"):
        return {
            f"{pid_up}_FLAG": {
                "id": f"{pid_up.lower()}-flag",
                "context": context,
                "default": "no",
                "help": "h",
                "label": "L",
                "regex": "^(yes|no)$",
                "type": "check",
            }
        }

    @staticmethod
    def _write_template(tmp_path, settings):
        templates = tmp_path / "templates"
        templates.mkdir(exist_ok=True)
        (templates / "flag.json").write_text(
            dumps({"name": "Flag", "settings": settings, "steps": [{"title": "S", "subtitle": "", "settings": list(settings)}]})
        )

    @pytest.mark.parametrize("per_plugin_commit", [True, False])
    def test_template_settings_kept_on_first_sync(self, db, monkeypatch, tmp_path, per_plugin_commit):
        # The plugin's own settings are only staged when its templates are checked: they must
        # count as existing, or a brand-new plugin's template lands with no settings at all.
        plugin = make_external_plugin("extplug")
        plugin["settings"] = self._flag_setting("EXTPLUG") | self._flag_setting("EXTPLUG_G", context="global")
        monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path)
        self._write_template(tmp_path, {"EXTPLUG_FLAG": "on", "EXTPLUG_G_FLAG": "yes"})

        assert db.update_external_plugins([plugin], _type="external", per_plugin_commit=per_plugin_commit) == ""
        # The global setting is still refused: only the multisite one belongs in a template.
        assert db.get_template_settings("flag") == {"EXTPLUG_FLAG": "yes"}

    @pytest.mark.parametrize("per_plugin_commit", [True, False])
    def test_template_settings_kept_when_setting_added_in_same_sync(self, db, monkeypatch, tmp_path, per_plugin_commit):
        # Same ordering on the update path: a new version adds a setting and a template that uses it.
        plugin = make_external_plugin("extplug", version="1.0", checksum="sum-1")
        monkeypatch.setattr(db, "_uep_resolve_plugin_dir", lambda *_: tmp_path)
        assert db.update_external_plugins([plugin], _type="external", per_plugin_commit=per_plugin_commit) == ""

        updated = make_external_plugin("extplug", version="2.0", checksum="sum-2")
        updated["settings"] |= self._flag_setting("EXTPLUG")
        self._write_template(tmp_path, {"EXTPLUG_FLAG": "on"})

        assert db.update_external_plugins([updated], _type="external", per_plugin_commit=per_plugin_commit) == ""
        assert db.get_template_settings("flag") == {"EXTPLUG_FLAG": "yes"}


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


def _ids(db):
    return sorted(plugin["id"] for plugin in db.get_plugins(_type="external"))


def _methods(db):
    return {plugin["id"]: plugin["method"] for plugin in db.get_plugins(_type="external")}


class TestPreserveIds:
    """``delete_missing`` deletes every row of the type that is absent from the incoming list. The
    scheduler's scan only lists what changed on disk, so it names what it did not list in
    ``preserve_ids`` (dev #3303)."""

    @staticmethod
    def _seed(db):
        rows = [
            make_external_plugin("changed", method="manual"),
            make_external_plugin("quiet", method="manual"),
            make_external_plugin("url", method="scheduler"),
        ]
        assert db.update_external_plugins(rows, _type="external", delete_missing=False) == ""
        assert _ids(db) == ["changed", "quiet", "url"]

    def test_without_it_a_partial_list_deletes_the_rest(self, db):
        """T0 at the database layer: the hazard the argument exists for."""
        self._seed(db)
        assert db.update_external_plugins([make_external_plugin("changed", version="2.0", checksum="new")], _type="external", delete_missing=True) == ""
        assert _ids(db) == ["changed"]

    def test_the_named_ids_survive_with_their_settings(self, db):
        self._seed(db)
        incoming = [make_external_plugin("changed", version="2.0", checksum="new")]
        assert db.update_external_plugins(incoming, _type="external", delete_missing=True, preserve_ids={"quiet", "url"}) == ""
        assert _ids(db) == ["changed", "quiet", "url"]
        assert "QUIET_GLOBAL" in next(p for p in db.get_plugins(_type="external") if p["id"] == "quiet")["settings"]

    def test_an_id_that_is_neither_listed_nor_preserved_is_still_deleted(self, db):
        self._seed(db)
        incoming = [make_external_plugin("changed", version="2.0", checksum="new")]
        assert db.update_external_plugins(incoming, _type="external", delete_missing=True, preserve_ids={"url"}) == ""
        assert _ids(db) == ["changed", "url"]

    def test_preserved_ids_do_not_weaken_the_empty_list_guard(self, db):
        self._seed(db)
        assert db.update_external_plugins([], _type="external", delete_missing=True, preserve_ids={"url"}) == ""
        assert _ids(db) == ["changed", "quiet", "url"]

    def test_an_unknown_preserved_id_is_harmless(self, db):
        self._seed(db)
        assert (
            db.update_external_plugins([make_external_plugin("changed")], _type="external", delete_missing=True, preserve_ids={"quiet", "url", "ghost"}) == ""
        )
        assert _ids(db) == ["changed", "quiet", "url"]


class TestSchedulerToDownloadTransition:
    """The download job relabels a plugin it just installed from ``scheduler`` to ``download`` -- and
    nothing else may change a plugin's method through this path (T7)."""

    @staticmethod
    def _seed(db, method):
        assert db.update_external_plugins([make_external_plugin("urlplug", method=method)], _type="external", delete_missing=False) == ""
        assert _methods(db) == {"urlplug": method}

    def _sync(self, db, method, **kwargs):
        plugin = make_external_plugin("urlplug", method=method, **kwargs)
        assert db.update_external_plugins([plugin], _type="external", delete_missing=False) == ""

    def test_scheduler_to_download_is_accepted(self, db):
        self._seed(db, "scheduler")
        self._sync(db, "download")
        assert _methods(db) == {"urlplug": "download"}

    @pytest.mark.parametrize("current", ["manual", "ui", "wizard", "api", "autoconf"])
    def test_any_other_method_cannot_be_taken_over(self, db, current):
        self._seed(db, current)
        self._sync(db, "download")
        assert _methods(db) == {"urlplug": current}

    def test_download_back_to_scheduler_is_refused(self, db):
        self._seed(db, "download")
        self._sync(db, "scheduler")
        assert _methods(db) == {"urlplug": "download"}

    def test_a_download_row_keeps_updating_through_its_own_method(self, db):
        self._seed(db, "download")
        self._sync(db, "download", version="2.0", checksum="new")
        assert next(p for p in db.get_plugins(_type="external") if p["id"] == "urlplug")["version"] == "2.0"

    def test_the_plugins_templates_and_resource_groups_follow(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr(type(db), "_uep_resolve_plugin_dir", lambda self, plugin_id, _type: tmp_path)
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "flag.json").write_text(dumps({"name": "Flag", "settings": {}, "steps": []}))
        self._seed(db, "scheduler")
        now = datetime.now().astimezone()
        with session(db) as s:
            s.add(ResourceGroups(id="urlgroup", name="urlgroup", method="scheduler", plugin_id="urlplug", creation_date=now, last_update=now))
            s.add(ResourceGroups(id="hand", name="hand", method="ui", plugin_id="urlplug", creation_date=now, last_update=now))
        with session(db) as s:
            assert s.get(Templates, "flag").method == "scheduler"

        self._sync(db, "download")

        with session(db) as s:
            assert s.get(Templates, "flag").method == "download"
            assert s.get(ResourceGroups, "urlgroup").method == "download"
            assert s.get(ResourceGroups, "hand").method == "ui"  # the operator's own group is not the plugin's

    def test_a_refused_transition_leaves_the_children_alone(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr(type(db), "_uep_resolve_plugin_dir", lambda self, plugin_id, _type: tmp_path)
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "flag.json").write_text(dumps({"name": "Flag", "settings": {}, "steps": []}))
        self._seed(db, "manual")
        self._sync(db, "download")
        with session(db) as s:
            assert s.get(Templates, "flag").method == "manual"
