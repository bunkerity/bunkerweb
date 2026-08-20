"""`cleanup_methods` — behavioural cover for the widening of 33f42592d, at BOTH call sites.

The fix: a save whose method is one of `EDITABLE_METHODS` ("ui", "api", "wizard") cleans up rows
owned by *any* of them, because those methods own one another's rows on the write path. Before it,
a save could WRITE a sibling's row but never CLEAR one -- unchecking a setting on a wizard-created
service reported success and silently kept the old value, and a UI write does not migrate the row's
method, so it never healed on a later edit either.

Written under RULE 14b. `cleanup_methods` is computed twice and consumed at two call sites:

  * `Global_values.method.in_(cleanup_methods)`     (the global settings cleanup)
  * `Services_settings.method.in_(cleanup_methods)` (the per-service settings cleanup)

One test for "the behaviour" would have covered whichever site it happened to reach and left the
other free to regress. `skip_service_management=True` -- which most tests in this tier pass --
short-circuits the service loop to `[]`, so a global-path test proves *nothing* about the service
path by construction. Both are exercised here, and each has its own negative control.

The controls matter as much as the cases: "scheduler" and "autoconf" are deliberately NOT editable
(config-as-code rows stay owned by the method that declared them). A widening that swallowed them
would pass every positive case here while destroying that guarantee.
"""

from pathlib import Path

import pytest

from sqlalchemy import select

from fixtures.seed import add_global_value, add_service, add_service_setting, make_core_plugin, make_general_settings, session
from model import Services_settings

pytestmark = pytest.mark.slow

SERVICE = "app1.example.com"

# The set the fix is about. Kept as a literal rather than imported from the product so that a
# widening of EDITABLE_METHODS itself shows up here as a failing test instead of being adopted
# silently -- adding a method to that frozenset is an authorization change and belongs in review.
EDITABLE = ("ui", "api", "wizard")
NOT_EDITABLE = ("scheduler", "autoconf")


def test_the_method_sets_this_file_pins_are_not_empty():
    """RULE 13: every case below is parametrized off these two tuples.

    Emptying either one deletes its cases from the run, and pytest reports that as success --
    "0 failed" and "nothing ran" are the same output. Floors (`>=`), not exact counts: a lane
    legitimately adding a method to either group should not have to edit this assertion.
    """
    assert len(EDITABLE) >= 3, f"EDITABLE shrank to {len(EDITABLE)} -- cases below stopped running"
    assert len(NOT_EDITABLE) >= 2, f"NOT_EDITABLE shrank to {len(NOT_EDITABLE)} -- controls below stopped running"
    assert not set(EDITABLE) & set(NOT_EDITABLE)


@pytest.fixture
def seeded(db):
    # Two multisite settings on purpose. With one, dropping it is a 100% wipe of the service's rows
    # and the data-loss guard at the bottom of the same function refuses the whole cleanup -- every
    # case below would then pass or fail on the GUARD, never on the cleanup select it is testing.
    # BETA_MS is the survivor that keeps the wipe partial. TestServiceWipeGuard covers the 100% case.
    db.init_tables([make_general_settings(), make_core_plugin("alpha"), make_core_plugin("beta")])
    db.initialize_db("1.7.0", "Docker")
    return db


class TestGlobalCleanupCallSite:
    """`Global_values.method.in_(cleanup_methods)`."""

    @pytest.mark.parametrize("owner", EDITABLE)
    @pytest.mark.parametrize("saver", EDITABLE)
    def test_an_editable_method_clears_a_sibling_editable_row(self, seeded, owner, saver):
        add_global_value(seeded, setting_id="ALPHA_GLOBAL", value="stale", method=owner)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "stale"

        assert isinstance(seeded.save_config({}, saver, skip_service_management=True), set)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "def", f"{saver} could not clear a {owner}-owned global row"

    @pytest.mark.parametrize("owner", NOT_EDITABLE)
    def test_an_editable_method_does_not_touch_a_config_as_code_row(self, seeded, owner):
        add_global_value(seeded, setting_id="ALPHA_GLOBAL", value="declared", method=owner)

        seeded.save_config({}, "ui", skip_service_management=True)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "declared", f"a ui save cleared a {owner}-owned row"

    @pytest.mark.parametrize("saver", NOT_EDITABLE)
    def test_a_non_editable_method_clears_only_its_own_rows(self, seeded, saver):
        add_global_value(seeded, setting_id="ALPHA_GLOBAL", value="from-ui", method="ui")

        seeded.save_config({}, saver, skip_service_management=True)
        assert seeded.get_config()["ALPHA_GLOBAL"] == "from-ui", f"a {saver} save cleared a ui-owned row"


class TestServiceCleanupCallSite:
    """`Services_settings.method.in_(cleanup_methods)` — the site `skip_service_management` hides."""

    @staticmethod
    def _seed(db, owner, *, value="stale", second=True):
        add_service(db, SERVICE, method=owner)
        add_service_setting(db, service_id=SERVICE, setting_id="ALPHA_MS", value=value, method=owner)
        if second:
            add_service_setting(db, service_id=SERVICE, setting_id="BETA_MS", value="kept", method=owner)

    @staticmethod
    def _keep_alive(saver, db):
        """Drop ALPHA_MS, keep the service and BETA_MS -- a partial wipe, so the guard stays out."""
        return db.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE, f"{SERVICE}_BETA_MS": "kept"}, saver)

    @staticmethod
    def _row(db, setting_id="ALPHA_MS"):
        """The stored value, read from the row itself.

        Not `get_config()`: that view only exposes multisite keys once MULTISITE is "yes", so it
        answers "is this service published" as well as "does the row exist" and would report a
        surviving row as absent. The cleanup deletes a ROW -- that is what these assert on.
        """
        with session(db) as s:
            row = s.scalars(select(Services_settings).filter_by(service_id=SERVICE, setting_id=setting_id)).first()
            return None if row is None else row.value

    @pytest.mark.parametrize("owner", EDITABLE)
    @pytest.mark.parametrize("saver", EDITABLE)
    def test_an_editable_method_clears_a_sibling_editable_row(self, seeded, owner, saver):
        self._seed(seeded, owner)
        assert self._row(seeded) == "stale"

        self._keep_alive(saver, seeded)
        assert self._row(seeded) is None, f"{saver} could not clear a {owner}-owned service row"
        assert self._row(seeded, "BETA_MS") == "kept", "the cleanup took a row the config still carried"

    @pytest.mark.parametrize("owner", NOT_EDITABLE)
    def test_an_editable_method_does_not_touch_a_config_as_code_row(self, seeded, owner):
        self._seed(seeded, owner, value="declared")

        self._keep_alive("ui", seeded)
        assert self._row(seeded) == "declared", f"a ui save cleared a {owner}-owned service row"

    @pytest.mark.parametrize("saver", NOT_EDITABLE)
    def test_a_non_editable_method_clears_only_its_own_rows(self, seeded, saver):
        self._seed(seeded, "ui", value="from-ui")

        self._keep_alive(saver, seeded)
        assert self._row(seeded) == "from-ui", f"a {saver} save cleared a ui-owned service row"


class TestServiceWipeGuard:
    """The refusal branch of the same function -- the half real data does not reach on its own.

    The cleanup select decides WHICH rows are cleanable; the guard at the end of
    `_sc_cleanup_service_settings` decides whether to apply the result at all, refusing a save that
    would delete 100% of an existing service's rows while the service is still listed in
    SERVER_NAME (an incomplete Advanced-mode form post, a JS rebuild race, a plugin tab that failed
    to render). Every case in the class above deliberately keeps the wipe partial so the guard stays
    out of the way -- which means the whole class runs without ever entering this branch. A guard
    cannot validate a branch real data never reaches: reaching it takes a synthetic case, and this
    is it.

    It also pins the 12:18 asymmetry that currently lives only in a comment: the guard is keyed on
    `("ui", "api")` while the select above uses the wider EDITABLE_METHODS, so a `wizard` save is
    NOT refused. That is deliberate (the wizard's save is server-built and single), and a later
    "completion" of the asymmetry would change behaviour the comment cannot enforce.
    """

    @staticmethod
    def _wipe_everything(saver, db):
        """One row on the service, dropped, service still in SERVER_NAME -> a 100% wipe."""
        add_service(db, SERVICE, method="ui")
        add_service_setting(db, service_id=SERVICE, setting_id="ALPHA_MS", value="only-row", method="ui")
        db.save_config({"MULTISITE": "yes", "SERVER_NAME": SERVICE}, saver)
        with session(db) as s:
            row = s.scalars(select(Services_settings).filter_by(service_id=SERVICE, setting_id="ALPHA_MS")).first()
            return None if row is None else row.value

    @pytest.mark.parametrize("saver", ["ui", "api"])
    def test_a_total_wipe_from_the_ui_or_api_is_refused(self, seeded, saver):
        assert self._wipe_everything(saver, seeded) == "only-row", f"a {saver} save wiped every row of a live service"

    def test_the_wizard_is_not_covered_by_the_guard(self, seeded):
        """The asymmetry, asserted as behaviour rather than as the text that implements it.

        The guard exists for the incomplete-payload callers: an Advanced-mode form post that lost
        keys, a JS rebuild race, a plugin tab that failed to render. All of those are `ui`/`api`.
        The wizard's save is server-built and submitted once, so an incomplete wizard payload is not
        a thing that happens -- which is why the guard is keyed on `("ui", "api")` while the cleanup
        select above uses the wider EDITABLE_METHODS. That reasoning stands on its own; it does not
        need the current source to be true.

        Written this way on purpose: an earlier version of this test asserted that the literal
        `'if ctx.method in ("ui", "api") and service_method_to_delete'` appears in config_save.py.
        That pins the implementation, so a ruling to widen the tuple would have had to fight the
        test suite to land -- a bug or a deferred decision turned into a requirement. This version
        goes red on the same change, but for the right reason: the wizard's wipe would start being
        refused, and THAT is a behaviour change someone must sign off.
        """
        assert self._wipe_everything("wizard", seeded) is None, (
            "a wizard save is now refused by the data-loss guard; if the guard's method tuple was "
            "widened to EDITABLE_METHODS that is the behaviour change the 12:18 ruling deferred"
        )
