#!/usr/bin/python3
# -*- coding: utf-8 -*-

from functools import partial
from logging import Logger
from os import getenv, listdir
from pathlib import Path
from time import sleep
from typing import Any

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class UiContext:
    def __init__(self, LOGGER: Logger, driver: webdriver.Firefox, driver_wait: WebDriverWait):
        self.LOGGER = LOGGER
        self.driver = driver
        self.wait = driver_wait
        self.base_url: str = ""
        self.saved_data: dict[str, Any] = {}


def build_driver(LOGGER: Logger, accept_insecure_certs: bool = True) -> webdriver.Firefox:
    firefox_options = Options()
    local_geckodriver = "geckodriver" in listdir(Path.cwd())

    if getenv("HEADLESS") or not local_geckodriver:
        firefox_options.add_argument("--headless")
        firefox_options.add_argument("--width=1920")
        firefox_options.add_argument("--height=1080")
    firefox_options.log.level = "trace"  # type: ignore

    if accept_insecure_certs:
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


def get_wait(driver: webdriver.Firefox, timeout: int = 30) -> WebDriverWait:
    return WebDriverWait(driver, timeout)


def maybe_sleep(LOGGER: Logger, seconds: float | int | None) -> None:
    if seconds and seconds > 0:
        LOGGER.info(f"🦊 Sleeping for {seconds} seconds ...")
        sleep(seconds)
