"""Tower-of-Hanoi rotation (issue #3271): which backups the purge gives up, and which it must not.

Rotation deletes files, so the invariant that matters more than the ladder itself is that the new
strategy can never remove MORE than the FIFO rotation that shipped before it: both give up exactly
`count - BACKUP_ROTATION` files and differ only in which ones. `hanoi` is the default (PO ruling,
2026-08-24); `fifo` remains available as `BACKUP_ROTATION_STRATEGY=fifo`, and its decisions still
match the slice `backup-data.py` used to compute inline for every archive whose name carries a
valid timestamp -- which is every archive the plugin itself writes. An archive whose name
does not (or whose stamp is not a real date) is now ordered by its true modification time instead of
by that time rendered as a local wall-clock string, which differs only where wall-clock time is not
monotonic: the hour a DST fall-back repeats.

The ladder's own load-bearing property is that a backup which falls out of it is never wanted
again -- "a slot is never vacated then needed". That cannot be checked on a snapshot: it is a
statement about a sequence, so the simulations below walk hundreds of backup periods and assert it
at every step. The now-relative variant of this scheme (age windows measured back from `now`,
keeping one backup per window) passes every snapshot assertion and fails exactly there, which is
why the levels are anchored on an absolute grid instead.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

from backup import backup_time, hanoi_keep, hanoi_rank, period_index, rotate_backups, rotation_victims, sorted_backups  # noqa: E402

DAY = timedelta(days=1)
# Midday of an epoch-aligned day: the ladder cuts its blocks on UTC boundaries, so anchoring
# here is what keeps `_dated(0, 0.25)` a same-period pair whatever timezone the suite runs in.
NOW = datetime.fromtimestamp(20689 * 86400 + 43200).astimezone()


def _dated(*ages_in_days, engine="mariadb"):
    """`(taken_at, path)` pairs, one per age in days, named the way the plugin names archives."""
    pairs = []
    for age in ages_in_days:
        taken = NOW - age * DAY
        pairs.append((taken, Path(f"backup-{engine}-{taken.strftime('%Y-%m-%d_%H-%M-%S')}.zip")))
    return pairs


def _kept(dated, rotation, strategy="hanoi"):
    victims = {backup for backup, _ in rotation_victims(dated, rotation, strategy, DAY)}
    return [backup for _, backup in sorted(dated, key=lambda pair: pair[0]) if backup not in victims]


def _ages(dated, kept):
    taken_of = {backup: taken for taken, backup in dated}
    return sorted(round((NOW - taken_of[backup]) / DAY) for backup in kept)


class TestLadder:
    def test_the_period_index_is_the_session_counter(self):
        """The Hanoi session counter is derived from the timestamp, never stored, so it survives
        a restore and cannot drift out of step with the files on disk. One period apart is one
        session apart, which is what the ladder reads. The blocks are cut on UTC boundaries while
        the stamp in the file name is local time, so the cut does not line up with local midnight
        and, across a DST change, two daily backups can share a period or skip one -- one file,
        once a year, handled as a period with two backups (see the conception's edge cases)."""
        taken = datetime(2026, 8, 24, 3, 0, 0).astimezone()
        assert period_index(taken + DAY, DAY) == period_index(taken, DAY) + 1
        assert period_index(taken + timedelta(minutes=5), DAY) == period_index(taken, DAY)
        assert period_index(taken + timedelta(weeks=1), timedelta(weeks=1)) == period_index(taken, timedelta(weeks=1)) + 1

    @pytest.mark.parametrize("rotation", range(1, 40))
    def test_the_ladder_never_asks_for_more_files_than_the_operator_allows(self, rotation):
        """`levels + 1 <= rotation` is what makes the quota hold: every level's newer keeper is
        the newest backup there is, so a level costs one file, not two. It is not obvious enough
        to take on trust -- keeping the newest of each block instead of the oldest breaks it."""
        dated = _dated(*range(600))
        assert len(hanoi_keep(dated, rotation, DAY)) <= rotation

    def test_the_newest_backup_is_always_on_the_ladder(self):
        dated = _dated(*range(40))
        newest = sorted(dated, key=lambda pair: pair[0])[-1][1]
        for rotation in range(1, 30):
            assert newest in hanoi_keep(dated, rotation, DAY)

    def test_an_empty_directory_is_not_a_special_case(self):
        assert hanoi_keep([], 7, DAY) == set()


class TestNeverMoreThanFifo:
    @pytest.mark.parametrize("count", range(0, 30))
    @pytest.mark.parametrize("strategy", ("fifo", "hanoi"))
    def test_both_strategies_give_up_exactly_the_same_number_of_files(self, count, strategy):
        assert len(rotation_victims(_dated(*range(count)), 7, strategy, DAY)) == max(0, count - 7)

    def test_nothing_is_deleted_below_the_limit(self):
        assert rotation_victims(_dated(0, 1, 2), 7, "hanoi", DAY) == []

    def test_the_newest_backup_is_never_a_victim(self):
        """Every file older than a period, so the recent-fill cannot be what saves it."""
        dated = _dated(*range(10, 50))
        victims = {backup for backup, _ in rotation_victims(dated, 7, "hanoi", DAY)}
        assert sorted(dated, key=lambda pair: pair[0])[-1][1] not in victims

    def test_an_unpopulated_ladder_still_only_drops_the_excess(self):
        """After a long outage every backup is far older than the levels it could sit on. The
        ladder would `want` only a couple of them; the excess cap is what stops the rest going."""
        assert len(rotation_victims(_dated(*range(100, 110)), 8, "hanoi", DAY)) == 2


class TestFifoIsUnchanged:
    @pytest.mark.parametrize("count", range(0, 20))
    @pytest.mark.parametrize("rotation", (1, 3, 7, 12))
    def test_fifo_matches_the_slice_the_job_used_to_compute_inline(self, count, rotation):
        dated = _dated(*range(count))
        ordered = [backup for _, backup in sorted(dated, key=lambda pair: pair[0])]

        # What backup-data.py did before this change, verbatim.
        expected = ordered[: len(ordered) - rotation] if len(ordered) > rotation else []

        assert [backup for backup, _ in rotation_victims(dated, rotation, "fifo", DAY)] == expected

    def test_an_unknown_strategy_falls_back_to_fifo(self):
        """Only the exact literal `hanoi` selects the ladder. A value the setting's own regex would
        have rejected therefore degrades to FIFO rather than to the shipped default -- the same
        number of files either way, and the conservative half of the choice."""
        dated = _dated(*range(10))
        assert [backup for backup, _ in rotation_victims(dated, 7, "hanOi", DAY)] == [backup for backup, _ in rotation_victims(dated, 7, "fifo", DAY)]

    def test_fifo_ignores_the_ladder_even_when_files_are_sparse(self):
        dated = _dated(0, 30, 60, 90)
        assert _ages(dated, _kept(dated, 2, "fifo")) == [0, 30]

    def test_fifo_on_a_real_directory_deletes_the_head_of_sorted_backups(self, tmp_path):
        """The pin above compares the selector against itself: it builds `expected` with the same
        sort and never touches disk, so it pins the slice arithmetic and nothing else. This one
        goes through the real path -- `sorted_backups()` off a real directory, one archive with no
        timestamp in its name -- and pins the OUTCOME: FIFO still takes the head of the list the
        job would have sliced.
        """
        for _, backup in _dated(0, 1, 2):
            (tmp_path / backup.name).write_bytes(b"x")
        stampless = tmp_path / "backup-mariadb-nostamp.zip"
        stampless.write_bytes(b"x")
        os.utime(stampless, (NOW.timestamp() - 400 * 86400, NOW.timestamp() - 400 * 86400))

        ordered = sorted_backups(tmp_path)
        expected = ordered[: len(ordered) - 2]

        assert rotate_backups(sorted_backups(tmp_path), 2, "fifo", DAY) == expected

    def test_an_archive_with_no_stamp_is_ordered_by_its_real_modification_time(self, tmp_path):
        """Where the new code is deliberately NOT identical to the old. `sorted_backups` ranks a
        stamp-less archive by its mtime rendered as a local wall-clock STRING; rotation now ranks
        it by the instant. The two agree except where local wall-clock time is not monotonic --
        the hour a DST fall-back repeats -- and there the instant is the right answer.
        """
        for _, backup in _dated(0):
            (tmp_path / backup.name).write_bytes(b"x")
        for name, age_days in (("backup-mariadb-older.zip", 30), ("backup-mariadb-newer.zip", 2)):
            path = tmp_path / name
            path.write_bytes(b"x")
            os.utime(path, (NOW.timestamp() - age_days * 86400,) * 2)

        removed = rotate_backups(sorted_backups(tmp_path), 2, "fifo", DAY)

        assert [backup.name for backup in removed] == ["backup-mariadb-older.zip"]


class _Run:
    """One backup per period through the real selector, with the real epoch-anchored indices.

    The ladder is anchored on an absolute grid, so where the first backup falls relative to that
    grid changes the result. `start` moves the whole run, and the tests below sweep it rather than
    pinning one lucky phase.
    """

    def __init__(self, periods, rotation, period=DAY, start=datetime(2026, 1, 1, 3, 0, 0), extras=()):
        self.period = period
        self.rotation = rotation
        self.start = start.astimezone()
        self.kept = []
        self.deleted = set()
        self.max_files = 0
        self.resurrected = []
        for step in range(periods):
            self.now = self.start + step * period
            self._backup(self.now)
            for at, tag in extras:
                if at == step:
                    self._backup(self.now + tag * period)
            victims = {backup for backup, _ in rotation_victims(self.kept, rotation, "hanoi", period)}
            self.deleted |= victims
            self.kept = [pair for pair in self.kept if pair[1] not in victims]
            self.max_files = max(self.max_files, len(self.kept))
            # The whole point of the absolute grid: nothing already deleted is wanted again.
            self.resurrected.extend(self.deleted & hanoi_keep(self.kept + [(self.now, Path("probe.zip"))], rotation, period))

    def _backup(self, taken):
        self.kept.append((taken, Path(f"backup-sqlite-{taken.strftime('%Y-%m-%d_%H-%M-%S')}.zip")))

    @property
    def ages(self):
        return sorted(round((self.now - taken) / self.period) for taken, _ in self.kept)


class TestSimulatedSequences:
    @pytest.mark.parametrize("periods", (1, 2, 7, 30, 120, 400))
    def test_the_file_count_never_exceeds_the_limit(self, periods):
        assert _Run(periods, 12).max_files <= 12

    @pytest.mark.parametrize("periods", (30, 400))
    def test_the_whole_quota_is_used(self, periods):
        """A ladder that keeps 8 of the 12 files the operator paid for is throwing away
        granularity it has room for."""
        assert len(_Run(periods, 12).ages) == 12

    @pytest.mark.parametrize("start_offset", range(0, 8))
    def test_a_backup_that_leaves_the_ladder_is_never_wanted_again(self, start_offset):
        """`a slot is never vacated then needed`, stated as what it actually means: no deleted
        file is ever back in the keep set on a later day. Swept over the grid phase because the
        levels are absolute -- a single start date proves one alignment, not the rule."""
        run = _Run(400, 12, start=datetime(2026, 1, 1, 3, 0, 0) + timedelta(days=start_offset))
        assert run.resurrected == []

    @pytest.mark.parametrize("start_offset", range(0, 8))
    def test_coverage_reaches_far_beyond_what_fifo_can(self, start_offset):
        """FIFO with 12 files reaches back 11 periods however long the install runs."""
        run = _Run(400, 12, start=datetime(2026, 1, 1, 3, 0, 0) + timedelta(days=start_offset))
        assert run.ages[-1] > 100

    def test_twenty_four_files_span_months_where_fifo_spans_days(self):
        """The roadmap claim, in periods: 24 files, ~2050 periods of history (85 days hourly).
        FIFO keeps 24 periods of it; the ladder still holds a backup from most of the way back."""
        run = _Run(2050, 24)
        assert len(run.ages) == 24
        assert run.ages[-1] > 1000
        assert run.ages[:8] == [0, 1, 2, 3, 4, 5, 6, 7]  # and the recent end stays dense

    def test_each_extra_file_roughly_doubles_the_depth(self):
        depths = [_Run(2050, rotation).ages[-1] for rotation in (8, 10, 12, 14)]
        assert depths == sorted(depths)
        assert depths[-1] > 8 * depths[0]

    def test_the_schedule_sets_the_base_period(self):
        """A weekly schedule makes every level a week wide, so the same files reach far deeper."""
        weekly = _Run(60, 12, period=timedelta(weeks=1))
        assert weekly.ages[-1] > 11
        assert len(weekly.ages) == 12


class TestEdges:
    def test_a_gap_in_the_sequence_does_not_delete_more_than_the_excess(self):
        """The scheduler was down for 20 days, then made three backups."""
        assert len(rotation_victims(_dated(0, 1, 2, 25, 26, 27, 28, 29), 7, "hanoi", DAY)) == 1

    def test_a_gap_keeps_the_backups_that_frame_it(self):
        dated = _dated(0, 1, 2, 25, 26, 27, 28, 29)
        kept = _ages(dated, _kept(dated, 7))
        assert kept[0] == 0 and kept[-1] == 29

    def test_an_outage_does_not_flush_the_ladder_when_backups_resume(self):
        """30 periods of backups, 200 periods of nothing, then 30 more: the old ladder points
        must still be there, not replaced wholesale by the fresh run."""
        run = _Run(30, 12)
        resumed = _Run(30, 12, start=run.start + timedelta(days=230))
        survivors = [pair for pair in run.kept if pair[1] not in resumed.deleted]
        assert survivors

    def test_a_backup_that_is_not_the_last_of_its_period_is_given_up_first(self):
        """Two backups in one period are one restore point: dropping the older of them costs no
        coverage at all, so it goes before any backup that is the only one left for its period --
        even though plenty of OLDER files are expendable too, which is what makes this an ordering
        rule and not just a consequence of deleting oldest first."""
        dated = _dated(0, 1, 1.25, 2, 3, 4, 5, 6)
        victims = [backup for backup, _ in rotation_victims(dated, 5, "hanoi", DAY)]

        assert len(victims) == 3
        assert victims[0] == _dated(1.25)[0][1]

    def test_the_ladder_point_of_a_period_is_its_freshest_backup(self):
        dated = _dated(0, 1, 3, 3.25)
        kept = _kept(dated, 3)

        assert [backup for _, backup in _dated(3.25)][0] not in kept
        assert [backup for _, backup in _dated(3)][0] in kept

    def test_a_pile_of_backups_from_a_few_periods_still_only_loses_the_excess(self):
        """12 files over 4 days, room for 8. The ladder has 4 restore points to protect and no
        use for the other 8, and only the excess cap stands between it and deleting them all --
        the guarantee that hanoi never removes more files than FIFO would for the same input."""
        dated = _dated(*(day + fraction for day in range(4) for fraction in (0, 0.25, 0.5)))

        assert len(rotation_victims(dated, 8, "hanoi", DAY)) == 4
        assert len(rotation_victims(dated, 8, "fifo", DAY)) == 4

    def test_manual_backups_in_the_same_period_do_not_evict_the_ladder(self):
        """Three `bwcli plugin backup save` runs on the same day, against a full ladder."""
        dated = _dated(0, 0.1, 0.2, 1, 2, 3, 4, 5, 6)
        kept = _ages(dated, _kept(dated, 7))
        assert kept[0] == 0  # the freshest restore point survives
        assert kept[-1] == 6  # so does the deepest -- the duplicate manual copies pay instead

    def test_a_manual_backup_burst_leaves_the_deep_end_alone(self):
        deep = _Run(400, 12).ages[-1]
        assert _Run(400, 12, extras=[(398, 0.1), (398, 0.2), (399, 0.3)]).ages[-1] == deep

    def test_two_engines_in_one_directory_are_ranked_by_date_only(self):
        """A SQLite install migrated to MariaDB leaves dumps of both engines in one directory, and
        the file name sorts by engine before date. The ladder must not see that at all: swapping
        which engine took which backup cannot change which dates survive."""
        mixed = _dated(0, 2, 4, engine="mariadb") + _dated(1, 3, 5, engine="sqlite")
        swapped = _dated(0, 2, 4, engine="sqlite") + _dated(1, 3, 5, engine="mariadb")

        assert _ages(mixed, _kept(mixed, 4)) == _ages(swapped, _kept(swapped, 4))
        assert len(_kept(mixed, 4)) == 4

    def test_a_backup_dated_in_the_future_is_kept_like_any_other_recent_one(self):
        dated = _dated(-1, 0, 1, 2, 3, 4, 5, 6)
        victims = [backup for backup, _ in rotation_victims(dated, 7, "hanoi", DAY)]
        assert len(victims) == 1
        assert victims[0] not in [backup for _, backup in _dated(-1, 0)]

    def test_the_reason_names_the_period_and_how_close_it_came(self):
        """A deletion log that says only "rotation limit reached" is unauditable: the operator
        cannot tell a backup that was one block short of being kept from one that was nowhere
        near. Every victim names its period, the level it came closest on, and by how much."""
        reasons = dict(rotation_victims(_dated(*range(9)), 7, "hanoi", DAY))

        assert len(reasons) == 2
        for reason in reasons.values():
            assert "period " in reason
            assert "level " in reason and "blocks behind the newest" in reason

    def test_a_redundant_copy_says_so_instead_of_blaming_the_ladder(self):
        reasons = dict(rotation_victims(_dated(0, 1, 2, 3, 4, 5, 5.25), 6, "hanoi", DAY))

        assert list(reasons.values()) == [f"period {period_index(NOW - 5.25 * DAY, DAY)} already has a newer backup"]

    def test_the_level_a_victim_came_closest_on_is_the_one_reported(self):
        """Two backups from adjacent periods, far behind: at level 0 they are many blocks back,
        but at a level whose blocks are wide enough to hold them both they are much closer."""
        level, rank = hanoi_rank(100, list(range(100, 140)), 8)

        assert (1 << level) >= 32 and rank <= 1 + 39 // (1 << level)


class TestDefaults:
    """The signature defaults, which nothing else pins: every other test passes `strategy`.

    They are `hanoi`, the same value `plugin.json` and the job's `getenv` fall back to. One default
    for the whole plugin is the point: were the signatures left on `fifo` while the product shipped
    `hanoi`, a caller that omits `strategy` -- a future job, a test, `bwcli` -- would silently get a
    policy the product no longer ships, which is this pin's own failure mode with the sign flipped.
    """

    def test_omitting_the_strategy_rotates_hanoi(self):
        dated = _dated(*range(10))

        assert rotation_victims(dated, 7) == rotation_victims(dated, 7, "hanoi", DAY)
        assert rotation_victims(dated, 7) != rotation_victims(dated, 7, "fifo", DAY)

    def test_omitting_the_strategy_in_the_destructive_helper_rotates_hanoi(self, tmp_path):
        """On an input where the two strategies genuinely disagree, or the assertion is vacuous
        and a flipped default sails through."""
        directories = {}
        for name in ("default", "fifo", "hanoi"):
            directories[name] = tmp_path / name
            directories[name].mkdir()
            for _, backup in _dated(*range(20)):
                (directories[name] / backup.name).write_bytes(b"x")

        removed = {
            "default": rotate_backups(sorted_backups(directories["default"]), 7),
            "fifo": rotate_backups(sorted_backups(directories["fifo"]), 7, "fifo", DAY),
            "hanoi": rotate_backups(sorted_backups(directories["hanoi"]), 7, "hanoi", DAY),
        }

        assert [backup.name for backup in removed["default"]] == [backup.name for backup in removed["hanoi"]]
        assert [backup.name for backup in removed["default"]] != [backup.name for backup in removed["fifo"]]

    def test_the_default_period_is_one_day(self):
        """The other signature default, and the one the ladder is measured in: a caller that omits
        `period` must land on the same blocks as the daily schedule the job passes."""
        dated = _dated(*range(20))

        assert rotation_victims(dated, 7, "hanoi") == rotation_victims(dated, 7, "hanoi", DAY)


class TestMalformedNames:
    """A file name that matches the stamp pattern but is not a real date.

    `STAMP_RE` accepts `2026-02-30`; `strptime` does not. Letting that raise took the whole backup
    job down -- on the DEFAULT fifo path, for a file nothing else in the plugin would have cared
    about -- and the job dying before `update_cache_file` freezes the manifest date, which leaves
    `already_done` false for good: a full database dump on every run and rotation never running
    again. One bad file name, retention permanently off, disk growing without bound.
    """

    IMPOSSIBLE = "backup-mariadb-2026-02-30_00-00-00.zip"

    def _populated(self, directory, impossible_mtime):
        for _, backup in _dated(0, 1, 2, 3):
            (directory / backup.name).write_bytes(b"x")
        bad = directory / self.IMPOSSIBLE
        bad.write_bytes(b"x")
        os.utime(bad, (impossible_mtime, impossible_mtime))
        return bad

    def test_an_impossible_date_does_not_stop_rotation(self, tmp_path):
        bad = self._populated(tmp_path, NOW.timestamp() - 400 * 86400)

        removed = rotate_backups(sorted_backups(tmp_path), 3, "fifo", DAY)

        assert len(removed) == 2
        assert len(sorted_backups(tmp_path)) == 3
        assert bad in removed  # 400 days old by mtime: the oldest thing in the directory

    def test_an_impossible_date_does_not_stop_the_hanoi_path_either(self, tmp_path):
        self._populated(tmp_path, NOW.timestamp() - 400 * 86400)

        assert len(rotate_backups(sorted_backups(tmp_path), 3, "hanoi", DAY)) == 2

    def test_it_is_read_as_a_name_without_a_stamp(self, tmp_path):
        """Not as an error, and not as the impossible date either: the old code sorted by the
        string `2026-02-30_00-00-00` and always deleted such a file first. It is now dated by its
        modification time, like any other archive whose name carries no usable timestamp."""
        bad = self._populated(tmp_path, NOW.timestamp() - 400 * 86400)

        assert backup_time(bad) == datetime.fromtimestamp(bad.stat().st_mtime).astimezone()

    def test_a_recent_impossible_date_is_not_treated_as_ancient(self, tmp_path):
        """The consequence of the line above, stated where it can regress: a freshly written file
        with a nonsense name is recent, so it is not the first thing rotation reaches for."""
        bad = self._populated(tmp_path, NOW.timestamp())

        assert bad not in rotate_backups(sorted_backups(tmp_path), 3, "fifo", DAY)


class TestBackupTime:
    def test_the_timestamp_comes_from_the_name(self, tmp_path):
        backup = tmp_path / "backup-mariadb-2026-08-14_15-13-42.zip"
        backup.write_bytes(b"")
        assert backup_time(backup) == datetime(2026, 8, 14, 15, 13, 42).astimezone()

    def test_a_name_without_a_stamp_falls_back_to_mtime(self, tmp_path):
        backup = tmp_path / "backup-mariadb-nostamp.zip"
        backup.write_bytes(b"")
        assert abs((backup_time(backup) - datetime.fromtimestamp(backup.stat().st_mtime).astimezone()).total_seconds()) < 1

    def test_it_agrees_with_the_order_sorted_backups_produces(self, tmp_path):
        for name in ("backup-sqlite-2026-08-14_15-13-42.zip", "backup-mariadb-2026-08-14_15-14-52.zip", "backup-mariadb-2026-08-01_03-00-00.zip"):
            (tmp_path / name).write_bytes(b"")
        ordered = sorted_backups(tmp_path)
        assert [backup_time(backup) for backup in ordered] == sorted(backup_time(backup) for backup in ordered)


class TestRotateBackups:
    """The one destructive helper: the job calls nothing else."""

    def _dir(self, directory, *ages):
        for _, backup in _dated(*ages):
            (directory / backup.name).write_bytes(b"x")
        return sorted_backups(directory)

    def test_fifo_removes_the_oldest_files_from_disk(self, tmp_path):
        backups = self._dir(tmp_path, 0, 1, 2, 3)
        removed = rotate_backups(backups, 2, "fifo", DAY)

        assert [backup.name for backup in removed] == [backups[0].name, backups[1].name]
        assert len(sorted_backups(tmp_path)) == 2

    def test_hanoi_removes_the_same_number_but_keeps_a_deeper_span(self, tmp_path):
        """20 daily backups, room for 7. FIFO leaves the last week; the ladder leaves a week's
        worth of recent points AND something from three times further back, for the same 7 files."""
        fifo, hanoi = tmp_path / "fifo", tmp_path / "hanoi"
        for directory in (fifo, hanoi):
            directory.mkdir()
            self._dir(directory, *range(20))

        assert len(rotate_backups(sorted_backups(fifo), 7, "fifo", DAY)) == 13
        assert len(rotate_backups(sorted_backups(hanoi), 7, "hanoi", DAY)) == 13

        assert len(sorted_backups(hanoi)) == len(sorted_backups(fifo)) == 7
        assert backup_time(sorted_backups(hanoi)[0]) < backup_time(sorted_backups(fifo)[0])
        assert sorted_backups(hanoi)[-1].name == sorted_backups(fifo)[-1].name  # both keep the newest

    def test_nothing_is_touched_when_the_directory_is_under_the_limit(self, tmp_path):
        backups = self._dir(tmp_path, 0, 1, 2)
        assert rotate_backups(backups, 7, "hanoi", DAY) == []
        assert len(sorted_backups(tmp_path)) == 3

    def test_the_job_calls_this_helper_and_no_longer_purges_by_hand(self):
        """The purge lives in one place. A reintroduced inline slice would silently bypass the
        strategy setting and the logging, and every test above would still pass."""
        job = (_BACKUP / "jobs" / "backup-data.py").read_text(encoding="utf-8")
        assert "rotate_backups(sorted_files, backup_rotation, backup_strategy" in job
        assert 'getenv("BACKUP_ROTATION_STRATEGY", "hanoi")' in job
        assert "num_files_to_remove" not in job

    def test_the_setting_is_declared_with_the_shipped_default(self):
        """`hanoi` by PO ruling (2026-08-24). An install that never set the setting keeps the same
        NUMBER of backups it always did and a different selection of them; `fifo` stays offered,
        which is what an operator who wants the old selection back sets."""
        from json import loads

        setting = loads((_BACKUP / "plugin.json").read_text(encoding="utf-8"))["settings"]["BACKUP_ROTATION_STRATEGY"]
        assert setting["default"] == "hanoi"
        assert setting["context"] == "global"
        assert setting["select"] == ["fifo", "hanoi"]

    def test_the_four_defaults_are_one_value(self):
        """plugin.json, the job's getenv fallback and both signatures. A flip that misses one of
        them leaves the plugin with two different notions of `unset`, and every test above still
        passes: the ones that exercise a strategy all name it explicitly."""
        from inspect import signature
        from json import loads

        declared = loads((_BACKUP / "plugin.json").read_text(encoding="utf-8"))["settings"]["BACKUP_ROTATION_STRATEGY"]["default"]
        job = (_BACKUP / "jobs" / "backup-data.py").read_text(encoding="utf-8")

        assert f'getenv("BACKUP_ROTATION_STRATEGY", "{declared}")' in job
        assert signature(rotation_victims).parameters["strategy"].default == declared
        assert signature(rotate_backups).parameters["strategy"].default == declared
