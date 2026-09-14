"""Exercise the early Kubernetes fixture gate without running the integration harness.

The gate precedes all setup branches. Sync replaces host directories, so a pod that
already mounted the old directory cannot pick up its replacement through ACL LOAD.
"""

import subprocess
from pathlib import Path

import pytest

START_SH = Path(__file__).resolve().parents[3] / "tests/scripts/start.sh"


def _fixture_gate():
    source = START_SH.read_text()
    before, after = source.split("export BW_VERSION\n", 1)
    gate, setup = after.split('if [ "$integration" == "Swarm" ] ; then', 1)
    assert "sync_minikube_fixtures" not in before
    calls = [line for line in source.splitlines() if line.strip().startswith("sync_minikube_fixtures ")]
    assert len(calls) == 1, "sync fixtures once, before all setup branches"
    for manifest in ("redis-master", "redis-sentinel", "valkey", "valkey-sentinel"):
        apply = f"kubectl apply -f tests/misc/k8s/{manifest}.yml"
        assert apply in setup, f"{apply} must follow the fixture gate"
    return gate


@pytest.mark.parametrize("integration", ["Kubernetes", "Docker", "Swarm", "Autoconf"])
def test_fixture_sync_runs_once_only_for_kubernetes(integration):
    script = 'sync_minikube_fixtures() { echo synced; }; integration="$1";\n' + _fixture_gate()
    result = subprocess.run(["bash", "-c", script, "test", integration], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ("synced\n" if integration == "Kubernetes" else "")


def test_failed_fixture_sync_stops_before_any_apply():
    script = "sync_minikube_fixtures() { return 1; }; integration=Kubernetes;\n" + _fixture_gate() + "\necho continued"
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stdout == ""
