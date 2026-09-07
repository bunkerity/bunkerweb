"""``clear_deferred_job_runs`` — a "Deferred" pill only clears once the push it waits on landed.

The debt a deferred job leaves behind is fleet-global (one broker key); the marker the UI renders
the pill from is per-job, on the run row. So the run that carries an earlier job's push settles the
debt for the whole fleet and leaves that job reading "reload deferred" forever, because an
``every: once`` job (``crowdsec-conf``, ``certbot-new``) never runs again to overwrite its own row.

What is asserted here is mostly what the method must NOT clear: a reason the push did not answer, a
row that ended after the tar was built, and a failure. Clearing one of those turns the pill into a
lie in the one direction that matters -- "delivered" about material still sitting on the worker.
"""

from datetime import datetime, timedelta, timezone

import pytest

from fixtures.seed import seed_minimal

CUTOFF = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

# The two reasons a successful push answers on the deferring job's behalf. Mirrors
# src/worker/tasks.py:RELOAD_DEFERRAL_PREFIXES.
NO_INSTANCE = "deferred: no reachable instance yet -- reload deferred"
UNRESOLVABLE = "deferred: could not resolve any reachable instance -- reload deferred"
PREFIXES = ("deferred: no reachable instance yet", "deferred: could not resolve any reachable instance")

# A job that deferred on its own precondition as well. The push carried its files, but "every
# instance down" is a statement about its own work, so its pill stands.
OWN_PRECONDITION = "deferred: every instance down; no reachable instance yet -- reload deferred"


@pytest.fixture
def jdb(db):
    seed_minimal(db)
    return db


def _errors(jdb):
    return [run["error"] for run in jdb.get_jobs()["testjob"]["history"]]


def _run(jdb, error, *, minutes, success=True):
    end = CUTOFF + timedelta(minutes=minutes)
    assert jdb.add_job_run("testjob", success, end, end, error=error) == ""


class TestClearDeferredJobRuns:
    def test_it_clears_what_the_push_answered_and_nothing_else(self, jdb):
        _run(jdb, NO_INSTANCE, minutes=-10)
        _run(jdb, UNRESOLVABLE, minutes=-9)
        _run(jdb, OWN_PRECONDITION, minutes=-8)
        _run(jdb, NO_INSTANCE, minutes=-7, success=False)
        # Recorded while the tar was being built: those files are NOT in the push that just landed.
        _run(jdb, NO_INSTANCE, minutes=5)

        assert jdb.clear_deferred_job_runs(*PREFIXES, before=CUTOFF) == ""

        errors = _errors(jdb)
        assert errors.count(None) == 2, "the two rows this push actually delivered for"
        assert sorted(error for error in errors if error) == sorted((OWN_PRECONDITION, NO_INSTANCE, NO_INSTANCE))

    def test_a_run_that_ended_after_the_cutoff_keeps_its_marker(self, jdb):
        """The same guard the caller's own compare-and-set is: a job that deferred while the tar was
        being built wrote files this push cannot have carried, so its marker is still true."""
        _run(jdb, NO_INSTANCE, minutes=1)

        assert jdb.clear_deferred_job_runs(*PREFIXES, before=CUTOFF) == ""

        assert _errors(jdb) == [NO_INSTANCE]

    def test_a_failed_run_keeps_its_message(self, jdb):
        """`error` is the failure column too. A run that failed says why, and no push makes that
        false -- clearing it would erase the only description of the failure there is."""
        _run(jdb, NO_INSTANCE, minutes=-1, success=False)

        assert jdb.clear_deferred_job_runs(*PREFIXES, before=CUTOFF) == ""

        assert _errors(jdb) == [NO_INSTANCE]

    def test_no_prefixes_clears_nothing(self, jdb):
        """`or_()` over an empty set is not "match nothing" in SQLAlchemy, so the caller passing an
        empty tuple must not fall through to an unfiltered UPDATE over every deferred run."""
        _run(jdb, NO_INSTANCE, minutes=-1)

        assert jdb.clear_deferred_job_runs(before=CUTOFF) == ""

        assert _errors(jdb) == [NO_INSTANCE]

    def test_a_neighbouring_reason_is_not_matched_through_a_like_wildcard(self, jdb):
        """The reasons are prose and go into a LIKE. Unescaped, a `_` in a prefix matches any
        character, so a future reason could silently clear the pill of a different one."""
        _run(jdb, "deferred: no reachable instance yes -- something else entirely", minutes=-1)

        assert jdb.clear_deferred_job_runs("deferred: no reachable instance ye_", before=CUTOFF) == ""

        assert _errors(jdb) == ["deferred: no reachable instance yes -- something else entirely"]
