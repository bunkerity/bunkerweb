"""Scheduler permission normalization must not reinstall unchanged plugin archives."""

from io import BytesIO
from pathlib import Path
from tarfile import open as tar_open
from unittest.mock import Mock

import pytest


@pytest.fixture
def installed_plugin(sched_main, sandbox, fake_sched, tmp_path, monkeypatch):
    source = tmp_path / "source" / "demo"
    files = {
        "plugin.json": '{"id":"demo"}',
        "jobs/run.py": "pass",
        "jobs/sub/helper.py": "pass",
        "bwcli/run": "exit 0",
        "ui/view.py": "pass",
        "ui/page.html": "page",
    }
    for name, content in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        path.chmod(0o644)
    blob = sched_main.create_plugin_tar_gz(source).getvalue()
    row = {"id": "demo", "name": "Demo", "method": "ui", "checksum": sched_main.bytes_hash(blob, algorithm="sha256"), "data": blob}
    fake_sched.db.plugins = [row]
    extract = Mock(wraps=sched_main.safe_tar_extractall)
    monkeypatch.setattr(sched_main, "safe_tar_extractall", extract)
    return source, row, extract


@pytest.mark.parametrize("pro,method", [(False, "ui"), (False, "scheduler"), (True, "scheduler")])
def test_two_generations_extract_an_unchanged_plugin_only_once(sched_main, sandbox, installed_plugin, pro, method):
    _, row, extract = installed_plugin
    row["method"] = method
    target = sandbox.PRO_PLUGINS_PATH if pro else sandbox.EXTERNAL_PLUGINS_PATH
    sched_main.generate_external_plugins(target, send=False)
    assert extract.call_count == 1
    assert (target / "demo/jobs/run.py").stat().st_mode & 0o777 == 0o750
    sched_main.generate_external_plugins(target, send=False)
    assert extract.call_count == 1


def test_legacy_archive_directory_modes_do_not_trigger_reextraction(sched_main, sandbox, installed_plugin):
    source, row, extract = installed_plugin
    for path in (source, *source.rglob("*")):
        if path.is_dir():
            path.chmod(0o750)
    stream = BytesIO()
    with tar_open(fileobj=stream, mode="w:gz") as archive:
        archive.add(source, arcname="demo")
    row["data"] = stream.getvalue()
    row["checksum"] = sched_main.bytes_hash(row["data"], algorithm="sha256")
    for _ in range(2):
        sched_main.generate_external_plugins(sandbox.EXTERNAL_PLUGINS_PATH, send=False)
    assert extract.call_count == 1


@pytest.mark.parametrize("change", ["content", "missing", "extra", "job-mode", "asset-mode", "checksum"])
def test_actual_plugin_changes_still_trigger_reextraction(sched_main, sandbox, installed_plugin, change):
    _, row, extract = installed_plugin
    target = sandbox.EXTERNAL_PLUGINS_PATH
    sched_main.generate_external_plugins(target, send=False)
    job = target / "demo/jobs/run.py"
    if change == "content":
        job.write_text("FAIL")
    elif change == "missing":
        job.unlink()
    elif change == "extra":
        job.with_name("extra.py").write_text("extra")
    elif change == "job-mode":
        job.chmod(0o700)
    elif change == "asset-mode":
        (target / "demo/ui/page.html").chmod(0o600)
    else:
        row["checksum"] = "changed"
    sched_main.generate_external_plugins(target, send=False)
    assert extract.call_count == 2
    assert job.read_text() == "pass"


@pytest.mark.parametrize("filename", ["../escape.py", "sub/../../escape.py", "/tmp/escape.py", "sub/../run.py"])
def test_job_validation_refuses_absolute_paths_and_parent_components(job_scheduler_module, filename):
    scheduler = job_scheduler_module.JobScheduler.__new__(job_scheduler_module.JobScheduler)
    scheduler._JobScheduler__logger = Mock()
    scheduler._JobScheduler__compiled_regexes = scheduler._JobScheduler__compile_regexes()
    definition = {"name": "job", "file": filename, "every": "once", "reload": False}
    assert scheduler._JobScheduler__validate_jobs([definition], "demo", "/plugins/demo/plugin.json") == []


def test_every_shipped_job_definition_remains_valid(job_scheduler_module):
    import json

    scheduler = job_scheduler_module.JobScheduler.__new__(job_scheduler_module.JobScheduler)
    scheduler._JobScheduler__logger = Mock()
    scheduler._JobScheduler__compiled_regexes = scheduler._JobScheduler__compile_regexes()
    core = Path(__file__).resolve().parents[3] / "src/common/core"
    checked = 0
    for plugin in core.glob("*/plugin.json"):
        definitions = json.loads(plugin.read_text()).get("jobs", [])
        assert len(scheduler._JobScheduler__validate_jobs(definitions, plugin.parent.name, str(plugin))) == len(definitions)
        checked += len(definitions)
    assert checked > 0


def test_a_job_symlink_cannot_leave_its_jobs_folder(job_scheduler_module, tmp_path):
    plugin = tmp_path / "demo"
    (plugin / "jobs").mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("pass")
    (plugin / "jobs/link.py").symlink_to(outside)
    scheduler = job_scheduler_module.JobScheduler.__new__(job_scheduler_module.JobScheduler)
    scheduler._JobScheduler__logger = Mock()
    scheduler._JobScheduler__compiled_regexes = scheduler._JobScheduler__compile_regexes()
    definition = {"name": "job", "file": "link.py", "every": "once", "reload": False}
    assert scheduler._JobScheduler__validate_jobs([definition], "demo", str(plugin / "plugin.json")) == []
