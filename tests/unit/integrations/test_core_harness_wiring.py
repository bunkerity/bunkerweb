"""Two harness facts the All-in-one arm of run 32508782608 proved were not holding.

* `restart_stack()` redeploys `/tmp/services.yml` in the Docker/Autoconf branch and in the Linux
  branch, and did not in the All-in-one one. An action that declares `services:` therefore ran
  against containers nothing had started -- `antibot;capjs` reached the antibot page and failed
  on an xpath because a Cap backend that did not exist could not validate its token.
* `before/reversescan.sh` exported the container NAME as the address the spec puts in
  `X-Forwarded-For`. nginx's realip module ignores a value that is not an IP, so `remote_addr`
  stayed whatever Docker's plumbing produced -- the gateway of the instance's primary bridge --
  and the scan hit the runner host instead of custom-api.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "tests" / "scripts" / "utils.sh"
BEFORE = ROOT / "tests" / "scripts" / "before" / "reversescan.sh"
CUSTOM_API = ROOT / "tests" / "misc" / "docker" / "custom-api.yml"
CUSTOM_API_DOCKERFILE = ROOT / "tests" / "misc" / "api" / "Dockerfile"
SPEC = ROOT / "tests" / "core" / "reversescan.yml"

# The integration chain inside `restart_stack`: one `if`, two `elif`s and a trailing `else` that
# carries Linux/FreeBSD. Kubernetes is out of the check below: it applies manifests through
# kubectl, not compose.
CHAIN_HEAD = 'if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then'
COMPOSE_BRANCHES = ("Docker/Autoconf", "All-in-one", "else (Linux)")


def _restart_stack_body():
    text = UTILS.read_text(encoding="utf-8")
    start = text.index("function restart_stack () {")
    end = text.index("\nfunction ", start + 1)
    return text[start:end]


def _branches():
    body = _restart_stack_body()
    lines = body.splitlines(keepends=True)
    head = next(i for i, line in enumerate(lines) if line.strip() == CHAIN_HEAD)

    cuts = [(head, "Docker/Autoconf")]
    for i in range(head + 1, len(lines)):
        line = lines[i]
        if re.match(r'^    elif \[ "\$integration" == "(?P<name>[\w-]+)" \] ; then', line):
            cuts.append((i, re.search(r'"(?P<name>[\w-]+)" \] ; then', line).group("name")))
        elif line.rstrip() == "    else":
            cuts.append((i, "else (Linux)"))
            break

    out = {}
    for (pos, name), nxt in zip(cuts, cuts[1:] + [(len(lines), None)]):
        end = nxt[0]
        out[name] = "".join(lines[pos:end])
    return out


BRANCHES = _branches()


def test_the_branches_are_still_found():
    """A parser that matched nothing would make every assertion below vacuously true."""
    assert set(COMPOSE_BRANCHES) <= set(BRANCHES), sorted(BRANCHES)
    assert "Kubernetes" in BRANCHES, "the chain no longer looks like the one this test splits"


@pytest.mark.parametrize("branch_name", COMPOSE_BRANCHES, ids=str)
def test_every_compose_branch_redeploys_the_dockerized_services(branch_name):
    branch = BRANCHES[branch_name]
    assert "/tmp/services.yml" in branch, f"the {branch_name} branch of restart_stack ignores the action's services:"
    assert "restart_services" in branch, f"the {branch_name} branch redeploys services unconditionally or never"
    assert "docker compose -f /tmp/services.yml up -d" in branch


def test_the_reverse_scan_client_address_is_an_ip_literal():
    """A bare container name is silently dropped by realip; the spec then scans the wrong host."""
    match = re.search(r'^CUSTOM_API_IP="(?P<value>[^"]+)"', BEFORE.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "before/reversescan.sh no longer sets CUSTOM_API_IP"
    value = match.group("value")
    assert re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", value), f"CUSTOM_API_IP={value!r} is not an IP literal"

    # …and the right one: custom-api pins its address in its own compose file.
    pinned = re.search(r"ipv4_address:\s*(?P<ip>[\d.]+)", CUSTOM_API.read_text(encoding="utf-8"))
    assert pinned and pinned.group("ip") == value, f"CUSTOM_API_IP={value} is not custom-api's address"


def test_the_scanned_ports_include_the_one_custom_api_listens_on():
    """Otherwise `activated` asserts a 403 that nothing can produce."""
    listen = re.search(r"--port\D+(?P<port>\d+)", CUSTOM_API_DOCKERFILE.read_text(encoding="utf-8"))
    assert listen, "the custom-api image no longer states its port"

    plugin = ROOT / "src" / "common" / "core" / "reversescan" / "plugin.json"
    import json

    default_ports = json.loads(plugin.read_text(encoding="utf-8"))["settings"]["REVERSE_SCAN_PORTS"]["default"].split()
    assert listen.group("port") in default_ports, f"custom-api's port is not in REVERSE_SCAN_PORTS ({default_ports})"

    # The spec relies on the default list for `activated` (it only overrides it for tweaked_ports).
    assert "REVERSE_SCAN_PORTS" not in SPEC.read_text(encoding="utf-8").split("tweaked_ports")[0]
