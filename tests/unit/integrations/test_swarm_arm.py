"""The Swarm arm: the four invariants it cannot be allowed to lose silently.

The arm is `tests/swarm/harness-stack.yml` deployed as one stack by `tests/scripts/start.sh`,
with the application layer converted out of `/tmp/services.yml` by
`tests/scripts/swarm-services.py`. Each test below guards a failure that produces a GREEN or a
misleading run rather than an obvious one:

1. **The label move.** `SwarmController` reads SERVICE labels (`Spec.Labels`) and never looks at
   a container. A converter that stopped moving them would leave a stack that comes up perfectly,
   discovers nothing, and fails every assertion against a default server — with nothing anywhere
   naming labels.
2. **The stack-glob boundary.** `test_swarm_spec_images.py` and `test_swarm_spec_ports.py` both
   enumerate `tests/swarm/stack*.yml`. The arm's stack takes 80/443/8888 ON PURPOSE, because it
   IS the harness — if it ever matched that glob, the port test would fail for a wrong reason and
   the honest answer would be to weaken the test.
3. **The image set.** `--resolve-image never` means an image the workflow did not retag is simply
   absent and the task is rejected with "No such image"; that is exactly how all three swarm
   specs died on the Docker arm in run 32508782608.
4. **The enrolment list.** Swarm is opt-in in `tests/parse.py`: `integrations: "all"` excludes it
   so that flipping a runner into `integrations.yml` cannot enrol ~70 unproven specs at once.
   This pins the specs that actually opted in, so widening the arm is a deliberate edit here and
   not a side effect somewhere else.
"""

import re
import sys
from pathlib import Path

import pytest
from yaml import safe_load

ROOT = Path(__file__).resolve().parents[3]
SWARM_DIR = ROOT / "tests" / "swarm"
ARM_STACKS = sorted(SWARM_DIR.glob("harness-stack*.yml"))
SPEC_STACKS = sorted(SWARM_DIR.glob("stack*.yml"))
CONVERT_SCRIPT = ROOT / "tests" / "scripts" / "swarm-services.py"
WORKFLOW = ROOT / ".github" / "workflows" / "integration-tests.yml"
PARSE = ROOT / "tests" / "parse.py"

# The specs the Swarm arm runs in CI. Deliberately explicit and deliberately short: it is the set
# that has been executed on a real single-node swarm, not the set that is theoretically eligible.
# Adding a name here without running it is the failure mode this constant exists to make loud.
EXPECTED_SWARM_SPECS: set = set()


def _convert_module():
    """Import swarm-services.py by path — the filename is not an importable module name."""
    sys.path.insert(0, str(CONVERT_SCRIPT.parent))
    try:
        from importlib.util import module_from_spec, spec_from_file_location

        spec = spec_from_file_location("swarm_services", CONVERT_SCRIPT)
        assert spec and spec.loader, CONVERT_SCRIPT
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


# ------------------------------------------------------------------ 1. the label move


def test_the_converter_moves_container_labels_onto_the_service():
    convert = _convert_module().convert
    out = convert(
        {
            "services": {
                "app1": {
                    "image": "nginx",
                    "container_name": "app1",
                    "labels": {"bunkerweb.SERVER_NAME": "www.example.com", "bunkerweb.NAMESPACE": "bw-tests"},
                    "networks": {"bw-services": {"ipv4_address": "192.168.0.254"}},
                }
            }
        }
    )
    app1 = out["services"]["app1"]
    # SwarmController reads this and only this.
    assert app1["deploy"]["labels"]["bunkerweb.SERVER_NAME"] == "www.example.com"
    # And the container label survives, which is what keeps a Docker autoconf controller elsewhere
    # on the daemon from adopting the container.
    assert app1["labels"]["bunkerweb.NAMESPACE"] == "bw-tests"


def test_the_converter_drops_what_swarm_rejects_and_replaces_it_with_an_alias():
    convert = _convert_module().convert
    out = convert(
        {
            "services": {
                "app1": {
                    "image": "nginx",
                    "container_name": "app1",
                    "restart": "unless-stopped",
                    "networks": {"bw-services": {"ipv4_address": "192.168.0.254"}},
                }
            }
        }
    )
    app1 = out["services"]["app1"]
    # `docker stack deploy` REJECTS ipv4_address outright; container_name/restart it silently
    # ignores, which is worse — the file would claim something that never happens.
    assert "ipv4_address" not in app1["networks"]["bw-services"]
    assert "container_name" not in app1 and "restart" not in app1
    # dnsmasq.hosts hardcodes `192.168.0.254 app1.bw-services`; build.sh comments that row out for
    # this arm, so the dotted name has to resolve through Docker's own resolver instead.
    assert app1["networks"]["bw-services"]["aliases"] == ["app1", "app1.bw-services"]


def test_the_converter_marks_only_the_harness_networks_external():
    convert = _convert_module().convert
    out = convert(
        {
            "services": {"a": {"image": "x", "networks": ["bw-services", "private"]}},
            "networks": {"private": {"driver": "bridge"}},
        }
    )
    # start.sh pre-created bw-services as an attachable overlay; a spec's own network is not its
    # business and must keep whatever the compose file said.
    assert out["networks"]["bw-services"] == {"external": True}
    assert out["networks"]["private"] == {"driver": "bridge"}


# ------------------------------------------------------------------ 2. the stack-glob boundary


def test_there_are_stacks_on_both_sides_of_the_glob():
    """Two globs that matched nothing would make every assertion below vacuously true."""
    assert ARM_STACKS, "tests/swarm/harness-stack*.yml matched nothing — the Swarm arm lost its stack"
    assert len(SPEC_STACKS) >= 2, "tests/swarm/stack*.yml matched fewer than the swarm specs deploy"


def test_the_arm_stack_is_not_swept_by_the_swarm_spec_tests():
    """`test_swarm_spec_ports.py` asserts a stack publishes nothing the harness holds. The arm's
    stack publishes 80, 443 and 8888 BECAUSE it is the harness, so it must stay outside that glob:
    renaming it to `stack-harness.yml` would fail that test for entirely the wrong reason."""
    overlap = set(ARM_STACKS) & set(SPEC_STACKS)
    assert not overlap, f"the arm's stack now matches tests/swarm/stack*.yml: {sorted(p.name for p in overlap)}"


def test_the_arm_stack_takes_the_harness_ports_on_purpose():
    """The mirror of the test above: if the arm stopped publishing the harness ports, every spec
    would silently be hitting nothing, so pin the intent rather than only the file name."""
    published = set()
    for stack in ARM_STACKS:
        for service in (safe_load(stack.read_text(encoding="utf-8")).get("services") or {}).values():
            for port in service.get("ports") or []:
                published.add(str(port["published"]) if isinstance(port, dict) else str(port))
    assert {"80", "443", "8888"} <= published, f"the Swarm arm no longer serves the harness ports: {sorted(published)}"


# ------------------------------------------------------------------ 3. the image set


def _retagged_images() -> set:
    """Every `bunkerity/<image>:tests` name the workflow retags for the Swarm arm."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    retagged = set()
    for step in re.split(r"\n      - name: ", workflow):
        if "Swarm" not in step.partition("run:")[0]:
            continue
        retagged.update(re.findall(r"(bunkerity/[\w-]+):tests", step))
    return retagged


def test_the_workflow_retags_every_image_the_arm_deploys():
    deployed = set()
    for stack in ARM_STACKS:
        for service in (safe_load(stack.read_text(encoding="utf-8")).get("services") or {}).values():
            image = service.get("image", "")
            if image.startswith("bunkerity/"):
                deployed.add(image.split(":", 1)[0])
    assert deployed, "the arm's stacks declare no BunkerWeb image — the parser broke, not the stack"

    retagged = _retagged_images()
    # bunkerweb-ui only ships on a `ui` run, and the workflow gates that step on inputs.TYPE, so
    # it is checked the same way the other arms' UI pull is: presence of the name anywhere in a
    # step that names Swarm.
    missing = deployed - retagged
    assert not missing, f"the Swarm arm deploys {sorted(missing)} but the workflow never retags them for it"


# ------------------------------------------------------------------ 4. the enrolment list


def _specs_naming_swarm() -> set:
    named = set()
    for directory in ("core", "ui", "api"):
        for path in sorted((ROOT / "tests" / directory).glob("*.yml")):
            spec = safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                continue
            declared = spec.get("integrations")
            if isinstance(declared, list) and any(str(entry).split(";")[0] == "Swarm" for entry in declared):
                named.add(f"{directory}/{path.stem}")
    return named


def test_swarm_is_opt_in_so_all_cannot_enrol_the_catalogue():
    """`integrations: "all"` must not reach Swarm. Without this gate, giving the Swarm rows a
    runner in integrations.yml enrols every `all` spec at once."""
    source = PARSE.read_text(encoding="utf-8")
    assert re.search(r'^OPT_IN_ONLY = \([^)]*"Swarm"', source, re.MULTILINE), "tests/parse.py no longer marks Swarm opt-in"
    all_branch = source.partition('if isinstance(test_integrations, list) and "all" in test_integrations:')[2]
    all_branch = all_branch.partition("if isinstance(test_integrations, list):")[0]
    assert all_branch, "the `all` expansion in tests/parse.py moved — this guard is now checking nothing"
    assert "OPT_IN_ONLY" in all_branch, "the `all` expansion no longer skips opt-in-only arms, so it enrols Swarm"


def test_all_stays_composable_with_an_opt_in_arm():
    """`integrations: ["all", "Swarm"]` is how an `all` spec joins the arm without freezing its
    list of arms. Normalising the bare string into a list is what makes that spelling work; drop
    it and the only way to opt an `all` spec in is to enumerate every arm by hand, which then
    silently skips the next arm anyone adds."""
    source = PARSE.read_text(encoding="utf-8")
    assert (
        'if test_integrations == "all":\n                test_integrations = ["all"]' in source
    ), 'tests/parse.py no longer normalises the bare `all` into a list, so ["all", "Swarm"] cannot work'
    # And the expansion must not swallow the rest of the list on its way out.
    assert (
        'test_integrations = [entry for entry in test_integrations if entry != "all"]' in source
    ), "the `all` expansion no longer hands the remaining entries to the explicit branch"


def test_only_the_specs_that_were_actually_run_are_enrolled():
    """The arm runs what someone has executed on a real swarm, not what is eligible. Adding a name
    to a spec's `integrations:` list without adding it here — or the reverse — is the mistake."""
    assert _specs_naming_swarm() == EXPECTED_SWARM_SPECS, (
        "the set of specs opted in to the Swarm arm changed; run them on a real single-node swarm "
        "and update EXPECTED_SWARM_SPECS, do not widen one side alone"
    )


@pytest.mark.parametrize("stack", ARM_STACKS, ids=lambda path: path.name)
def test_the_arm_never_declares_a_network_it_does_not_pre_create(stack: Path):
    """A Swarm service cannot join a local bridge — the daemon answers "network X not found" — so
    every network the arm's stack names has to be one `swarm_ensure_networks` creates as an
    attachable overlay, and it has to be declared external so the stack does not make its own."""
    utils = (ROOT / "tests" / "scripts" / "utils.sh").read_text(encoding="utf-8")
    created = set(re.findall(r'"([\w-]+):[\d./]*"', utils.partition("SWARM_NETWORKS=(")[2].partition(")")[0]))
    assert created, "SWARM_NETWORKS disappeared from tests/scripts/utils.sh"

    declared = safe_load(stack.read_text(encoding="utf-8")).get("networks") or {}
    for name, definition in declared.items():
        assert (definition or {}).get("external") is True, f"{stack.name} declares {name} inline; Swarm needs it pre-created"
        assert name in created, f"{stack.name} uses {name}, which swarm_ensure_networks does not create"


# ------------------------------------------------------------------ 5. the host-state guard

UTILS = ROOT / "tests" / "scripts" / "utils.sh"

# A fake `docker` driven by two files in the work directory: `state` is what `docker info` reports,
# and every invocation is appended to `calls`. Enough to observe whether the arm initialised a
# swarm and whether it recorded having done so.
FAKE_DOCKER = """#!/bin/bash
echo "$*" >> "$WORK/calls"
case "$1 $2" in
  "info --format")
    case "$3" in
      *LocalNodeState*) cat "$WORK/state" ;;
      *) echo "" ;;
    esac ;;
  "swarm init") echo active > "$WORK/state" ;;
  "node ls") echo "nodeid" ;;
  "node inspect") cat "$WORK/label" 2>/dev/null || echo "" ;;
  "node update") echo true > "$WORK/label" ;;
esac
exit 0
"""


def _swarm_host_shell() -> str:
    """The constants plus the two host-state functions, lifted out of utils.sh so they can be run
    without sourcing the whole file (which validates arguments and needs redis at load time)."""
    source = UTILS.read_text(encoding="utf-8")
    block = re.search(r"^SWARM_STACK=.*?^SWARM_NETWORKS=\([^)]*\)", source, re.S | re.M)
    assert block, "the SWARM_* constants moved in utils.sh"
    out = [block.group()]
    for name in ("swarm_forget_markers", "swarm_ensure_host"):
        found = re.search(rf"^function {name}\(\) \{{.*?^\}}", source, re.S | re.M)
        assert found, f"{name} is gone from utils.sh"
        out.append(found.group())
    return "\n".join(out)


def _run_host_guard(tmp_path: Path, initial_state: str, calls: str) -> tuple:
    work = tmp_path / "work"
    work.mkdir()
    (work / "state").write_text(initial_state)
    binonly = tmp_path / "bin"
    binonly.mkdir()
    fake = binonly / "docker"
    fake.write_text(FAKE_DOCKER)
    fake.chmod(0o755)

    script = "\n".join(
        [
            "set -u",
            "log() { :; }",
            # Markers under the work directory so the test never touches the real /tmp ones.
            _swarm_host_shell()
            .replace('SWARM_INIT_MARKER="/tmp/bw_swarm_initialised"', 'SWARM_INIT_MARKER="$WORK/init"')
            .replace('SWARM_LABEL_MARKER="/tmp/bw_swarm_labelled"', 'SWARM_LABEL_MARKER="$WORK/label-marker"'),
            calls,
        ]
    )
    import os
    import subprocess

    env = dict(os.environ, WORK=str(work), PATH=f"{binonly}:{os.environ['PATH']}")
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    return work, (work / "calls").read_text(encoding="utf-8") if (work / "calls").exists() else ""


def test_a_swarm_this_arm_created_is_still_marked_after_the_second_ensure(tmp_path: Path):
    """`swarm_ensure_host` runs at least twice per run — build.sh, then start.sh, and again after
    every full_clean. By the second call the daemon IS in a swarm, and an `else` branch that
    cleared the marker there would erase the record that says WE created it: teardown would then
    skip `swarm leave` and the developer keeps a swarm they never asked for."""
    work, calls = _run_host_guard(tmp_path, "inactive\n", "swarm_forget_markers\nswarm_ensure_host\nswarm_ensure_host\n")
    assert "swarm init --advertise-addr 127.0.0.1" in calls, calls
    assert calls.count("swarm init") == 1, f"initialised twice: {calls}"
    assert (work / "init").exists(), "the marker was cleared by the second ensure — the swarm would never be left"
    assert (work / "label-marker").exists(), "the node-label marker was cleared by the second ensure"


def test_a_pre_existing_swarm_is_never_marked_and_so_never_left(tmp_path: Path):
    """The half that protects a user's daemon: if it was already a manager, this arm must record
    nothing, so `swarm_host_restore` cannot run `swarm leave --force` on it."""
    work, calls = _run_host_guard(tmp_path, "active\n", "swarm_forget_markers\nswarm_ensure_host\n")
    assert "swarm init" not in calls, f"initialised a swarm that already existed: {calls}"
    assert not (work / "init").exists(), "a pre-existing swarm was marked as ours; teardown would destroy it"


def test_build_sh_clears_the_markers_before_the_first_ensure():
    """The reset has to happen once per run and outside swarm_ensure_host. If it moved back
    inside, the first test above would still pass on its own and the guard would be gone."""
    build = (ROOT / "tests" / "scripts" / "build.sh").read_text(encoding="utf-8")
    # Invocations, not mentions: the comment above the reset names swarm_ensure_host, so a bare
    # `index()` would compare a comment against a call.
    calls = [
        line.strip().split()[0]
        for line in build.splitlines()
        if line.strip().startswith(("swarm_forget_markers", "swarm_ensure_host", "swarm_ensure_networks"))
    ]
    assert "swarm_forget_markers" in calls, "build.sh no longer clears the markers at the start of a run"
    assert calls.index("swarm_forget_markers") < calls.index("swarm_ensure_host"), f"the reset runs after the first ensure: {calls}"
    host = re.search(r"^function swarm_ensure_host\(\) \{.*?^\}", UTILS.read_text(encoding="utf-8"), re.S | re.M).group()
    assert "rm -f" not in host, "swarm_ensure_host clears a marker again; that is the defect this pins"
