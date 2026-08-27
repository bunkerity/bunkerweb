"""CI and local Kubernetes tests must publish the same Minikube ports."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
BUILD_SCRIPT = ROOT / "tests" / "scripts" / "build.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "integration-tests.yml"


def _build_ports(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    match = re.search(r"^\s*minikube_ports=\(\s*(?P<body>.*?)^\s*\)", source, re.MULTILINE | re.DOTALL)
    assert match, f"missing minikube_ports array in {path}"
    ports = {port.replace("${UI_HOST_PORT:-7000}", "7000") for port in re.findall(r'"([^"]+)"', match.group("body"))}
    assert ports, f"empty minikube_ports array in {path}"
    return ports


def _workflow_ports(path: Path) -> set[str]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    start_args = [step.get("with", {}).get("start-args") for step in workflow["jobs"]["test"]["steps"] if "setup-minikube@" in step.get("uses", "")]
    assert len(start_args) == 1 and isinstance(start_args[0], str), f"expected one setup-minikube start-args string in {path}"
    ports = set(re.findall(r"--ports\s+127\.0\.0\.1:(\d+:\d+)", start_args[0]))
    assert len(ports) == start_args[0].count("--ports"), f"unrecognised or duplicate --ports mapping in {path}"
    return ports


def _assert_ports_synced(build_script: Path, workflow: Path) -> None:
    build_ports = _build_ports(build_script)
    workflow_ports = _workflow_ports(workflow)
    assert workflow_ports == build_ports, (
        f"CI minikube ports drift from build.sh: missing={sorted(build_ports - workflow_ports)}, " f"extra={sorted(workflow_ports - build_ports)}"
    )


def test_ci_minikube_ports_match_build_script():
    _assert_ports_synced(BUILD_SCRIPT, WORKFLOW)


def test_sync_guard_detects_a_synthetic_mismatch(tmp_path: Path):
    build_script = tmp_path / "build.sh"
    build_script.write_text('minikube_ports=(\n  "80:80" "${UI_HOST_PORT:-7000}:30070"\n)\n', encoding="utf-8")
    workflow = tmp_path / "integration-tests.yml"
    workflow.write_text(
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      - uses: medyagh/setup-minikube@pinned\n"
        "        with:\n"
        '          start-args: "--ports 127.0.0.1:80:80 --ports 127.0.0.1:7001:30070"\n',
        encoding="utf-8",
    )

    assert _build_ports(build_script) == {"80:80", "7000:30070"}
    with pytest.raises(AssertionError, match="CI minikube ports drift from build.sh"):
        _assert_ports_synced(build_script, workflow)
