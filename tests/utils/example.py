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

COMPOSE_FILES = {
    "Docker": "docker-compose.yml",
    "Autoconf": "autoconf.yml",
    "Kubernetes": "kubernetes.yml",
}


def materialise(logger: Logger, name: str, integration: str, bw_version: str) -> Path:
    """Copy examples/<name> to /tmp and point it at the images under test.

    Returns the path of the compose file to deploy.
    """
    source = Path("examples", name)
    if not source.is_dir():
        logger.error(f"Example {name} does not exist")
        exit(1)

    compose_name = COMPOSE_FILES.get(integration)
    if compose_name is None:
        logger.error(f"Examples are not wired for the {integration} integration")
        exit(1)

    if STACK_DIR.exists():
        rmtree(STACK_DIR)
    copytree(source, STACK_DIR)

    compose = STACK_DIR.joinpath(compose_name)
    if not compose.is_file():
        logger.error(f"Example {name} has no {compose_name}, so it cannot run on {integration}")
        exit(1)

    content = compose.read_text()

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

    compose.write_text(content)
    STACK_MARKER.write_text(str(compose))
    logger.info(f"📝 Materialised example {name} at {compose}")
    return compose


def clear() -> None:
    """Drop the marker so the next non-example run uses the framework's own stack."""
    STACK_MARKER.unlink(missing_ok=True)
