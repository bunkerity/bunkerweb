"""`bunkernet-stats` must not ping the instances before the deployment is registered.

The connectivity probe is best-effort, but it is not free: an instance with no BunkerNet ID
answers `POST /bunkernet/ping` with HTTP 500 "missing instance ID", and `ApiCaller` logs that
as an ❌ line. On the integrations where the worker and the scheduler share one log stream
(All-in-one, Linux) that line lands in the "scheduler" logs and fails every core spec that
asserts a clean log — `db`, `modsecurity`, `upgrade`. `USE_BUNKERNET=no` is the common case:
`bunkernet-register` skips, so no ID is ever cached, yet the stats job pinged anyway.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "bunkernet" / "jobs" / "bunkernet-stats.py"


def _run(instance_id):
    """Execute the job end to end against stubbed deps; return the ApiCaller stub and the rows."""
    caller_cls = MagicMock()
    stubs = {name: ModuleType(name) for name in ("API", "ApiCaller", "logger", "jobs")}
    stubs["API"].API = MagicMock()
    stubs["ApiCaller"].ApiCaller = caller_cls
    stubs["logger"].getLogger = Mock(return_value=Mock())

    job = MagicMock()
    job.db.get_metadata.return_value = {"scheduler_first_start": False}
    job.db.get_job_cache_file.side_effect = lambda name, _file: {
        "bunkernet-data": b"1.2.3.4\n",
        "bunkernet-send": b'{"reports": []}',
        "bunkernet-register": instance_id,
    }[name]
    job.db.get_instances.return_value = [{"hostname": "bw-1"}]
    job.db.ext.return_value.upsert_stats.return_value = ""
    stubs["jobs"].Job = Mock(return_value=job)

    module = ModuleType("bw_bunkernet_stats")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        with pytest.raises(SystemExit) as exit_info:
            exec(compile(JOB_PATH.read_text(encoding="utf-8"), str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    assert exit_info.value.code == 0
    rows = job.db.ext.return_value.upsert_stats.call_args[0][0]
    return caller_cls, rows


def _metric(rows, name):
    return next(row["value"] for row in rows if row["metric"] == name)


@pytest.mark.parametrize("instance_id", [None, b"", b"   \n"])
def test_no_ping_without_an_instance_id(instance_id):
    caller_cls, rows = _run(instance_id)
    caller_cls.assert_not_called()
    assert _metric(rows, "registered") == 0
    assert not [row for row in rows if row["metric"] == "connected"]


def test_pings_once_registered():
    caller_cls, rows = _run(b"an-instance-id\n")
    caller_cls.return_value.send_to_apis.assert_called_once_with("POST", "/bunkernet/ping", response=True)
    assert _metric(rows, "registered") == 1
