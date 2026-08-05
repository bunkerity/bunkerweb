from pathlib import Path
from unittest.mock import Mock

from api_client import SchedulerApiClient

ROOT = Path(__file__).resolve().parents[3]


def test_endpoint_reconcile_patches_only_endpoint_fields():
    client = SchedulerApiClient.__new__(SchedulerApiClient)
    client._patch = Mock()
    instances = [{"hostname": "bw-1", "credential_set": True}, {"hostname": "bw-2", "listen_https": True}]

    assert client.update_instance_endpoints(instances, 5001, "control") == ""

    assert client._patch.call_args_list == [
        (("/instances/bw-1",), {"json": {"port": 5001, "server_name": "control"}}),
        (("/instances/bw-2",), {"json": {"port": 5001, "server_name": "control"}}),
    ]


def test_scheduler_no_longer_uses_destructive_bulk_reconcile():
    source = (ROOT / "src" / "scheduler" / "main.py").read_text(encoding="utf-8")
    assert "update_instance_endpoints(" in source
    assert "API_CLIENT.update_instances(" not in source
