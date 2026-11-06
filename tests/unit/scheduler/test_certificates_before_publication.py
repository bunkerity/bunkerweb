"""Local certificate jobs must finish before the first cache upload of each configuration."""

from types import SimpleNamespace

import pytest

import test_jobscheduler_jobs as jobs
import test_main_loop

make_scheduler = jobs.make_scheduler
drive = test_main_loop.drive


@pytest.fixture
def certificate_cycle(drive, make_scheduler, job_scheduler_module, monkeypatch, tmp_path):
    cache = drive.sandbox.CACHE_PATH
    trace = tmp_path / "events.txt"
    trace.touch()
    plugins = []
    for plugin, name in (("customcert", "custom-cert"), ("selfsigned", "self-signed"), ("letsencrypt", "certbot-new")):
        script = (
            "import os\nfrom pathlib import Path\n"
            f"trace = Path({str(trace)!r})\n"
            "server = os.environ['SERVER_NAME']\n"
            f"with trace.open('a') as output: output.write({name!r} + ':' + server + '\\n')\n"
        )
        if plugin == "letsencrypt":
            script += "assert 'publish:' + server in trace.read_text()\nraise SystemExit(0)\n"
        else:
            script += (
                f"folder = Path({str(cache / plugin)!r}) / server\n"
                "if os.environ.get('CERT_ACTION') == 'fail': raise SystemExit(2)\n"
                "if os.environ.get('CERT_ACTION') == 'delete':\n"
                "    for path in folder.glob('*.pem'): path.unlink()\n"
                "    raise SystemExit(0)\n"
                "folder.mkdir(parents=True, exist_ok=True)\n"
                "for name in ('cert.pem', 'key.pem'): (folder / name).write_text(server)\n"
                "raise SystemExit(1)\n"
            )
        plugins.append((plugin, [jobs.job(name, name + ".py", "day", True, **{"async": True})], {name + ".py": script}))

    monkeypatch.setattr(drive.db, "test_write", lambda: None, raising=False)
    monkeypatch.setattr(drive.db, "add_job_run", lambda *args: "", raising=False)
    monkeypatch.setattr(drive.db, "last_connection_retry", None, raising=False)
    monkeypatch.setattr(drive.db, "database_uri_readonly", None, raising=False)
    scheduler = make_scheduler(plugins, db=drive.db)
    # Exercise real cache snapshots, redirected to the same tree the test publishes.
    from cache_restore import cache_tree

    monkeypatch.setattr(job_scheduler_module, "cache_tree", lambda _: cache_tree(cache))
    monkeypatch.setattr(drive.main, "JobScheduler", lambda *args, **kwargs: scheduler)
    monkeypatch.setattr(drive.main, "wait_for_reachable_instance", lambda: bool(scheduler.apis))
    monkeypatch.setattr(scheduler, "send_to_apis", drive.sched.send_to_apis)
    snapshots = []

    def send(path, endpoint, *args, **kwargs):
        if endpoint == "/cache":
            server = drive.db.config["SERVER_NAME"]
            snapshots.append((server, {str(p.relative_to(cache)): p.read_text() for p in cache.rglob("*.pem")}))
            with trace.open("a") as output:
                output.write("publish:" + server + "\n")
        return True

    monkeypatch.setattr(drive.main, "send_file_to_bunkerweb", send)
    drive.db.config = {"SERVER_NAME": "first.test"}

    def change():
        drive.db.config = {"SERVER_NAME": "next.test"}
        drive.db.metadata["plugins_config_changed"] = ["customcert", "selfsigned", "letsencrypt"]

    return SimpleNamespace(drive=drive, scheduler=scheduler, trace=trace, snapshots=snapshots, change=change)


@pytest.mark.parametrize("configuration_change", [False, True], ids=["startup", "config-change"])
def test_local_certificate_pairs_are_published_before_challenge_jobs_and_run_once(certificate_cycle, configuration_change):
    cycle = certificate_cycle
    if configuration_change:
        cycle.drive.iterations = 2
        cycle.drive.on_iteration[1] = cycle.change
    cycle.drive.run()
    assert cycle.drive.stops == []
    events = cycle.trace.read_text().splitlines()
    for server in ("next.test",) if configuration_change else ("first.test",):
        first_upload = next(payload for name, payload in cycle.snapshots if name == server)
        for plugin, name in (("customcert", "custom-cert"), ("selfsigned", "self-signed")):
            assert first_upload.get(f"{plugin}/{server}/cert.pem") == server
            assert first_upload.get(f"{plugin}/{server}/key.pem") == server
            assert events.count(f"{name}:{server}") == 1
            assert events.index(f"{name}:{server}") < events.index(f"publish:{server}")
        assert events.count(f"certbot-new:{server}") == 1
        assert events.index(f"publish:{server}") < events.index(f"certbot-new:{server}")


@pytest.mark.parametrize("action", ["fail", "delete"])
def test_certificate_failure_or_exit_zero_deletion_keeps_existing_cache_semantics(certificate_cycle, action, caplog):
    cycle = certificate_cycle
    cycle.drive.iterations = 2

    def change():
        cycle.drive.db.config["CERT_ACTION"] = action
        cycle.drive.db.metadata["plugins_config_changed"] = ["customcert", "selfsigned"]
        cycle.snapshots.clear()
        cycle.trace.write_text("")

    cycle.drive.on_iteration[1] = change
    cycle.drive.run()
    assert cycle.drive.stops == []
    assert cycle.snapshots
    first_upload = cycle.snapshots[0][1]
    for plugin, name in (("customcert", "custom-cert"), ("selfsigned", "self-signed")):
        for pem in ("cert.pem", "key.pem"):
            key = f"{plugin}/first.test/{pem}"
            if action == "fail":
                assert first_upload[key] == "first.test"
            else:
                assert key not in first_upload
        assert cycle.trace.read_text().splitlines().count(f"{name}:first.test") == 1
    if action == "fail":
        assert "Jobs failed in run_once():" in caplog.text
        assert "Error while executing job '" in caplog.text
    else:
        # Exit-0 removal still requests publication, even though neither wrapper requested a reload.
        assert len(cycle.snapshots) == 2


def test_readonly_database_still_skips_certificate_jobs(certificate_cycle):
    cycle = certificate_cycle
    cycle.drive.db.readonly = True
    cycle.drive.run()
    assert cycle.drive.stops == []
    assert cycle.snapshots
    assert all(not payload for _, payload in cycle.snapshots)
    assert not any(name in cycle.trace.read_text() for name in ("custom-cert", "self-signed", "certbot-new"))
