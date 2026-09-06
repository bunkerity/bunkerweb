"""DatabaseMetadataMixin.cleanup_template_polluted_global_values — the boot-time one-shot that
removes ``bw_global_values`` rows a pre-fix (< c965d81ec) multi-layer ``USE_TEMPLATE`` save wrote
as ``method="scheduler"`` carrying the TEMPLATE's own resolved value, instead of leaving the
setting unset. See ``.cache/briefs-2026-09-02-wave12/LF-residual-bugfixes.md`` Item 1 and
``.cache/results-2026-09-01-wave11/report-L-B.md`` "Open questions" Q1.

Every fixture row sits behind its own never-declared-elsewhere setting, so the selection rule
(method == "scheduler" AND setting declared by an active USE_TEMPLATE layer AND value == that
layer's *resolved* last-wins default) is pinned in both directions, including the fold-vs-naive
distinction: a row matching a SHADOWED layer's default (not the merged one) must survive, and a
row matching the merged default via the LAST layer must not.
"""

import pytest
from unittest.mock import patch

from fixtures.seed import make_core_plugin, make_general_settings, session
from model import Global_values, Metadata


def _text(setting_id, ctx, *, default=""):
    return {"id": setting_id, "context": ctx, "default": default, "help": "h", "label": "L", "regex": "^.*$", "type": "text"}


def _settings():
    return {
        # declared by "low" only -- a plain single-layer pollution case.
        "ALPHA_FLAG": _text("alpha-flag", "global", default="yes"),
        # declared by BOTH layers, disagreeing -- the fold direction that must SURVIVE: a row
        # matching the SHADOWED ("low") layer's value is a real override of the effective ("high")
        # default, not pollution.
        "ALPHA_MODE": _text("alpha-mode", "global", default="off"),
        # same two layers, same disagreement -- the fold direction that must be DELETED: a row
        # matching the EFFECTIVE ("high") layer's value. Pairing it with ALPHA_MODE means a
        # first-wins bug (using "low"'s default instead of the merged one) mis-scores both.
        "EPSILON_MODE": _text("epsilon-mode", "global", default="off"),
        # declared by "low" only -- the method-filter case: an operator/UI row equal to the
        # template default must survive because it was never written as "scheduler".
        "GAMMA_FLAG": _text("gamma-flag", "global", default="no"),
        # never declared by any template layer -- must never be touched regardless of value/method.
        "DELTA_FLAG": _text("delta-flag", "global", default="no"),
    }


def _general():
    return make_general_settings() | {
        "USE_TEMPLATE": {
            "id": "use-template",
            "context": "multisite",
            "default": "",
            "help": "h",
            "label": "T",
            "regex": "^.*$",
            "type": "multivalue",
            "separator": " ",
        }
    }


@pytest.fixture
def layered(db):
    db.init_tables([_general(), make_core_plugin("alpha", settings=_settings())])
    db.initialize_db("1.7.0", "Docker")
    assert (
        db.create_template(
            "low",
            name="Low",
            settings={"ALPHA_FLAG": "yes", "ALPHA_MODE": "detect", "EPSILON_MODE": "detect", "GAMMA_FLAG": "no"},
            steps=[{"title": "S", "settings": ["ALPHA_FLAG", "ALPHA_MODE", "EPSILON_MODE", "GAMMA_FLAG"]}],
        )
        == ""
    )
    assert (
        db.create_template(
            "high",
            name="High",
            settings={"ALPHA_MODE": "block", "EPSILON_MODE": "block"},
            steps=[{"title": "S", "settings": ["ALPHA_MODE", "EPSILON_MODE"]}],
        )
        == ""
    )
    return db


def _seed_row(db, setting_id, value, method, suffix=0):
    with session(db) as s:
        s.add(Global_values(setting_id=setting_id, value=value, suffix=suffix, method=method))


def _rows(db):
    with session(db) as s:
        return {(r.setting_id, r.suffix or 0): (r.value, r.method) for r in s.query(Global_values).all()}


def _marker(db):
    """``bw_metadata.template_values_cleaned_at`` -- NULL until a pass has completed."""
    with session(db) as s:
        return s.get(Metadata, 1).template_values_cleaned_at


def _seed_polluted_db(db):
    """The shape a pre-fix multi-layer save on ``USE_TEMPLATE=low high`` actually left behind."""
    _seed_row(db, "USE_TEMPLATE", "low high", "scheduler")
    _seed_row(db, "ALPHA_FLAG", "yes", "scheduler")  # (a) single-layer pollution -- DELETE
    _seed_row(db, "ALPHA_MODE", "detect", "scheduler")  # (b) shadowed-layer override -- SURVIVE
    _seed_row(db, "EPSILON_MODE", "block", "scheduler")  # (a) fold-correct pollution -- DELETE
    _seed_row(db, "GAMMA_FLAG", "no", "manual")  # (c) operator row at the default -- SURVIVE
    _seed_row(db, "DELTA_FLAG", "no", "scheduler")  # not template-declared at all -- SURVIVE
    return db


class TestCleanupTemplatePollutedGlobalValues:
    def test_deletes_only_the_polluted_rows(self, layered):
        _seed_polluted_db(layered)

        deleted = layered.cleanup_template_polluted_global_values()

        assert {(setting_id, value) for setting_id, value, _ in deleted} == {("ALPHA_FLAG", "yes"), ("EPSILON_MODE", "block")}
        remaining = _rows(layered)
        assert ("ALPHA_FLAG", 0) not in remaining
        assert ("EPSILON_MODE", 0) not in remaining
        assert remaining[("ALPHA_MODE", 0)] == ("detect", "scheduler")
        assert remaining[("GAMMA_FLAG", 0)] == ("no", "manual")
        assert remaining[("DELTA_FLAG", 0)] == ("no", "scheduler")
        assert remaining[("USE_TEMPLATE", 0)] == ("low high", "scheduler")

    def test_records_the_owning_layer(self, layered):
        _seed_polluted_db(layered)

        deleted = layered.cleanup_template_polluted_global_values()

        by_setting = {setting_id: template_id for setting_id, _, template_id in deleted}
        assert by_setting["ALPHA_FLAG"] == "low"
        assert by_setting["EPSILON_MODE"] == "high"

    def test_idempotent_second_run_deletes_nothing(self, layered):
        _seed_polluted_db(layered)
        layered.cleanup_template_polluted_global_values()

        assert layered.cleanup_template_polluted_global_values() == []
        remaining = _rows(layered)
        assert remaining[("ALPHA_MODE", 0)] == ("detect", "scheduler")
        assert remaining[("GAMMA_FLAG", 0)] == ("no", "manual")


class TestThePersistedMarker:
    """``bw_metadata.template_values_cleaned_at`` is what makes this a real one-shot.

    The in-process flag it sits behind only means "once per ``Database`` instance", and a fresh
    ``Database`` is built per job execution, per ``gen/save_config.py`` subprocess and per
    ``bwcli`` invocation -- so the sweep re-ran on essentially every one of them. These calls go
    straight to the method, which never touches the in-process flag, so the marker is the only
    thing under test here.
    """

    def test_a_completed_pass_stamps_the_marker(self, layered):
        _seed_polluted_db(layered)
        assert _marker(layered) is None

        assert layered.cleanup_template_polluted_global_values()

        assert _marker(layered) is not None

    def test_a_stamped_marker_skips_the_sweep_entirely(self, layered):
        _seed_polluted_db(layered)
        layered.cleanup_template_polluted_global_values()
        # Fresh pollution, of exactly the shape the first pass deleted. It must survive: only the
        # marker can be stopping the scan, since this call carries no in-process state.
        _seed_row(layered, "ALPHA_FLAG", "yes", "scheduler")

        assert layered.cleanup_template_polluted_global_values() == []
        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler")

    def test_a_readonly_database_neither_sweeps_nor_stamps(self, layered):
        _seed_polluted_db(layered)
        layered.readonly = True

        assert layered.cleanup_template_polluted_global_values() == []

        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler")
        assert _marker(layered) is None, "a read-only database must not write the marker either"

    def test_no_active_template_layer_leaves_the_marker_unset(self, layered):
        """Deliberate: stamping here would disable the sweep on a stack that adopts templates
        later, before it could ever have matched a row."""
        _seed_row(layered, "ALPHA_FLAG", "yes", "scheduler")  # no USE_TEMPLATE row seeded

        assert layered.cleanup_template_polluted_global_values() == []

        assert _marker(layered) is None
        # ... and the sweep still fires once templates are actually in use.
        _seed_row(layered, "USE_TEMPLATE", "low high", "scheduler")
        assert {setting_id for setting_id, _, _ in layered.cleanup_template_polluted_global_values()} == {"ALPHA_FLAG"}
        assert _marker(layered) is not None

    def test_a_failed_stamp_rolls_the_deletes_back_with_it(self, layered):
        """The marker is stamped in the SAME transaction as the deletes, so a half-finished pass
        leaves nothing behind and the next process retries the whole thing. Without that, a crash
        between the deletes and the stamp would either lose the deletes or -- worse -- keep them
        and lose the stamp, re-running the scan forever."""
        _seed_polluted_db(layered)

        # `update()` is reached only by the stamp in this call path -- the deletes use `delete()`
        # and have already run when it raises.
        with patch("db_methods.metadata.update", side_effect=RuntimeError("stamp failed")):
            assert layered.cleanup_template_polluted_global_values() == []

        assert _marker(layered) is None, "a failed stamp must not leave the marker set"
        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler"), "the deletes must roll back with it"

    def test_no_active_template_is_a_cheap_no_op(self, layered):
        _seed_row(layered, "ALPHA_FLAG", "yes", "scheduler")  # would match if USE_TEMPLATE were set
        assert layered.cleanup_template_polluted_global_values() == []
        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler")

    def test_readonly_database_is_untouched(self, layered):
        _seed_polluted_db(layered)
        layered.readonly = True

        assert layered.cleanup_template_polluted_global_values() == []
        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler")


class TestGetMetadataRunsCleanupOnceInProcess:
    def test_first_call_cleans_up_and_marks_the_process_flag(self, layered):
        _seed_polluted_db(layered)
        assert not getattr(layered, "_template_defaults_cleanup_attempted", False)

        layered.get_metadata()

        assert layered._template_defaults_cleanup_attempted is True
        assert ("ALPHA_FLAG", 0) not in _rows(layered)

    def test_second_call_does_not_rescan(self, layered):
        _seed_polluted_db(layered)
        layered.get_metadata()

        # Reintroduce a row that WOULD be pollution if the scan ran again -- it must survive,
        # proving the in-process guard actually short-circuits the second call.
        _seed_row(layered, "ALPHA_FLAG", "yes", "scheduler")
        layered.get_metadata()

        assert _rows(layered)[("ALPHA_FLAG", 0)] == ("yes", "scheduler")


class TestGetMetadataOnAnUninitializedDatabase:
    """B2 (Criticos round 1): ``gen/save_config.py``'s own wait loop calls ``get_metadata()``
    BEFORE ``init_tables``/``initialize_db`` ever run -- on a truly fresh install, ``bw_global_values``
    does not exist yet. The cleanup must never be attempted there: it previously logged an
    ERROR-level "no such table" on every such call, landing verbatim in the scheduler's log
    stream and tripping ``tests/core/db.yml``'s ``not_log: "❌"`` on every database arm.

    Uses a bare ``Database`` against a brand-new SQLite file with NO schema created (unlike the
    ``db`` fixture, which resets the schema for every test) -- the actual pre-``initialize_db``
    shape this regression bites in.
    """

    def test_the_cleanup_is_never_attempted_before_the_database_is_initialized(self, quiet_logger, tmp_path, monkeypatch):
        from Database import Database  # noqa: E402 -- resolved via conftest sys.path injection

        uri = f"sqlite:///{tmp_path / 'fresh.db'}"
        fresh_db = Database(quiet_logger, sqlalchemy_string=uri, log=False)
        try:
            calls = []
            monkeypatch.setattr(fresh_db, "cleanup_template_polluted_global_values", lambda: calls.append(1))

            md = fresh_db.get_metadata()

            assert md["is_initialized"] is False
            assert calls == [], "the cleanup must not even be attempted before the schema exists"
            assert not getattr(fresh_db, "_template_defaults_cleanup_attempted", False)
        finally:
            fresh_db.close()
