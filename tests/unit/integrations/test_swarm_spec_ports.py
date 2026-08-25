"""The swarm stacks publish host ports on a daemon the compose harness is already using.

`tests/core/swarm*/test.sh` deploy `tests/swarm/stack*.yml` on the SAME daemon that runs the
Docker arm's own stack, in host mode ("mode: host", so the routing mesh does not source-NAT the
client away). A host port both sides want is not a conflict Swarm resolves: the task is rejected
over and over with

    starting container failed: ... Bind for 0.0.0.0:8080 failed: port is already allocated

and `docker stack deploy` never converges. That is exactly how `Docker;swarm` died in run
32733647372 -- `stack.yml` published 8080, which `tests/misc/docker/services.yml` gives to app1 --
while `swarm-secrets` (8081) and `swarm-example` (8082, rewritten at deploy time) stayed green.

The file's own header comment claims which ports are free; these tests are what keeps that claim
true when either side moves.
"""

import re
from pathlib import Path

import pytest
from yaml import safe_load

ROOT = Path(__file__).resolve().parents[3]
STACKS = sorted((ROOT / "tests" / "swarm").glob("stack*.yml"))
# What the Docker arm itself brings up: the framework's stack plus the shared services (app1 and
# friends) build.sh starts beside it.
HARNESS = sorted((ROOT / "tests" / "docker").glob("docker-compose.*.yml")) + sorted((ROOT / "tests" / "misc" / "docker").glob("*.yml"))


def _host_port(value):
    """The literal host port, or None when the file leaves it to the environment.

    Several harness files interpolate (`"127.0.0.1:${TESTS_REDIS_PORT:-6390}:6379"`), so the
    default inside `${…:-N}` is the port a run actually binds unless someone overrides it.
    """
    if value is None:
        return None
    text = str(value)
    default = re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*:-(\d+)\}", text)
    if default:
        return int(default.group(1))
    return int(text) if text.isdigit() else None


def _published(compose):
    """host port -> service, for both the short `"127.0.0.1:8080:8080"` and long forms."""
    ports = {}
    for service, config in (safe_load(compose.read_text(encoding="utf-8")).get("services") or {}).items():
        for entry in config.get("ports") or []:
            if isinstance(entry, dict):
                published = entry.get("published")
            else:
                # "80:80", "127.0.0.1:5001:5000", "443:443/udp" -- the host port is the
                # second-to-last colon-separated field, and only when there IS one.
                fields = str(entry).split("/")[0].split(":")
                published = fields[-2] if len(fields) > 1 else None
            published = _host_port(published)
            if published is not None:
                ports.setdefault(published, []).append(f"{compose.name}:{service}")
    return ports


def test_there_are_stacks_and_a_harness_to_compare():
    """Two globs that matched nothing would make every assertion below vacuously true."""
    assert len(STACKS) >= 2
    assert len(HARNESS) > 5
    assert any(_published(compose) for compose in HARNESS)


@pytest.mark.parametrize("stack", STACKS, ids=lambda s: s.name)
def test_a_stack_publishes_nothing_the_harness_already_holds(stack):
    mine = _published(stack)
    for compose in HARNESS:
        for port, owners in _published(compose).items():
            assert port not in mine, f"{stack.name} publishes {port}, already bound by {', '.join(owners)}"


def test_the_stacks_do_not_collide_with_each_other():
    """They are separate specs today, but they run on one daemon and a `swarm*` job may overlap."""
    seen = {}
    for stack in STACKS:
        for port in _published(stack):
            assert port not in seen, f"{stack.name} and {seen[port]} both publish {port}"
            seen[port] = stack.name


def test_swarm_example_still_rewrites_the_ports_it_thinks_it_does():
    """swarm-example deploys stack.yml through `sed -e "s/published: <n>/published: <its own>/"`.

    A pattern that stops matching is silent: the copy keeps stack.yml's ports, the example stack
    binds them, and it collides with nothing until the two specs run close enough together -- while
    its own assertions dial the port it never moved.
    """
    script = (ROOT / "tests" / "core" / "swarm-example" / "test.sh").read_text(encoding="utf-8")
    stack = (ROOT / "tests" / "swarm" / "stack.yml").read_text(encoding="utf-8")

    rewritten = [int(port) for port in re.findall(r"s/published: (\d+)/published:", script)]

    assert rewritten, "swarm-example no longer rewrites any port -- this guard would pass vacuously"
    for port in rewritten:
        assert f"published: {port}" in stack, f"swarm-example rewrites published {port}, which stack.yml no longer uses"
