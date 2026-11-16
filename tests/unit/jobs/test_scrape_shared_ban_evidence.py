"""Scrape the real job: one evidence fetch per ban, durable snapshot or explicit loss."""

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
BAN_ID = "http:" + "x" * 32
SUMMARY = {"ban_id": BAN_ID, "counter": 50, "event_count": 1, "server_name": "a.example"}


@pytest.mark.parametrize("available", [True, False])
def test_scrape_snapshots_each_shared_ban_once_and_preserves_stream_inline(monkeypatch, available):
    records = [{"id": name, "reason": "bad behavior", "data": dict(SUMMARY)} for name in ("r1", "r2")]
    inline = [{"url": "tcp://example:443", "counter": 20}]
    records.append({"id": "stream", "reason": "bad behavior", "data": inline})
    db, logger = Mock(), Mock()
    db.get_metadata.return_value = {"scheduler_first_start": False}
    db.get_instances.return_value = [{"hostname": "one"}]
    db.batch_upsert_metrics_requests.return_value = ""
    evidence = {**SUMMARY, "events": [{"url": "/kept", "server_name": "a.example"}]} if available else {"ban_id": BAN_ID, "evidence_missing": True}
    requests = []

    class Caller:
        def __init__(self, apis):
            self.apis = apis

        def send_to_apis(self, method, path, **kwargs):
            requests.append(path)
            payload = {"data": records} if path.startswith("/metrics/requests/query") else evidence
            return True, {"one": {"status": "success", "msg": payload}}

    for name, attributes in {
        "API": {"API": Mock(from_instance=lambda instance: SimpleNamespace(endpoint="http://" + instance["hostname"] + ":5000"))},
        "ApiCaller": {"ApiCaller": Caller},
        "logger": {"getLogger": lambda _: logger},
        "jobs": {"Job": lambda *_: Mock(db=db)},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    for key, value in {"METRICS_PERSIST_TO_DB": "yes", "MULTISITE": "no", "USE_METRICS": "yes", "METRICS_BASELINE_SAMPLE_RATE": "0"}.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(ROOT / "src/common/core/metrics/jobs/scrape-persist-reports.py"), run_name="__main__")
    assert result.value.code == 0
    persisted = db.batch_upsert_metrics_requests.call_args.args[0]
    assert persisted[2]["data"] == inline
    expected = evidence if available else {**SUMMARY, "evidence_missing": True}
    assert persisted[0]["data"] == persisted[1]["data"] == expected
    assert requests.count("/metrics/badbehavior/ban/" + BAN_ID) == 1
