"""Once-jobs that change cache bytes must publish even when they exit 0.

An unchanged batch must retain the second-push suppression from #4106.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def cache_batch(job_scheduler_module, monkeypatch, tmp_path, sched_logger):
    import jobs

    module = job_scheduler_module
    root = tmp_path / "var/cache/bunkerweb"
    root.mkdir(parents=True)
    monkeypatch.setattr(os, "environ", {"SERVER_NAME": "app.test", "MULTISITE": "no", "SCHEDULER_MAX_WORKERS": "2"})
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(module, "sys_path", sys.path)
    monkeypatch.setattr(module, "glob", lambda _: [])
    monkeypatch.setattr(module, "Path", lambda *args: root if Path(*args) == Path("/var/cache/bunkerweb") else Path(*args))
    monkeypatch.setattr(jobs, "sep", str(tmp_path))
    monkeypatch.setattr(module.JobScheduler, "_JobScheduler__update_cache_permissions", lambda _: None)
    db = SimpleNamespace(
        readonly=False,
        test_write=lambda: None,
        add_job_run=lambda *args: "",
        delete_job_cache=lambda *args, **kwargs: "",
        upsert_job_cache=lambda *args, **kwargs: "",
        get_job_cache_file=lambda *args, **kwargs: None,
    )
    real_job = jobs.Job
    monkeypatch.setattr(jobs, "Job", lambda logger, path: real_job(logger, path, db=db, deprecated=True))
    scheduler = module.JobScheduler(sched_logger, db=db)

    def run(relative, *, env=None):
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        path = ROOT / "src/common/core" / relative
        scheduler._JobScheduler__jobs = {path.parent.parent.name: [{"path": str(path.parent.parent), "name": path.stem, "file": path.name, "async": False}]}
        return scheduler.run_once()

    yield SimpleNamespace(root=root, scheduler=scheduler, run=run, module=module)
    scheduler.cleanup_modules()
    scheduler._JobScheduler__executor.shutdown(wait=True)


def seed(batch, relative, content=b"stale"):
    path = batch.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def publishes(batch, sched_main, monkeypatch):
    monkeypatch.setattr(sched_main, "IGNORE_FAIL_SENDING_CONFIG", False)
    changed, regenerate = batch.scheduler.consume_pending_publication()
    result = sched_main.once_jobs_republish(False, True, True, changed or regenerate, False)
    assert batch.scheduler.consume_pending_publication() == (False, False)
    return result


@pytest.mark.parametrize(
    "relative, cached, env",
    [
        ("crowdsec/jobs/crowdsec-conf.py", "crowdsec/app.test/crowdsec.conf", {"USE_CROWDSEC": "no"}),
        ("customcert/jobs/custom-cert.py", "customcert/app.test/cert.pem", {"USE_CUSTOM_SSL": "no"}),
        ("selfsigned/jobs/self-signed.py", "selfsigned/app.test/cert.pem", {"GENERATE_SELF_SIGNED_SSL": "no"}),
        ("blacklist/jobs/blacklist-download.py", "blacklist/app.test/IP.list", {"USE_BLACKLIST": "yes", "BLACKLIST_COMMUNITY_LISTS": ""}),
        ("greylist/jobs/greylist-download.py", "greylist/app.test/IP.list", {"USE_GREYLIST": "yes"}),
        ("whitelist/jobs/whitelist-download.py", "whitelist/app.test/IP.list", {"USE_WHITELIST": "yes"}),
        ("dnsbl/jobs/dnsbl-download.py", "dnsbl/app.test/IGNORE_IP.list", {"USE_DNSBL": "yes"}),
        ("realip/jobs/realip-download.py", "realip/app.test/combined.list", {"USE_REAL_IP": "yes"}),
        ("robotstxt/jobs/robots-txt-download.py", "robotstxt/app.test/rules.list", {"USE_ROBOTSTXT": "yes"}),
        (
            "robotstxt/jobs/robots-txt-darkvisitors.py",
            "robotstxt/app.test/darkvisitors.list",
            {"USE_ROBOTSTXT": "yes", "ROBOTSTXT_DARKVISITORS_TOKEN": "unit-placeholder", "ROBOTSTXT_DARKVISITORS_AGENT_TYPES": ""},
        ),
    ],
    ids=["crowdsec-off", "customcert-off", "selfsigned-off", "blacklist", "greylist", "whitelist", "dnsbl", "realip", "robotstxt", "darkvisitors"],
)
def test_exit_zero_cache_cleanup_republishes(cache_batch, sched_main, monkeypatch, relative, cached, env):
    stale = seed(cache_batch, cached)
    assert cache_batch.run(relative, env=env) is True
    assert not stale.exists()
    assert publishes(cache_batch, sched_main, monkeypatch) is True
    # Repeating cleanup with nothing left must not force another reload.
    assert cache_batch.run(relative, env=env) is True
    assert publishes(cache_batch, sched_main, monkeypatch) is False


@pytest.mark.parametrize("content, expected", [(None, True), (b"stale", True), (b"fresh", False)])
def test_crowdsec_cache_write_uses_content(cache_batch, sched_main, monkeypatch, content, expected):
    import jinja2

    template = cache_batch.root.parent / "templates"
    template.mkdir()
    (template / "crowdsec.conf").write_bytes(b"fresh")
    loader = jinja2.FileSystemLoader
    monkeypatch.setattr(jinja2, "FileSystemLoader", lambda _: loader(template))
    target = cache_batch.root / "crowdsec/app.test/crowdsec.conf"
    if content is not None:
        seed(cache_batch, "crowdsec/app.test/crowdsec.conf", content)
    assert cache_batch.run("crowdsec/jobs/crowdsec-conf.py", env={"USE_CROWDSEC": "yes", "MULTISITE": "yes", "app.test_USE_CROWDSEC": "yes"}) is True
    assert target.read_bytes() == b"fresh"
    assert publishes(cache_batch, sched_main, monkeypatch) is expected


@pytest.mark.parametrize("has_id", [False, True], ids=["retry-write", "retry-delete"])
def test_bunkernet_retry_cache_changes_publish(cache_batch, sched_main, monkeypatch, has_id):
    monkeypatch.syspath_prepend(str(ROOT / "src/common/core/bunkernet/jobs"))
    import bunkernet

    monkeypatch.setattr(bunkernet, "register", lambda: (True, 429, {}))
    if has_id:
        seed(cache_batch, "bunkernet/instance.id", b"unit-instance")
        seed(cache_batch, "bunkernet/register.retry", b"{}")
    assert cache_batch.run("bunkernet/jobs/bunkernet-register.py") is True
    retry = cache_batch.root / "bunkernet/register.retry"
    if has_id:
        assert not retry.exists()
    else:
        assert json.loads(retry.read_bytes())["code"] == 0
    assert publishes(cache_batch, sched_main, monkeypatch) is True


@pytest.mark.parametrize("exit_code", [0, 2])
def test_direct_cache_write_is_detected_even_on_failure(cache_batch, sched_main, monkeypatch, tmp_path, exit_code):
    plugin = tmp_path / "plugin"
    (plugin / "jobs").mkdir(parents=True)
    target = seed(cache_batch, "plugin/data", b"before")
    script = plugin / "jobs/change.py"
    script.write_text(f"from pathlib import Path\nPath({str(target)!r}).write_bytes(b'after!')\nraise SystemExit({exit_code})\n")
    cache_batch.scheduler._JobScheduler__jobs = {"plugin": [{"path": str(plugin), "name": "change", "file": "change.py"}]}
    assert cache_batch.scheduler.run_once() is (exit_code == 0)
    assert target.read_bytes() == b"after!"
    assert publishes(cache_batch, sched_main, monkeypatch) is True


def test_unreadable_cache_does_not_suppress_publication(cache_batch, sched_main, monkeypatch):
    seed(cache_batch, "crowdsec/app.test/crowdsec.conf")
    monkeypatch.setattr(cache_batch.module, "file_hash", Mock(side_effect=OSError("unreadable")), raising=False)
    assert cache_batch.run("crowdsec/jobs/crowdsec-conf.py", env={"USE_CROWDSEC": "no"}) is True
    assert publishes(cache_batch, sched_main, monkeypatch) is True


def test_unchanged_large_cache_is_hashed_only_once(cache_batch, sched_main, monkeypatch):
    from common_utils import file_hash

    seed(cache_batch, "jobs/country.mmdb", b"unchanged" * 131072)
    hashing = Mock(wraps=file_hash)
    monkeypatch.setattr(cache_batch.module, "file_hash", hashing, raising=False)
    for _ in range(2):
        assert cache_batch.run("crowdsec/jobs/crowdsec-conf.py", env={"USE_CROWDSEC": "no"}) is True
        assert publishes(cache_batch, sched_main, monkeypatch) is False
    assert hashing.call_count == 1


@pytest.mark.parametrize("change, expected", [("same-bytes", False), ("same-mtime", True), ("symlink", True), ("transient", False)])
def test_cache_snapshot_compares_final_payload(cache_batch, sched_main, monkeypatch, tmp_path, change, expected):
    plugin = tmp_path / "plugin"
    (plugin / "jobs").mkdir(parents=True)
    target = seed(cache_batch, "plugin/data", b"before")
    if change == "symlink":
        target.unlink()
        target.symlink_to("old-target")
        operation = "p.unlink(); p.symlink_to('new-target')"
    elif change == "transient":
        operation = "p.with_name('temporary').write_bytes(b'new'); p.with_name('temporary').unlink()"
    elif change == "same-mtime":
        operation = "s = p.stat(); p.write_bytes(b'after!'); os.utime(p, ns=(s.st_atime_ns, s.st_mtime_ns))"
    else:
        operation = "p.write_bytes(b'before')"
    (plugin / "jobs/change.py").write_text(f"import os\nfrom pathlib import Path\np = Path({str(target)!r})\n{operation}\nraise SystemExit(0)\n")
    cache_batch.scheduler._JobScheduler__jobs = {"plugin": [{"path": str(plugin), "name": "change", "file": "change.py", "async": True}]}
    assert cache_batch.scheduler.run_once() is True
    assert publishes(cache_batch, sched_main, monkeypatch) is expected


def test_release_metadata_cache_write_publishes(cache_batch, sched_main, monkeypatch):
    import common_utils

    monkeypatch.setattr(common_utils, "get_version", lambda: "1.6.18")
    monkeypatch.setattr(common_utils, "fetch_bunkerweb_releases", lambda _: [{"tag_name": "v1.6.18", "draft": False, "prerelease": False}])
    assert cache_batch.run("jobs/jobs/update-check.py") is True
    assert json.loads((cache_batch.root / "jobs/latest_release.json").read_bytes())["tag_name"] == "v1.6.18"
    assert publishes(cache_batch, sched_main, monkeypatch) is True


@pytest.mark.parametrize("content, expected", [("after", True), ("before", False)])
def test_folder_cache_uses_instance_files(cache_batch, sched_main, monkeypatch, tmp_path, content, expected):
    plugin = tmp_path / "plugin"
    (plugin / "jobs").mkdir(parents=True)
    target = seed(cache_batch, "plugin/etc/data", b"before")
    (plugin / "jobs/change.py").write_text(
        "from logging import getLogger\nfrom jobs import Job\n"
        "job = Job(getLogger('folder-cache'), __file__)\n"
        f"target = job.job_path / 'etc/data'\ntarget.write_text({content!r})\n"
        "assert job.cache_dir(target.parent)[0]\nraise SystemExit(0)\n"
    )
    cache_batch.scheduler._JobScheduler__jobs = {"plugin": [{"path": str(plugin), "name": "change", "file": "change.py"}]}
    assert cache_batch.scheduler.run_once() is True
    assert target.read_text() == content
    assert publishes(cache_batch, sched_main, monkeypatch) is expected
