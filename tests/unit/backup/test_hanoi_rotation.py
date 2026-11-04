"""`hanoi_rotation` -- what survives months of hourly backups, and the job that drives it.

The first version anchored its windows on *now* and kept the newest backup of each window. As the
windows slid an hour per run, the backup a window would need an hour later had already been deleted
by the window before it: after 100 days it held 16 files instead of 24, missed the 2h and 3h old
backups, and reached back 64 days. Buckets are aligned on the epoch now, each twice as wide as the
one before, so the backup a coarse bucket keeps is one a finer bucket kept.

The job compared the last backup's end time against "one hour ago", and the next hourly run starts
an hour after the previous one started, so every other run skipped: `hanoi` backed up every 2 hours.
"""

import logging
import os
import random
import re
import sys
from datetime import datetime, timedelta
from json import dumps
from pathlib import Path
from runpy import run_path
from time import tzset
from types import ModuleType, SimpleNamespace

import pytest

_BACKUP = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import backup  # noqa: E402

START = datetime(2026, 1, 1, 0, 0, 30).astimezone()


@pytest.fixture(autouse=True)
def _utc(monkeypatch):
    """Pin UTC so the long simulations do not depend on the machine's zone; the DST hour has its own test."""
    monkeypatch.setenv("TZ", "UTC")
    tzset()
    yield
    monkeypatch.undo()
    tzset()


def _name(when):
    return Path(f"backup-sqlite-{when.strftime('%Y-%m-%d_%H-%M-%S')}.zip")


def _taken(path):
    return datetime.strptime(re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", path.name).group(1), "%Y-%m-%d_%H-%M-%S").astimezone()


def _tier_width_hours(age_hours):
    start = 0.0
    for count, interval in backup.HANOI_TIERS:
        width = interval.total_seconds() / 3600
        if age_hours < start + count * width:
            return width
        start += count * width
    return None


def _simulate(days, skip=range(0)):
    """Run the job's rotation after every hourly backup (with jitter); yield (now, kept files) after each run."""
    rng = random.Random(1)
    start = START.astimezone()  # in the pinned time zone
    files = []
    for hour in range(24 * days):
        if hour in skip:
            continue
        now = start + timedelta(hours=hour, seconds=rng.randint(0, 90))
        files.append(_name(now))
        deleted = set(backup.hanoi_rotation(files, now))
        files = [f for f in files if f not in deleted]
        yield now, files


def test_months_of_hourly_backups_keep_24_to_34_files_reaching_64_to_85_days():
    counts, oldest = [], []
    for hour, (now, files) in enumerate(_simulate(days=120)):
        if hour >= 24 * 90:
            counts.append(len(files))
            oldest.append((now - min(map(_taken, files))) / timedelta(days=1))

    # 34 is the bound: each tier's age range touches at most one bucket more than its count (24 + 10)
    assert 24 <= min(counts) and max(counts) <= sum(count + 1 for count, _ in backup.HANOI_TIERS) == 34
    assert 64 <= min(oldest) and max(oldest) <= 85.5


def test_the_gap_between_kept_backups_never_exceeds_the_bucket_width_of_their_tier():
    for hour, (now, files) in enumerate(_simulate(days=100)):
        if hour < 24 * 90:
            continue
        ages = sorted((now - _taken(f)) / timedelta(hours=1) for f in files)
        assert ages[:7] == pytest.approx([0, 1, 2, 3, 4, 5, 6], abs=0.05), f"recent hours missing at {now}: {ages[:7]}"
        for younger, older in zip(ages, ages[1:]):
            assert older - younger <= _tier_width_hours(older) * 1.05, f"gap {younger:.1f}h -> {older:.1f}h at {now}"


def test_an_outage_does_not_open_a_gap_in_the_backups_taken_before_it():
    *_, (now, files) = _simulate(days=50, skip=range(24 * 40, 24 * 43))
    ages = sorted((now - _taken(f)) / timedelta(hours=1) for f in files)
    before_outage = [age for age in ages if age > 24 * 10]
    for younger, older in zip(before_outage, before_outage[1:]):
        assert older - younger <= _tier_width_hours(older) * 1.05


def test_the_hour_a_dst_change_repeats_keeps_one_backup_per_hour(tmp_path, monkeypatch):
    """Names carry local time without an offset: 02:30 CEST and 02:30 CET share a name pattern, and only
    the file's modification time tells them apart. Parsed as one instant, a backup looked an hour off."""
    monkeypatch.setenv("TZ", "Europe/Berlin")
    tzset()
    start = datetime(2026, 10, 24, 18, 0, 20).astimezone()  # CEST; clocks go back at 03:00 on the 25th
    files = []
    for hour in range(18):
        # A different second each run: two runs at the same second of the repeated hour would share a name
        now = (start + timedelta(hours=hour, seconds=hour)).astimezone()
        path = tmp_path / _name(now).name
        path.write_bytes(b"")
        os.utime(path, (now.timestamp(), now.timestamp()))
        files.append(path)
        deleted = set(backup.hanoi_rotation(files, now))
        files = [f for f in files if f not in deleted]

        if hour >= 6:
            ages = sorted((now - backup.backup_taken_at(f, datetime.strptime(f.name[14:33], "%Y-%m-%d_%H-%M-%S"))) / timedelta(hours=1) for f in files)
            assert ages[:7] == pytest.approx([0, 1, 2, 3, 4, 5, 6], abs=0.01), f"at {now}: {ages[:7]}"


def test_future_dated_and_foreign_files_are_never_deleted():
    now = START.astimezone() + timedelta(days=200)
    future = _name(now + timedelta(hours=3))
    foreign = Path("backup-notes.zip")
    old = _name(now - timedelta(days=150))

    deleted = backup.hanoi_rotation([future, foreign, old], now)

    assert deleted == [old]


# --- the job ------------------------------------------------------------------------------------


class _FakeBackup(ModuleType):
    def __init__(self):
        super().__init__("backup")
        self.backups = []
        self.DatabaseLockBusy = type("DatabaseLockBusy", (Exception,), {})
        self.hanoi_rotation = backup.hanoi_rotation
        self.acquire_db_lock = lambda *args, **kwargs: 41
        self.release_db_lock = lambda handle: None
        self.update_cache_file = lambda *args, **kwargs: ""

    def backup_database(self, current_time, db, backup_dir):
        self.backups.append(current_time)
        backup_dir.joinpath(_name(current_time).name).write_bytes(b"")
        return db, None


def _run_job(tmp_path, monkeypatch, last_backup, existing=()):
    fake = _FakeBackup()
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    for when in existing:
        backup_dir.joinpath(_name(when).name).write_bytes(b"")
    job = SimpleNamespace(
        get_cache=lambda name: dumps({"date": last_backup.isoformat()}).encode(),
        db=SimpleNamespace(get_metadata=lambda: {"scheduler_first_start": False}),
    )
    monkeypatch.setitem(sys.modules, "backup", fake)
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: job))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    monkeypatch.setitem(sys.modules, "Database", SimpleNamespace(Database=None))
    for key, value in {"BACKUP_SCHEDULE": "hanoi", "BACKUP_DIRECTORY": str(backup_dir), "BACKUP_ROTATION": "1"}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("FORCE_BACKUP", raising=False)
    monkeypatch.delenv("USE_BACKUP", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        run_path(str(_BACKUP / "jobs" / "backup-data.py"), run_name="__main__")
    return exit_info.value.code, fake, sorted(p.name for p in backup_dir.iterdir())


def test_the_previous_hourly_backup_does_not_skip_this_run(tmp_path, monkeypatch):
    # The last run started an hour ago and its backup ended 50 seconds later: the old check skipped this run
    last = datetime.now().astimezone() - timedelta(minutes=59, seconds=10)

    status, fake, _ = _run_job(tmp_path, monkeypatch, last)

    assert status == 0
    assert len(fake.backups) == 1


def test_a_backup_taken_minutes_ago_skips_this_run(tmp_path, monkeypatch):
    last = datetime.now().astimezone() - timedelta(minutes=10)

    status, fake, _ = _run_job(tmp_path, monkeypatch, last)

    assert status == 0
    assert fake.backups == []


def test_the_job_applies_hanoi_rotation_and_ignores_backup_rotation(tmp_path, monkeypatch):
    now = datetime.now().astimezone()
    hourly = [now - timedelta(hours=hours) for hours in range(1, 6)]
    too_old = now - timedelta(days=120)

    status, _, left = _run_job(tmp_path, monkeypatch, now - timedelta(hours=2), existing=[*hourly, too_old])

    assert status == 0
    assert _name(too_old).name not in left
    assert all(_name(when).name in left for when in hourly), "BACKUP_ROTATION=1 must not apply to hanoi"
    assert len(left) == 6  # the five hourly backups and the one this run took
