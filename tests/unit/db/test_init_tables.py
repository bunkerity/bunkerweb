"""Integration tier — DatabaseInitTablesMixin.init_tables (plugin/settings schema sync).

High-risk method previously guarded only by misc/refactor/snapshot.sh. Here it's exercised
end-to-end on every engine: create -> idempotent re-run -> update -> prune. Marked `slow`
(deselect with `-m 'not slow'`).
"""

import pytest

from fixtures.seed import make_core_plugin, session

pytestmark = pytest.mark.slow


class TestInitTables:
    def test_creates_plugin_and_settings(self, db):
        ok, err = db.init_tables([make_core_plugin("alpha")])
        assert (ok, err) == (True, "")
        alpha = next(p for p in db.get_plugins() if p["id"] == "alpha")
        assert "ALPHA_GLOBAL" in alpha["settings"]
        assert "ALPHA_MS" in alpha["settings"]

    def test_idempotent_rerun_reports_no_changes(self, db):
        # The bool is "changes applied", not "success": first run mutates, re-run is a no-op.
        assert db.init_tables([make_core_plugin("alpha")]) == (True, "")
        assert db.init_tables([make_core_plugin("alpha")]) == (False, "")
        assert len([p for p in db.get_plugins() if p["id"] == "alpha"]) == 1

    def test_version_update(self, db):
        db.init_tables([make_core_plugin("alpha", version="1.0")])
        db.init_tables([make_core_plugin("alpha", version="2.0")])
        assert next(p for p in db.get_plugins() if p["id"] == "alpha")["version"] == "2.0"

    def test_plugin_removal_prunes(self, db):
        db.init_tables([make_core_plugin("alpha"), make_core_plugin("beta")])
        assert {"alpha", "beta"} <= {p["id"] for p in db.get_plugins()}
        db.init_tables([make_core_plugin("alpha")])  # beta dropped from desired
        ids = {p["id"] for p in db.get_plugins()}
        assert "alpha" in ids and "beta" not in ids

    def _external_manual(self, plugin_id):
        # An external, method="manual" plugin: the init-diff delete branch fires for method=="manual"
        # rows, so this is exactly the shape whose FS dir vanishing on disable would trigger deletion.
        p = make_core_plugin(plugin_id)
        p["type"] = "external"
        p["method"] = "manual"
        return p

    def test_disabled_plugin_absent_from_desired_is_retained(self, db):
        # Disabling an external/pro plugin removes its FS dir, so it is absent from the desired
        # (FS-derived) set on the next init_tables. The disabled guard must skip the delete so the
        # row AND its settings survive until re-enable.
        db.init_tables([make_core_plugin("alpha"), self._external_manual("extp")])
        assert db.set_plugin_enabled("extp", False) == ""
        db.init_tables([make_core_plugin("alpha")])  # extp dropped from desired (dir gone)
        plugins = {p["id"]: p for p in db.get_plugins()}
        assert "extp" in plugins  # retained despite absence
        assert "EXTP_GLOBAL" in plugins["extp"]["settings"]  # settings survived
        assert plugins["extp"]["enabled"] is False

    def test_enabled_plugin_absent_from_desired_still_deleted(self, db):
        # Control: an ENABLED external/manual plugin dropped from desired is still pruned.
        db.init_tables([make_core_plugin("alpha"), self._external_manual("extp")])
        db.init_tables([make_core_plugin("alpha")])
        assert "extp" not in {p["id"] for p in db.get_plugins()}

    def test_jobs_created(self, db):
        db.init_tables([make_core_plugin("alpha", jobs=[{"name": "alphajob", "file": "alphajob.py", "every": "hour", "reload": False}])])
        assert "alphajob" in db.get_jobs()

    def test_case_insensitive_fetched_by_init_diff(self, db):
        # A3 regression: the bw_settings diff (_it_fetch_old_data) must fetch
        # Settings.case_insensitive. A missing fetch made the diff read old=None != desired=True
        # for a core select that opts in, emitting a redundant bw_settings UPDATE every scheduler
        # boot. (Pre-fix this assertion raises AttributeError — the column isn't on the row.)
        settings = {
            "CIPLUG_PICK": {
                "id": "ciplug-pick",
                "context": "global",
                "default": "modern",
                "help": "h",
                "label": "L",
                "regex": "^(modern|old)$",
                "type": "select",
                "select": ["modern", "old"],
                "case_insensitive": True,
            }
        }
        assert db.init_tables([make_core_plugin("ciplug", settings=settings)]) == (True, "")
        # the flag round-trips through the serializer...
        sd = next(p for p in db.get_plugins() if p["id"] == "ciplug")["settings"]["CIPLUG_PICK"]
        assert sd["case_insensitive"] is True
        # ...and the init-diff fetch now exposes it, so the row diff compares True == True.
        with session(db) as s:
            old = db._it_fetch_old_data(s)
        row = next(r for r in old["bw_settings"] if r.id == "CIPLUG_PICK")
        assert row.case_insensitive is True
