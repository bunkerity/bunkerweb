"""Integration tier — DatabaseInitTablesMixin.init_tables (plugin/settings schema sync).

High-risk method previously guarded only by misc/refactor/snapshot.sh. Here it's exercised
end-to-end on every engine: create -> idempotent re-run -> update -> prune. Marked `slow`
(deselect with `-m 'not slow'`).
"""

import pytest

from fixtures.seed import make_core_plugin

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

    def test_jobs_created(self, db):
        db.init_tables([make_core_plugin("alpha", jobs=[{"name": "alphajob", "file": "alphajob.py", "every": "hour", "reload": False}])])
        assert "alphajob" in db.get_jobs()
