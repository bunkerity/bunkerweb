import gzip

from jobs import Job


class _CacheDB:
    def __init__(self):
        self.payloads = []

    def upsert_job_cache(self, _service_id, _name, content, **_kwargs):
        self.payloads.append(content)
        return ""


def test_cache_dir_bytes_do_not_depend_on_the_gzip_clock(tmp_path, monkeypatch):
    monkeypatch.setattr("jobs.CACHE_PATH", tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("payload.txt").write_text("unchanged", encoding="utf-8")
    db = _CacheDB()
    job = Job.__new__(Job)
    job.db = db
    job.job_name = "backup"
    job.job_path = tmp_path / "cache"
    # `cache_file` logs through it now that it takes the cache publication lock; a real Job always
    # has one (`Job.__init__`), this partial one has to be told.
    job.logger = None

    monkeypatch.setattr(gzip.time, "time", lambda: 100)
    assert job.cache_dir(source) == (True, "")
    monkeypatch.setattr(gzip.time, "time", lambda: 200)
    assert job.cache_dir(source) == (True, "")

    assert db.payloads[0] == db.payloads[1]
    assert int.from_bytes(db.payloads[0][4:8], "little") == 0
