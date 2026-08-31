#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from glob import glob
from json import dumps
from logging import getLogger
from os import getenv, sep
from os.path import basename, join
from pathlib import Path
from typing import List

from yaml import safe_load

import utils.logger  # noqa: F401

LOGGER = getLogger("PARSE")

parser = ArgumentParser(prog="Tests parser", description="Parse test files and return them as a b64encoded json file.")
parser.add_argument("type", type=str, help="Type of test to parse", choices=["core", "ui", "api"])
parser.add_argument(
    "--integration", type=str, help="Integration to parse tests for", choices=["Docker", "Linux", "Autoconf", "Swarm", "Kubernetes", "All-in-one"]
)
parser.add_argument("--category", type=str, help="Category of the test to parse actions from")
parser.add_argument("--dev", action="store_true", help="Run in development mode")
ARGS = parser.parse_args()

LOGGER.info(f"✂ Parsing {ARGS.type} tests{' in dev mode' if ARGS.dev else ''}{', only actions from category ' + ARGS.category if ARGS.category else ''}")
LOGGER.debug(f"Arguments: {ARGS}")

# Arms a spec has to ask for BY NAME. `integrations: "all"` means "every arm this framework runs
# a spec on by default", and Swarm is deliberately not one of them: the arm exists and works, but
# it has been proven against a named subset of the catalogue, not against all of it. Without this
# gate, giving the Swarm rows a runner in integrations.yml would silently enrol every `all` spec
# — around seventy of them — in an arm none of them has ever executed on, and the resulting board
# is indistinguishable from a broken product.
#
# Widening it is a one-line deletion the day the whole catalogue has been run. Until then the
# deferral is visible here rather than hidden in a green wall.
OPT_IN_ONLY = ("Swarm",)

integrations = {}
if not ARGS.category:
    LOGGER.info("📖 Reading integrations.yml")

    integrations = safe_load(Path("tests", "utils", "integrations.yml").read_text())["dev" if ARGS.dev else "staging"]

    LOGGER.debug(f"Integrations: {integrations}")


# An arm has two spellings and both are load-bearing. Specs, the `--integration` CLI choices and
# the pydantic `integrations` literals use the human one ("All-in-one"); integrations.yml keys, the
# first field of a matrix entry, the `/tmp/tests/<arm>_tests.json` file names and the GitHub Actions
# outputs built from them use the identifier one ("All_in_one"), because a hyphen cannot appear in a
# GitHub expression property (`outputs.All-in-one_tests` does not parse) nor in a Python attribute.
# `generate.py` and `integration-tests.yml` each convert at their own boundary; this is parse.py's.
#
# Without it `check_integration(["All-in-one"], ...)` missed the `All_in_one` key and the three specs
# that name the arm explicitly -- upgrade, badbehavior and limit -- were dropped from the matrix with
# nothing but a warning in a log nobody reads.
def integration_key(name: str) -> str:
    """integrations.yml key for an arm as a spec spells it."""
    return name.replace("-", "_")


def check_integration(entry: List[str], data: dict) -> bool:
    """Check if the integration exists in the integrations.yml file"""
    if entry:
        return data.get(entry[0], False) and check_integration(entry[1:], data[entry[0]])
    return True


tests = []
if not ARGS.category:
    LOGGER.info("📖 Reading tests")

    for file in glob(join("tests", ARGS.type, "*.yml")):
        LOGGER.debug(f"Reading {file}")
        data = safe_load(Path(file).read_text())
        if data:
            name = basename(file).split(".")[0]
            test_integrations = data.get("integrations", [])
            LOGGER.debug(f"Integrations: {test_integrations}")
            # A spec that wants every default arm PLUS an opt-in one writes
            # `integrations: ["all", "Swarm"]`; the bare string keeps working and means the
            # default arms only. Spelling the whole list out instead would freeze it, so a new
            # arm would silently skip every spec that had done so.
            if test_integrations == "all":
                test_integrations = ["all"]

            if isinstance(test_integrations, list) and "all" in test_integrations:
                for integration, arch in integrations.items():
                    if integration in OPT_IN_ONLY:
                        LOGGER.debug(f"Skipping {integration} for {name}: it is opt-in and this spec asks for 'all'")
                        continue
                    for arch, specs in arch.items():
                        if isinstance(specs, dict):
                            for spec, value in specs.items():
                                if value == "TODO":
                                    LOGGER.debug(f"Skipping {integration} / {arch} / {spec} because it's TODO")
                                    continue
                                tests.append(f"{integration};{arch};{spec};{value};{name}")
                            continue
                        elif specs == "TODO":
                            LOGGER.debug(f"Skipping {integration} / {arch} because it's TODO")
                            continue
                        tests.append(f"{integration};{arch};{specs};{name}")
                test_integrations = [entry for entry in test_integrations if entry != "all"]

            if isinstance(test_integrations, list):
                for integration in test_integrations:
                    parts = integration.split(";")
                    parts[0] = integration_key(parts[0])
                    integration = ";".join(parts)
                    if not check_integration(parts, integrations):
                        LOGGER.warning(f"Skipping integration {integration} for {name}")
                        continue

                    run_on = integrations[parts[0]]
                    if len(parts) > 1:
                        run_on = run_on[parts[1]]
                    if len(parts) > 2:
                        run_on = run_on[parts[2]]

                    if run_on == "TODO":
                        LOGGER.debug(f"Skipping {integration} because it's TODO")
                        continue

                    # "Docker" on its own leaves every architecture (and, on Linux, every
                    # distribution) unresolved. Expand them the way `integrations: "all"`
                    # does instead of stringifying the dict into the matrix entry.
                    if isinstance(run_on, dict):
                        for suffix, value in run_on.items():
                            if isinstance(value, dict):
                                for spec, spec_value in value.items():
                                    if spec_value == "TODO":
                                        LOGGER.debug(f"Skipping {integration} / {suffix} / {spec} because it's TODO")
                                        continue
                                    tests.append(f"{integration};{suffix};{spec};{spec_value};{name}")
                                continue
                            if value == "TODO":
                                LOGGER.debug(f"Skipping {integration} / {suffix} because it's TODO")
                                continue
                            tests.append(f"{integration};{suffix};{value};{name}")
                        continue

                    tests.append(f"{integration};{run_on};{name}")
            elif test_integrations:
                LOGGER.error(f"Invalid integrations for {name}: {test_integrations}")
        else:
            LOGGER.error(f"Invalid YAML in {file}")
            LOGGER.debug(f"Data: {data}")
else:
    LOGGER.info(f"📖 Reading actions from category: {ARGS.category}")
    file_path = join("tests", ARGS.type, ARGS.category + ".yml")
    LOGGER.debug(f"Reading {file_path}")
    data = safe_load(Path(file_path).read_text())
    if data:
        for action, settings in data.get("actions", {}).items():
            if ARGS.integration is not None and "integrations" in settings and ARGS.integration not in settings["integrations"]:
                LOGGER.warning(f"Ignoring {action} because it's not for {ARGS.integration}")
                continue
            tests.append(f"{ARGS.category};{action}")
    else:
        LOGGER.error(f"Invalid YAML in {file_path}")
        LOGGER.debug(f"Data: {data}")
        exit(1)

LOGGER.debug(f"Tests: {tests}")

if tests:
    LOGGER.info("📝 Writing tests files")

    if not ARGS.category:
        tmp_path = Path(sep, "tmp", "tests")
        tmp_path.mkdir(parents=True, exist_ok=True)

        for integration in integrations:
            tmp_path.joinpath(f"{integration}_tests.json").write_text(dumps([test for test in tests if test.startswith(f"{integration};")]))
    else:
        from redis import Redis

        redis_client = Redis(host="localhost", port=int(getenv("TESTS_REDIS_PORT", "6390")), db=0)

        resp = redis_client.ping()
        if not resp:
            LOGGER.error("Redis server is not running")
            exit(1)

        redis_client.rpush("tests", *tests)
