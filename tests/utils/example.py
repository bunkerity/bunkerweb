#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Materialise an examples/ stack so a spec can assert against it.

Examples are documentation: they pin released image tags and are meant to be copied
as-is. A test run needs the images built from this commit and a few settings that keep
a CI run from touching the outside world, so the example is copied to /tmp and the copy
is rewritten. The example itself is never modified.
"""

from logging import Logger
from os import sep
from pathlib import Path
from re import MULTILINE, sub
from shutil import copytree, rmtree
from subprocess import run

from yaml import safe_dump, safe_load

# Where the materialised stack lands, and the file start.sh reads to find it.
STACK_DIR = Path(sep, "tmp", "example-stack")
STACK_MARKER = Path(sep, "tmp", "example_stack.txt")

# Released tag -> the image built from this commit.
IMAGES = (
    "bunkerweb",
    "bunkerweb-scheduler",
    "bunkerweb-api",
    "bunkerweb-worker",
    "bunkerweb-autoconf",
    "bunkerweb-ui",
    "bunkerweb-all-in-one",
)

# Forced onto the scheduler of every example stack under test.
SCHEDULER_OVERRIDES = {
    "USE_LETS_ENCRYPT_STAGING": "yes",
    "LETS_ENCRYPT_MAX_RETRIES": "3",
    "CUSTOM_LOG_LEVEL": "debug",
    "LOG_LEVEL": "info",
    "USE_BUNKERNET": "no",
    "SEND_ANONYMOUS_REPORT": "no",
    "USE_DNSBL": "no",
}

# The file each integration deploys. Linux has no compose file at all: the package is already
# installed in the systemd container, and the example configures that instance through its own
# variables.env, so that file is what gets deployed.
STACK_FILES = {
    "Docker": "docker-compose.yml",
    "Autoconf": "autoconf.yml",
    "Kubernetes": "kubernetes.yml",
    "Linux": "variables.env",
}

# Isolates the Autoconf stack from any other BunkerWeb container on the same daemon. Must match
# NAMESPACES in tests/docker/docker-compose.autoconf.yml and the bunkerweb.NAMESPACE label in
# tests/docker/docker-compose.bunkerweb.yml. generate.py imports it from here.
AUTOCONF_NAMESPACE = "bw-tests"


def _join_test_namespace(content: str, logger: Logger) -> str:
    """Put the example's services in the namespace the test controller watches.

    The controller is scoped to `bw-tests` so it does not adopt every BunkerWeb container on
    the daemon, and that filter applies to service discovery too: an example's containers carry
    `bunkerweb.SERVER_NAME` labels but no namespace, so the controller ignored them entirely.
    The stack still came up and BunkerWeb still answered — with `SERVER_NAME` empty, from the
    default server — so the failure looked like the application serving the wrong page.
    """
    stack = safe_load(content)
    for name, service in (stack.get("services") or {}).items():
        labels = service.get("labels")
        if not labels:
            continue
        if isinstance(labels, dict):
            if any(key.startswith("bunkerweb.") for key in labels):
                labels.setdefault("bunkerweb.NAMESPACE", AUTOCONF_NAMESPACE)
                logger.debug(f"Namespaced example service {name}")
        elif any(str(label).startswith("bunkerweb.") for label in labels):
            if not any(str(label).startswith("bunkerweb.NAMESPACE") for label in labels):
                labels.append(f"bunkerweb.NAMESPACE={AUTOCONF_NAMESPACE}")
                logger.debug(f"Namespaced example service {name}")
    return safe_dump(stack, indent=2, sort_keys=False)


# On Docker an example ships the whole stack, BunkerWeb included, and replaces the one
# the framework composes. On Autoconf and Kubernetes it ships only its application layer
# and the labels or annotations that configure it, so it is deployed on top of the
# framework's stack instead. On Linux there is nothing to deploy: start.sh installs the
# variables.env before the units start and setup-linux.sh provisions the web root inside
# the systemd container. start.sh reads this from the integration name.


def materialise(logger: Logger, name: str, integration: str, bw_version: str) -> Path:
    """Copy examples/<name> to /tmp and point it at the images under test.

    Returns the path of the compose file to deploy.
    """
    source = Path("examples", name)
    if not source.is_dir():
        logger.error(f"Example {name} does not exist")
        exit(1)

    compose_name = STACK_FILES.get(integration)
    if compose_name is None:
        logger.error(f"Examples are not wired for the {integration} integration")
        exit(1)

    if STACK_DIR.exists():
        try:
            rmtree(STACK_DIR)
        except PermissionError:
            # An example that ships a database leaves its data directory behind owned by the
            # container's user (mattermost's `pgdata` is postgres:70), and the runner is not
            # root. Every later example then died here, at generation, nowhere near the spec
            # that actually created the directory. Delete it as root in a throwaway container.
            logger.warning(f"🧹 {STACK_DIR} holds root-owned files, removing it in a container")
            run(["docker", "run", "--rm", "-v", f"{STACK_DIR.parent}:/host", "bash:5", "rm", "-rf", f"/host/{STACK_DIR.name}"], check=True)
    copytree(source, STACK_DIR)

    compose = STACK_DIR.joinpath(compose_name)
    if not compose.is_file():
        logger.error(f"Example {name} has no {compose_name}, so it cannot run on {integration}")
        exit(1)

    content = compose.read_text()

    if integration == "Linux":
        # Nothing to re-tag: the packaged BunkerWeb under test is already installed. The
        # overrides go in as env-file lines, prepended for the same reason as below -- the
        # loader keeps the last assignment of a key, so the example still wins.
        content = "".join(f"{key}={value}\n" for key, value in SCHEDULER_OVERRIDES.items()) + content
    else:
        for image in IMAGES:
            content = sub(rf"image: bunkerity/{image}:\S+", f"image: bunkerity/{image}:{bw_version}", content)

        # The scheduler's environment block gets the test overrides prepended, so an example
        # that sets one of them later in the block still wins.
        overrides = "".join(f'      {key}: "{value}"\n' for key, value in SCHEDULER_OVERRIDES.items())
        content = sub(
            r"(^  bw-scheduler:\n(?:.*\n)*?    environment:\n)",
            r"\1" + overrides,
            content,
            count=1,
            flags=MULTILINE,
        )

    if integration == "Autoconf":
        content = _join_test_namespace(content, logger)

    compose.write_text(content)
    STACK_MARKER.write_text(str(compose))
    logger.info(f"📝 Materialised example {name} at {compose}")
    return compose


def clear() -> None:
    """Drop the marker so the next non-example run uses the framework's own stack."""
    STACK_MARKER.unlink(missing_ok=True)
