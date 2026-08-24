"""The Docker arm must hold every image the `swarm*` specs deploy.

`tests/core/swarm{,-secrets,-example}/test.sh` all `docker stack deploy` one of
`tests/swarm/stack*.yml` with `--resolve-image never`, so Swarm never reaches a registry: an
image the job did not pull is simply absent, the task is rejected with

    "No such image: bunkerity/bunkerweb-autoconf:tests"

and the stack never converges. That is how all three swarm specs died on the Docker arm of run
32508782608 -- `integration-tests.yml` pulled bw-autoconf for Autoconf and Kubernetes only,
while the swarm stacks (which run an autoconf) are driven from Docker.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "integration-tests.yml"
STACKS = sorted((ROOT / "tests" / "swarm").glob("stack*.yml"))

# `- name: …` then its `if:`/`run:` lines, up to the next step at the same indentation.
STEP = re.compile(r"^      - name: (?P<name>.+)\n(?P<body>(?:^        .*\n|^          .*\n)*)", re.MULTILINE)
# `docker tag ghcr.io/…:${{ inputs.RELEASE }} bunkerity/<image>:tests` -- the source tag
# carries a `${{ … }}` expression with spaces in it, so the hop cannot be `\S+`.
RETAG = re.compile(r"docker tag .*? (?P<image>bunkerity/[\w-]+):tests")


def _retag_steps():
    """image -> the `if:` expression of the step that puts it on the runner."""
    steps = {}
    for step in STEP.finditer(WORKFLOW.read_text(encoding="utf-8")):
        body = step.group("body")
        retag = RETAG.search(body)
        if not retag:
            continue
        condition = re.search(r"^        if: (?P<expr>.+)$", body, re.MULTILINE)
        steps[retag.group("image")] = condition.group("expr") if condition else ""
    return steps


RETAG_STEPS = _retag_steps()


def test_the_workflow_still_retags_images():
    """A parser that matched nothing would make every assertion below vacuously true."""
    assert len(RETAG_STEPS) >= 6, RETAG_STEPS


def test_there_are_swarm_stacks_to_check():
    assert len(STACKS) >= 2


@pytest.mark.parametrize("stack", STACKS, ids=lambda path: path.name)
def test_the_docker_arm_pulls_every_bunkerweb_image_the_swarm_stacks_deploy(stack):
    images = set(re.findall(r"^\s+image: (bunkerity/[\w-]+):tests$", stack.read_text(encoding="utf-8"), re.MULTILINE))
    assert images, f"{stack.name} references no bunkerity image any more -- has it moved?"

    for image in sorted(images):
        assert image in RETAG_STEPS, f"{image} is never pulled by {WORKFLOW.name}"
        condition = RETAG_STEPS[image]
        assert "'Docker'" in condition, f"{image} is pulled, but never on the Docker arm that runs the swarm specs: {condition}"


def test_the_autoconf_image_reaches_the_docker_arm_through_the_swarm_gate():
    """The Docker half of that condition is the whole point of the fix, and it is scoped.

    Asserting only that 'Docker' appears would survive both mutations that matter: dropping the
    `startsWith` (every one of the ~57 Docker jobs then pulls an image 54 of them never use) and
    dropping the Docker term (the swarm jobs go back to "No such image").
    """
    condition = RETAG_STEPS["bunkerity/bunkerweb-autoconf"]
    assert "needs.setup.outputs.integration == 'Docker'" in condition
    assert "startsWith(needs.setup.outputs.test, 'swarm')" in condition
    assert "&&" in condition, f"the Docker term is not ANDed with the swarm gate: {condition}"


@pytest.mark.parametrize("spec", ("swarm", "swarm-secrets", "swarm-example"), ids=str)
def test_every_swarm_spec_deploys_one_of_those_stacks(spec):
    """Keeps the test above honest: it only protects the stacks the specs actually deploy."""
    script = (ROOT / "tests" / "core" / spec / "test.sh").read_text(encoding="utf-8")
    assert any(stack.name in script for stack in STACKS), f"{spec} no longer deploys a tests/swarm/stack*.yml"
