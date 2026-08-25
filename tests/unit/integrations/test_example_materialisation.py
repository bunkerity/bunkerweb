"""The Docker example stacks must be materialised against the framework's own networks.

An example ships the whole stack and declares `bw-universe` / `bw-services` itself, which is
right for someone copying it and wrong under the harness: `build.sh` has already created both
(dnsmasq, redis and php-fpm sit on them) and compose *recreates* a live network whose
declaration differs from the one in the file it is deploying. `bw-services` always differs --
`tests/misc/docker/dnsmasq.yml` pins `192.168.0.0/24`, no example states a subnet -- so the
removal ran, hit dnsmasq's endpoint and every `example-*` job died on

    error while removing network: network bw-services has active endpoints

before a single request was sent. `tests/utils/example.py` rewrites the two entries to
`external: true` in the /tmp copy; these tests pin that rewrite and its blast radius.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "utils"))

from example import SHARED_NETWORKS, SHARED_SERVICES_SUBNET, _externalise_shared_networks, _widen_api_whitelist  # noqa: E402

LOGGER = logging.getLogger("test-example-materialisation")

_CACHE = {}


def _compose_config(compose):
    """Parse with compose itself -- the unit venv has no YAML reader, and this is what runs it."""
    if compose not in _CACHE:
        result = subprocess.run(
            ["docker", "compose", "-f", "-", "config", "--no-interpolate", "--format", "json"],
            cwd=ROOT,
            input=compose,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        _CACHE[compose] = json.loads(result.stdout)
    return _CACHE[compose]


def _examples():
    for compose in sorted((ROOT / "examples").glob("*/docker-compose.yml")):
        # bigbluebutton ships a prose snippet with `...` placeholders: documentation, not a
        # deployable stack, and no spec references it.
        if "\n  ...\n" in compose.read_text(encoding="utf-8"):
            continue
        yield compose


COMPOSES = list(_examples())


def test_there_are_examples_to_check():
    """A glob that silently matched nothing would make every assertion below vacuously true."""
    assert len(COMPOSES) > 20


@pytest.mark.parametrize("compose", COMPOSES, ids=lambda c: c.parent.name)
def test_the_shared_networks_become_external(compose):
    source = compose.read_text(encoding="utf-8")
    declared = _compose_config(source).get("networks") or {}
    rewritten = _compose_config(_externalise_shared_networks(source, LOGGER)).get("networks") or {}

    for network in SHARED_NETWORKS:
        if network not in declared:
            continue
        assert rewritten[network].get("external") is True, f"{network} is still managed by the example's own project"
        assert rewritten[network].get("name") == network
        assert not rewritten[network].get("ipam"), f"{network} still carries an ipam block compose would compare against"


@pytest.mark.parametrize("compose", COMPOSES, ids=lambda c: c.parent.name)
def test_nothing_but_those_two_networks_moves(compose):
    """The rewrite is a scalpel: an over-greedy pattern would eat the next top-level key."""
    source = compose.read_text(encoding="utf-8")
    before = _compose_config(source)
    after = _compose_config(_externalise_shared_networks(source, LOGGER))

    assert before.get("services") == after.get("services")
    assert before.get("volumes") == after.get("volumes")
    assert set(before) == set(after), "a top-level key was swallowed"

    others = {name: cfg for name, cfg in (before.get("networks") or {}).items() if name not in SHARED_NETWORKS}
    still = {name: cfg for name, cfg in (after.get("networks") or {}).items() if name not in SHARED_NETWORKS}
    assert others == still


# --- the call site, not just the function -------------------------------------------------
# Everything above exercises _externalise_shared_networks directly, so deleting its call in
# materialise() leaves all of it green. These three go through the entry point and read the file
# that start.sh actually deploys.

WIRING = "cors"  # ships docker-compose.yml, autoconf.yml and variables.env


def _materialise(tmp_path, integration, name=WIRING):
    import example

    stack_dir, marker = example.STACK_DIR, example.STACK_MARKER
    example.STACK_DIR = tmp_path / "example-stack"
    example.STACK_MARKER = tmp_path / "example_stack.txt"
    try:
        return example.materialise(LOGGER, name, integration, "tests").read_text(encoding="utf-8")
    finally:
        example.STACK_DIR, example.STACK_MARKER = stack_dir, marker


def test_the_docker_entry_point_writes_external_networks(tmp_path):
    written = _materialise(tmp_path, "Docker")
    assert "external: true" in written
    for network in SHARED_NETWORKS:
        assert _compose_config(written)["networks"][network].get("external") is True

    # The example itself is documentation: only the /tmp copy is rewritten.
    source = (ROOT / "examples" / WIRING / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ipam:" in source and "external: true" not in source


def test_a_non_docker_entry_point_gets_no_rewrite(tmp_path):
    """Linux stands in for every non-Docker branch: an env file has no networks to externalise.

    Autoconf would be the other half, but materialise() round-trips YAML on that path and the
    unit venv has no PyYAML -- and those examples' autoconf.yml files already ship
    `external: true`, so there is nothing the rewrite could change there anyway.
    """
    written = _materialise(tmp_path, "Linux")
    assert "external: true" not in written
    assert "networks" not in written
    assert "USE_BUNKERNET=no" in written  # the Linux branch still ran


class _Capture(logging.Handler):
    """Not caplog: importing any product module runs logger.py's basicConfig(handlers=[…]),
    which replaces the root handlers pytest's fixture relies on, and caplog.records then comes
    back empty depending on what else ran in the session. A handler on the logger under test
    does not care."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _warnings_from(content):
    capture = _Capture()
    LOGGER.addHandler(capture)
    previous = LOGGER.level
    LOGGER.setLevel(logging.DEBUG)
    try:
        out = _externalise_shared_networks(content, LOGGER)
    finally:
        LOGGER.removeHandler(capture)
        LOGGER.setLevel(previous)
    # levelno, not levelname: importing any product module runs logger.py, which calls
    # addLevelName(WARNING, "⚠️ ") -- so `r.levelname == "WARNING"` silently matches nothing
    # depending on what else the session imported.
    return out, [r for r in capture.records if r.levelno == logging.WARNING]


def test_a_network_it_cannot_rewrite_is_not_passed_over_in_silence():
    """count == 0 reads the same whether the example does not use the network or the rewrite
    missed it. Only the second is a bug, and it is the one that brings the stack-up failure back."""
    flow_style = "services:\n  app:\n    networks: [bw-services]\nnetworks:\n  bw-services: {name: bw-services}\n"

    out, warnings = _warnings_from(flow_style)

    assert out == flow_style, "nothing was rewritten, which is the premise of this test"
    assert any("bw-services" in r.getMessage() for r in warnings)


def test_an_unused_network_stays_quiet():
    """The other half: no warning when the example simply does not use it (php-multisite)."""
    _, warnings = _warnings_from("services:\n  app: {}\nnetworks:\n  other: {}\n")

    assert not warnings


def test_the_framework_owns_the_networks_it_hands_over():
    """`external: true` is a promise that something else created them -- keep that true."""
    dnsmasq = _compose_config((ROOT / "tests" / "misc" / "docker" / "dnsmasq.yml").read_text(encoding="utf-8"))
    assert set(SHARED_NETWORKS) <= set(dnsmasq.get("networks") or {})


# --- the whitelist that comes with those networks ------------------------------------------
# Externalising `bw-services` moves the copy onto the framework's 192.168.0.0/24, and the
# gateway of that bridge -- 192.168.0.1 -- is what BunkerWeb sees when the host calls a
# published instance API port. No example whitelists it (they cover Docker's default pool,
# 172.16.0.0/12), and an unwhitelisted caller gets its connection closed with no response, so
# `example-stream-multisite` timed out for 90s on a bare RemoteDisconnected in run 32733647372.

API_EXAMPLE = "stream-multisite"  # the one example that probes the instance API from the host


def _whitelists(content):
    return [line.split(":", 1)[1].strip() for line in content.splitlines() if line.strip().startswith("API_WHITELIST_IP:")]


def test_the_materialised_docker_copy_trusts_the_framework_gateway(tmp_path):
    written = _materialise(tmp_path, "Docker", API_EXAMPLE)
    values = _whitelists(written)

    assert values, f"{API_EXAMPLE} no longer sets API_WHITELIST_IP -- this guard would pass vacuously"
    for value in values:
        assert SHARED_SERVICES_SUBNET in value, f"the host cannot reach the instance API through {SHARED_SERVICES_SUBNET}.1"

    # The example itself is documentation, and its reader is not on the framework's network.
    source = (ROOT / "examples" / API_EXAMPLE / "docker-compose.yml").read_text(encoding="utf-8")
    assert SHARED_SERVICES_SUBNET not in source


def test_widening_twice_adds_it_once():
    """materialise() copies the example fresh every action, but a second pass must not accumulate."""
    once = _widen_api_whitelist('    API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"\n', LOGGER)
    twice = _widen_api_whitelist(once, LOGGER)

    assert once.count(SHARED_SERVICES_SUBNET) == 1
    assert twice == once


def test_widening_leaves_everything_else_alone():
    """A greedy pattern here would rewrite API_WHITELIST_IPS (the API's own, plural) too."""
    content = 'x-bw-env: &bw-env\n  API_WHITELIST_IP: "127.0.0.0/8"\n  API_TOKEN: "secret"\nservices:\n  bw-api:\n    environment:\n      API_WHITELIST_IPS: "127.0.0.0/8"\n'

    out = _widen_api_whitelist(content, LOGGER)

    assert f'API_WHITELIST_IP: "127.0.0.0/8 {SHARED_SERVICES_SUBNET}"' in out
    assert 'API_WHITELIST_IPS: "127.0.0.0/8"' in out
    assert 'API_TOKEN: "secret"' in out


def test_the_framework_still_pins_that_subnet():
    """The constant is a copy of dnsmasq.yml's ipam block; a silent drift there re-breaks the API."""
    dnsmasq = _compose_config((ROOT / "tests" / "misc" / "docker" / "dnsmasq.yml").read_text(encoding="utf-8"))
    subnets = [c.get("subnet") for c in ((dnsmasq["networks"]["bw-services"].get("ipam") or {}).get("config") or [])]

    assert SHARED_SERVICES_SUBNET in subnets
