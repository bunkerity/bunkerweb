#!/usr/bin/python3
# -*- coding: utf-8 -*-

from functools import partial
from logging import Logger
from os import listdir
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


def build_driver(LOGGER: Logger, action: Any):
    firefox_options = Options()
    local_geckodriver = "geckodriver" in listdir(Path.cwd())

    if not local_geckodriver:
        firefox_options.add_argument("--headless")
    firefox_options.log.level = "trace"  # type: ignore

    if not action.verify_ssl:
        firefox_options.accept_insecure_certs = True

    driver_func = partial(
        webdriver.Firefox,
        service=Service(
            executable_path="./geckodriver" if local_geckodriver else "/usr/local/bin/geckodriver",
            log_output="./geckodriver.log",
        ),
        options=firefox_options,
    )

    LOGGER.info("🦊 Starting Firefox ...")
    return driver_func()
