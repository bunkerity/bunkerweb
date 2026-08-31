#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Turn the harness's `/tmp/services.yml` into a Swarm stack fragment.

`generate.py` writes the application layer as a compose file with CONTAINER labels, which is what
the Docker autoconf controller reads. `SwarmController` reads SERVICE labels
(`service.attrs["Spec"]["Labels"]`, controllers/SwarmController.py) and never looks at a
container, so the same file deployed unchanged discovers nothing at all — the stack comes up, the
spec's `bunkerweb.SERVER_NAME` never reaches the control plane, and every assertion fails on a
default server. Moving the labels is the one structural difference between the Swarm arm and the
Autoconf arm; everything else the two arms do is the same.

Doing it here rather than in `generate.py` keeps the conversion in one place and leaves the
Docker/Autoconf path byte-identical: `generate.py` has no idea an arm rewrites its output.

Also handles what `docker stack deploy` cannot take from a compose file:

* `container_name`, `restart`, `depends_on`, `links` and `profiles` are silently IGNORED by
  `docker stack deploy` — dropped here so the emitted file says what will actually happen;
* `ipv4_address` is REJECTED ("Invalid ... networks.bw-services.ipv4_address"): Swarm allocates
  task addresses itself. The harness pins app1 at 192.168.0.254 and `tests/misc/conf/dnsmasq.hosts`
  hardcodes `192.168.0.254 app1.bw-services`, so dropping the address alone would leave that name
  pointing at nothing. Every service therefore gains `<name>` and `<name>.bw-services` as network
  ALIASES, and `build.sh` drops the matching static rows from dnsmasq.hosts for this arm so
  dnsmasq forwards them to Docker's own resolver (`server=127.0.0.11` in dnsmasq.conf) instead of
  answering with a stale address.
"""

from pathlib import Path
from sys import argv

from yaml import safe_dump, safe_load

# Keys `docker stack deploy` ignores outright. Kept as a named set rather than deleted inline so
# the reason above stays attached to the list.
IGNORED_BY_STACK_DEPLOY = ("container_name", "restart", "depends_on", "links", "profiles")

# The networks the Swarm arm pre-creates as attachable overlays (tests/scripts/start.sh). Anything
# a spec's `services:` block declares beyond these is left alone and will be created stack-scoped.
HARNESS_NETWORKS = ("bw-universe", "bw-services", "bw-db", "bw-docker")


def convert(compose: dict) -> dict:
    """Return `compose` rewritten as a Swarm stack fragment."""
    stack = {"services": {}}

    for name, service in (compose.get("services") or {}).items():
        service = dict(service)

        for key in IGNORED_BY_STACK_DEPLOY:
            service.pop(key, None)

        deploy = dict(service.get("deploy") or {})

        labels = service.get("labels") or {}
        if isinstance(labels, list):
            labels = dict(entry.split("=", 1) for entry in labels if "=" in entry)
        if labels:
            # SERVICE labels for the controller. The container labels are deliberately KEPT too:
            # `bunkerweb.NAMESPACE` on the container is what stops a Docker-autoconf controller
            # elsewhere on the daemon from adopting this container as one of its own.
            merged = dict(deploy.get("labels") or {})
            merged.update(labels)
            deploy["labels"] = merged

        service["deploy"] = deploy

        networks = service.get("networks")
        if isinstance(networks, dict):
            converted = {}
            for network, options in networks.items():
                options = dict(options or {})
                options.pop("ipv4_address", None)
                options.pop("ipv6_address", None)
                aliases = list(options.get("aliases") or [])
                for alias in (name, f"{name}.{network}"):
                    if alias not in aliases:
                        aliases.append(alias)
                options["aliases"] = aliases
                converted[network] = options
            service["networks"] = converted
        elif isinstance(networks, list):
            service["networks"] = {network: {"aliases": [name, f"{name}.{network}"]} for network in networks}

        stack["services"][name] = service

    declared = set()
    for service in stack["services"].values():
        declared.update(service.get("networks") or {})

    # Only the harness networks are external — start.sh created them. A spec that invents its own
    # network keeps whatever the compose file said about it.
    stack["networks"] = {}
    for network in sorted(declared):
        if network in HARNESS_NETWORKS:
            stack["networks"][network] = {"external": True}
        else:
            stack["networks"][network] = (compose.get("networks") or {}).get(network) or {}

    volumes = compose.get("volumes")
    if volumes:
        stack["volumes"] = volumes

    return stack


def main(source: str, destination: str) -> int:
    compose = safe_load(Path(source).read_text())
    if not compose or not compose.get("services"):
        print(f"swarm-services: {source} declares no service, nothing to convert")
        return 1
    Path(destination).write_text(safe_dump(convert(compose), indent=2, sort_keys=False))
    print(f"swarm-services: wrote {destination} ({len(compose['services'])} service(s))")
    return 0


def _self_check() -> None:
    """`python3 tests/scripts/swarm-services.py --self-check` — the smallest thing that fails if
    the label move, the static-address drop or the alias synthesis breaks."""
    out = convert(
        {
            "services": {
                "app1": {
                    "image": "nginx",
                    "container_name": "app1",
                    "restart": "unless-stopped",
                    "labels": {"bunkerweb.SERVER_NAME": "www.example.com"},
                    "networks": {"bw-services": {"ipv4_address": "192.168.0.254"}},
                },
                "extra": {"image": "busybox", "networks": ["bw-universe", "private"]},
            },
            "networks": {"bw-services": {"name": "bw-services"}, "private": {"driver": "bridge"}},
        }
    )
    app1 = out["services"]["app1"]
    assert app1["deploy"]["labels"] == {"bunkerweb.SERVER_NAME": "www.example.com"}, app1["deploy"]
    assert app1["labels"] == {"bunkerweb.SERVER_NAME": "www.example.com"}, "container labels must survive"
    assert "container_name" not in app1 and "restart" not in app1, app1
    assert "ipv4_address" not in app1["networks"]["bw-services"], app1["networks"]
    assert app1["networks"]["bw-services"]["aliases"] == ["app1", "app1.bw-services"], app1["networks"]
    extra = out["services"]["extra"]
    assert extra["networks"]["private"]["aliases"] == ["extra", "extra.private"], extra["networks"]
    assert out["networks"]["bw-services"] == {"external": True}, out["networks"]
    assert out["networks"]["private"] == {"driver": "bridge"}, out["networks"]
    print("swarm-services: self-check passed")


if __name__ == "__main__":
    if "--self-check" in argv:
        _self_check()
        raise SystemExit(0)
    raise SystemExit(main(argv[1] if len(argv) > 1 else "/tmp/services.yml", argv[2] if len(argv) > 2 else "/tmp/swarm-services.yml"))
