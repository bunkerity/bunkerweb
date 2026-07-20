"""Keep certificate inventory synchronized after certbot cache writes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "src" / "common" / "core" / "letsencrypt" / "jobs"


def test_certbot_jobs_sync_inventory_after_successful_cache_write():
    for name in ("certbot-new.py", "certbot-renew.py"):
        source = JOBS.joinpath(name).read_text()
        cache_write = source.index("cached, err = JOB.cache_dir(DATA_PATH)")
        cache_error = source.index("if not cached:", cache_write)
        sync = source.index("JOB.db.import_legacy_certbot_certificates()", cache_error)

        assert cache_write < cache_error < sync
        assert source.count("JOB.db.import_legacy_certbot_certificates()") == 1
