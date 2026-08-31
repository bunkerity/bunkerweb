"""CI and local Kubernetes tests derive Minikube ports from one list."""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
PORTS_SCRIPT = ROOT / "tests" / "scripts" / "minikube-ports.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "integration-tests.yml"


def _defined_ports(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    match = re.search(r"^minikube_ports=\(\s*(?P<body>.*?)^\)", source, re.MULTILINE | re.DOTALL)
    assert match, f"missing minikube_ports array in {path}"
    ports = {port.replace("${UI_HOST_PORT:-7000}", "7000") for port in re.findall(r'"([^"]+)"', match.group("body"))}
    assert ports, f"empty minikube_ports array in {path}"
    return ports


def _workflow_port_step(path: Path) -> str:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["test"]["steps"]
    port_steps = [step for step in steps if step.get("id") == "mk_ports"]
    assert len(port_steps) == 1 and isinstance(port_steps[0].get("run"), str), f"expected one mk_ports shell step in {path}"

    setup_steps = [step for step in steps if "setup-minikube@" in step.get("uses", "")]
    assert len(setup_steps) == 1, f"expected one setup-minikube step in {path}"
    start_args = setup_steps[0].get("with", {}).get("start-args")
    output_ref = "${{ steps.mk_ports.outputs.args }}"
    assert isinstance(start_args, str) and start_args.count(output_ref) == 1, f"setup-minikube must consume {output_ref} once"
    assert "--ports" not in start_args, f"setup-minikube still hardcodes --ports in {path}"
    return port_steps[0]["run"]


def _render_workflow_ports(root: Path, workflow: Path, output_file: Path) -> set[str]:
    env = os.environ.copy()
    env["GITHUB_OUTPUT"] = str(output_file)
    # _defined_ports normalizes ${UI_HOST_PORT:-7000} textually; pin the shell to the same value
    # so a developer's exported UI_HOST_PORT (tests/README.md workaround) cannot red the guard.
    env["UI_HOST_PORT"] = "7000"
    subprocess.run(["bash", "-eu", "-o", "pipefail", "-c", _workflow_port_step(workflow)], cwd=root, env=env, check=True)

    outputs = dict(line.split("=", 1) for line in output_file.read_text(encoding="utf-8").splitlines())
    args = outputs.get("args", "")
    ports = re.findall(r"--ports\s+127\.0\.0\.1:([^\s]+)", args)
    assert len(ports) == args.count("--ports"), f"unrecognised --ports argument in {args!r}"
    assert len(set(ports)) == len(ports), f"duplicate --ports argument in {args!r}"
    return set(ports)


def _assert_ports_derived(root: Path, workflow: Path, output_file: Path) -> None:
    defined_ports = _defined_ports(root / "tests" / "scripts" / "minikube-ports.sh")
    workflow_ports = _render_workflow_ports(root, workflow, output_file)
    assert workflow_ports == defined_ports, (
        f"derived CI minikube ports differ from minikube_ports: missing={sorted(defined_ports - workflow_ports)}, "
        f"extra={sorted(workflow_ports - defined_ports)}"
    )


def test_ci_minikube_ports_are_derived_from_the_shared_list(tmp_path: Path):
    _assert_ports_derived(ROOT, WORKFLOW, tmp_path / "github-output")


def test_derivation_guard_detects_tampered_helper_output(tmp_path: Path):
    helper = tmp_path / "tests" / "scripts" / "minikube-ports.sh"
    helper.parent.mkdir(parents=True)
    source = PORTS_SCRIPT.read_text(encoding="utf-8")
    tampered = source.replace('"127.0.0.1:${mapping}"', '"127.0.0.1:${mapping/80:80/81:81}"', 1)
    assert tampered != source
    helper.write_text(tampered, encoding="utf-8")

    workflow = tmp_path / ".github" / "workflows" / "integration-tests.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(AssertionError, match="derived CI minikube ports differ"):
        _assert_ports_derived(tmp_path, workflow, tmp_path / "github-output")


def test_build_sh_consumes_the_shared_list():
    """build.sh must source the helper and must not grow its own inline list back — the local
    cluster side has no other guard (build.sh has no `set -u`, so a dropped source silently
    starts minikube with zero port publishes)."""
    source = (ROOT / "tests" / "scripts" / "build.sh").read_text(encoding="utf-8")
    assert re.search(r"^\s*source\s+.*minikube-ports\.sh", source, re.MULTILINE), "build.sh no longer sources tests/scripts/minikube-ports.sh"
    assert "minikube_ports=(" not in source, "build.sh redefines minikube_ports inline; the shared list in minikube-ports.sh is the only source of truth"
