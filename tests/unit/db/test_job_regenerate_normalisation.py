"""Integration tier — a `plugin.json` job carrying ``regenerate`` normalises into ``Jobs``.

``regenerate`` is a manifest-only flag: the Scheduler reads it from ``plugin.json`` to build the
dispatch payload and the Worker acts on it, but nothing persists it — ``bw_jobs`` has no column
for it and (RULES, wave 13) the schema is frozen.

That makes the three job-normalisation blocks a real hazard rather than a formality. Each one
pops ``file`` -> ``file_name`` and ``async`` -> ``run_async`` and then splats the *rest* of the
manifest dict straight into the model (``Jobs(plugin_id=..., **job)``), so a key the model does
not know is not ignored — it raises ``TypeError: 'regenerate' is an invalid keyword argument for
Jobs`` and takes the whole plugin sync down with it. Shipping ``"regenerate": true`` in three core
manifests without popping it produced 41 errors across ``tests/unit/gen`` on the first run.

The three paths, one test each:
  * ``initialization.py::_it_build_desired_plugins``  — ``init_tables`` (core plugins at boot)
  * ``plugins_update.py::_uep_insert_plugin``         — a NEW external/PRO plugin
  * ``plugins_update.py::_uep_sync_jobs``             — a NEW job on an EXISTING plugin

A quieter fourth consequence is covered by the idempotence assertion below: the init diff compares
``any(getattr(old_job, k, None) != new_job.get(k) for k in new_job)``, so an unpopped key would
never match a model attribute and every job would diff as permanently changed, churning UPDATEs on
every boot.
"""

import pytest

from fixtures.seed import make_core_plugin, make_external_plugin

pytestmark = pytest.mark.slow

JOB = {"name": "regen-job", "file": "regen.py", "every": "hour", "reload": True, "async": True, "regenerate": True}


def _job(**over):
    return dict(JOB, **over)


class TestTheFlagIsAcceptedAndNotPersisted:
    def test_init_tables_path(self, db):
        """Core plugins at boot — the path the three shipped manifests take."""
        plugin = make_core_plugin("regenplug", jobs=[_job()])

        ok, err = db.init_tables([plugin])

        assert (ok, err) == (True, "")
        job = db.get_jobs()["regen-job"]
        assert job["every"] == "hour" and job["reload"] is True
        assert "regenerate" not in job, "the manifest-only flag must not be persisted"

    def test_init_tables_is_still_idempotent(self, db):
        """Anti-churn: an unpopped key diffs against no model attribute, so the second run would
        report changes forever."""
        assert db.init_tables([make_core_plugin("regenplug", jobs=[_job()])]) == (True, "")
        assert db.init_tables([make_core_plugin("regenplug", jobs=[_job()])]) == (False, "")

    def test_external_plugin_insert_path(self, db):
        """_uep_insert_plugin — an external/PRO plugin declaring the flag, which is the whole
        point of replacing the Scheduler's hardcoded two-job allowlist."""
        plugin = make_external_plugin("regenext")
        plugin["jobs"] = [_job(name="regenext-job")]

        assert db.update_external_plugins([plugin], _type="external") == ""
        assert db.get_jobs()["regenext-job"]["every"] == "hour"

    def test_new_job_on_an_existing_external_plugin(self, db):
        """_uep_sync_jobs — the branch that runs when a job name is not in the DB yet."""
        first = make_external_plugin("regenext2", version="1.0", checksum="sum-1")
        first["jobs"] = [{"name": "regenext2-a", "file": "a.py", "every": "day", "reload": False}]
        assert db.update_external_plugins([first], _type="external") == ""

        second = make_external_plugin("regenext2", version="2.0", checksum="sum-2")
        second["jobs"] = [
            {"name": "regenext2-a", "file": "a.py", "every": "day", "reload": False},
            _job(name="regenext2-b"),
        ]
        assert db.update_external_plugins([second], _type="external") == ""

        jobs = db.get_jobs()
        assert {"regenext2-a", "regenext2-b"} <= set(jobs)
        assert "regenerate" not in jobs["regenext2-b"]

    def test_a_job_without_the_flag_is_unaffected(self, db):
        """Anti-vacuity: the pop must not be what makes any of the above pass."""
        plugin = make_core_plugin("plainplug", jobs=[{"name": "plain-job", "file": "p.py", "every": "day", "reload": False}])

        assert db.init_tables([plugin]) == (True, "")
        assert db.get_jobs()["plain-job"]["every"] == "day"
