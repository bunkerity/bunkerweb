"""`clear_applied_changes` — acknowledging only the changes a run actually applied.

The scheduler used to clear the change flags in the same iteration that DISPATCHED the job that
applies them. Dispatch is fire-and-forget (no Celery result backend), so a push that never
completed left the flags already clear and nothing re-dispatched it: instances kept serving the
previous configuration with only a failed job run as evidence.

Moving the clear to the job that did the work trades that for the opposite hazard — a change that
lands WHILE the job runs must not be acknowledged by it. Hence compare-and-clear against each
flag's `last_*_change` watermark. These tests are mostly about that second hazard, because the
first one is easy and the second is what makes the design correct.

Runs against every selected engine via the ``db`` fixture.
"""

from datetime import datetime, timedelta

import pytest

from fixtures.seed import make_core_plugin, make_general_settings, seed_minimal


def _snapshot(db):
    """What a job takes before reading the data it is about to apply."""
    return db.get_metadata()


def _require_subsecond_watermarks(db):
    if db.sql_engine.dialect.name in ("mysql", "mariadb"):
        pytest.skip("MariaDB needs a DATETIME(6) migration before two writes in one second can be distinguished")


class TestAcknowledgingWhatWasApplied:
    def test_a_flag_untouched_since_the_snapshot_is_cleared(self, db):
        seed_minimal(db)
        db.checked_changes(["custom_configs"], value=True)
        snapshot = _snapshot(db)
        assert snapshot["custom_configs_changed"] is True

        assert db.clear_applied_changes(snapshot) == ""

        assert db.get_metadata()["custom_configs_changed"] is False

    def test_every_flag_the_snapshot_carried_is_cleared(self, db):
        seed_minimal(db)
        db.checked_changes(["custom_configs", "external_plugins", "pro_plugins", "instances"], value=True)
        snapshot = _snapshot(db)

        db.clear_applied_changes(snapshot)

        metadata = db.get_metadata()
        for key in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "instances_changed"):
            assert metadata[key] is False, key

    def test_only_the_named_keys_are_cleared_when_keys_are_given(self, db):
        """deploy-certificates acknowledges `certificates` alone; it must not speak for the
        custom-configs or plugin changes that push-configs owns."""
        seed_minimal(db)
        db.checked_changes(["custom_configs", "certificates"], value=True)
        snapshot = _snapshot(db)

        db.clear_applied_changes(snapshot, ("certificates",))

        metadata = db.get_metadata()
        assert metadata["certificates_changed"] is False
        assert metadata["custom_configs_changed"] is True

    def test_a_flag_that_was_already_clear_is_left_alone(self, db):
        seed_minimal(db)
        snapshot = _snapshot(db)
        assert snapshot["custom_configs_changed"] is False

        assert db.clear_applied_changes(snapshot) == ""
        assert db.get_metadata()["custom_configs_changed"] is False


class TestChangeArrivingMidRun:
    """The whole point of the compare: a change the run never saw must survive it."""

    def test_a_flag_re_raised_after_the_snapshot_is_not_cleared(self, db):
        _require_subsecond_watermarks(db)
        seed_minimal(db)
        db.checked_changes(["custom_configs"], value=True)
        snapshot = _snapshot(db)

        # ... the job is working. Someone edits a custom config, which re-raises the flag and
        # moves its watermark.
        db.checked_changes(["custom_configs"], value=True)
        assert db.get_metadata()["last_custom_configs_change"] != snapshot["last_custom_configs_change"]

        db.clear_applied_changes(snapshot)

        assert db.get_metadata()["custom_configs_changed"] is True, "a change that landed mid-run was acknowledged by a run that never saw it"

    def test_the_untouched_flags_still_clear_when_a_sibling_moved(self, db):
        """Per-flag comparison, not all-or-nothing: one moving change must not strand the rest."""
        _require_subsecond_watermarks(db)
        seed_minimal(db)
        db.checked_changes(["custom_configs", "instances"], value=True)
        snapshot = _snapshot(db)

        db.checked_changes(["instances"], value=True)
        db.clear_applied_changes(snapshot)

        metadata = db.get_metadata()
        assert metadata["custom_configs_changed"] is False
        assert metadata["instances_changed"] is True

    def test_the_watermark_itself_is_never_written(self, db):
        """The clear must not move the token it compares against — doing so would destroy the
        value the NEXT comparison depends on, and silently break the whole mechanism."""
        seed_minimal(db)
        db.checked_changes(["custom_configs"], value=True)
        snapshot = _snapshot(db)

        db.clear_applied_changes(snapshot)

        assert db.get_metadata()["last_custom_configs_change"] == snapshot["last_custom_configs_change"]


class TestPerPluginConfig:
    """`plugins_config_changed` arrives as {plugin_id: last_config_change} — one token each."""

    def _plugin_ids(self, db):
        return sorted(db.get_metadata()["plugins_config_changed"])

    def test_plugins_in_the_snapshot_are_cleared(self, db):
        seed_minimal(db)
        db.checked_changes([], plugins_changes="all", value=True)
        snapshot = _snapshot(db)
        assert snapshot["plugins_config_changed"]

        db.clear_applied_changes(snapshot)

        assert self._plugin_ids(db) == []

    def test_a_plugin_whose_config_changed_again_is_not_cleared(self, db):
        _require_subsecond_watermarks(db)
        seed_minimal(db)
        db.checked_changes([], plugins_changes="all", value=True)
        snapshot = _snapshot(db)
        targeted = sorted(snapshot["plugins_config_changed"])[0]

        # That one plugin is edited again while the job works.
        db.checked_changes([], plugins_changes=[targeted], value=True)
        db.clear_applied_changes(snapshot)

        assert self._plugin_ids(db) == [targeted]

    def test_a_plugin_absent_from_the_snapshot_is_untouched(self, db):
        """A plugin whose config changed for the first time mid-run is not in the snapshot at
        all, so nothing can acknowledge it."""
        seed_minimal(db)
        db.checked_changes([], plugins_changes="all", value=True)
        snapshot = _snapshot(db)
        latecomer = sorted(snapshot["plugins_config_changed"])[0]
        snapshot["plugins_config_changed"].pop(latecomer)

        db.clear_applied_changes(snapshot)

        assert self._plugin_ids(db) == [latecomer]


class TestSettersMoveTheWatermark:
    """The compare is only worth anything if raising a flag also moves its token.

    `save_config` used to set `Plugins.config_changed = True` WITHOUT touching
    `last_config_change`. That is the dominant path — every settings save from the UI and the
    API goes through it — and with a frozen timestamp the compare-and-clear silently degrades
    into "clear unconditionally", which is the exact behaviour this whole change removes.
    """

    def test_a_config_save_moves_the_plugin_watermark(self, db):
        _require_subsecond_watermarks(db)
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")

        db.save_config({"ALPHA_GLOBAL": "first"}, "scheduler", skip_service_management=True)
        first = db.get_metadata()["plugins_config_changed"]
        assert "alpha" in first, "saving a plugin's setting must raise its config_changed flag"

        # A job acknowledges that save, then a second save lands.
        db.clear_applied_changes(db.get_metadata())
        db.save_config({"ALPHA_GLOBAL": "second"}, "scheduler", skip_service_management=True)
        second = db.get_metadata()["plugins_config_changed"]

        assert "alpha" in second
        assert second["alpha"] != first["alpha"], "the watermark did not move, so the two saves are indistinguishable"

    def test_editing_a_template_moves_every_plugin_watermark(self, db):
        """`update_template` and `delete_template` raise `config_changed` on EVERY plugin, since
        a template can touch any of them. Same requirement, separate code path — and a path with
        no test is how the bump went missing on all three sites in the first place."""
        seed_minimal(db)
        assert db.create_template("low", name="Low", settings={"USE_REVERSE_PROXY": "yes"}, steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}]) == ""

        db.clear_applied_changes(db.get_metadata())
        before = db.get_metadata()["plugins_config_changed"]
        assert not before, "the acknowledgement should have cleared the create"

        assert db.update_template("low", name="Low 2", settings={"USE_REVERSE_PROXY": "no"}, steps=[{"title": "S", "settings": ["USE_REVERSE_PROXY"]}]) == ""
        after = db.get_metadata()["plugins_config_changed"]

        assert after, "editing a template must raise the plugin config flags"
        assert all(watermark is not None for watermark in after.values()), "a raised flag with no watermark is invisible to the acknowledgement"


class TestRobustness:
    def test_a_stale_watermark_clears_nothing(self, db):
        """A snapshot from a run so old its watermark no longer matches must be inert rather
        than clearing on a best-effort basis."""
        seed_minimal(db)
        db.checked_changes(["custom_configs"], value=True)
        snapshot = _snapshot(db)
        snapshot["last_custom_configs_change"] = datetime.now().astimezone() - timedelta(days=7)

        db.clear_applied_changes(snapshot)

        assert db.get_metadata()["custom_configs_changed"] is True

    def test_an_unknown_key_is_ignored(self, db):
        seed_minimal(db)
        assert db.clear_applied_changes(_snapshot(db), ("not_a_flag",)) == ""

    def test_config_is_not_clearable(self, db):
        """ "config" latches `first_config_saved` and clears nothing; it must never be treated as
        a clearable flag or the latch would look like a change to acknowledge."""
        from db_methods.metadata import CLEARABLE_CHANGES  # noqa: E402 — sys.path injected by conftest

        assert "config" not in CLEARABLE_CHANGES

    def test_a_readonly_database_reports_and_changes_nothing(self, db):
        seed_minimal(db)
        db.checked_changes(["custom_configs"], value=True)
        snapshot = _snapshot(db)

        db.readonly = True
        try:
            assert db.clear_applied_changes(snapshot) != ""
        finally:
            db.readonly = False

        assert db.get_metadata()["custom_configs_changed"] is True
