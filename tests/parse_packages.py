#!/usr/bin/python3
# -*- coding: utf-8 -*-

from json import dumps
from logging import getLogger
from os import sep
from pathlib import Path

from yaml import safe_load

import utils.logger  # noqa: F401

LOGGER = getLogger("PARSE")

LOGGER.info("✂ Parsing packages")

LOGGER.info("📖 Reading packages.yml")

packages = safe_load(Path("tests", "utils", "packages.yml").read_text())

LOGGER.debug(f"Packages: {packages}")

tmp_path = Path(sep, "tmp", "packages")
tmp_path.mkdir(parents=True, exist_ok=True)

for package_info, data in packages.items():
    LOGGER.info(f"📝 Writing {package_info}.json file from packages")
    tmp_path.joinpath(f"{package_info}.json").write_text(dumps(data, indent=2))
