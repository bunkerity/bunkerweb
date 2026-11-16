#!/usr/bin/python3
# -*- coding: utf-8 -*-

from functools import partial
from logging import Logger, getLogger
from os import listdir
from pathlib import Path
from socket import getdefaulttimeout, setdefaulttimeout
from typing import Any

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Selenium's Service.stop() does urlopen(f"{service_url}/shutdown") with no timeout: against a geckodriver blocked on
# a wedged Firefox it waits forever (CI run 43829563191, antibot / javascript_query_original_uri held a runner for
# 67+ minutes). Only the quit path gets a socket default timeout, so long harness HTTP/Docker calls are untouched.
# Keep in step with the identical class in tests/ui_handlers/common.py.
QUIT_SOCKET_TIMEOUT = 60


class BoundedFirefox(webdriver.Firefox):
    """Firefox whose quit() cannot block forever; a timeout is logged and never raised, so the test's own result stands."""

    def quit(self) -> None:
        previous = getdefaulttimeout()
        setdefaulttimeout(QUIT_SOCKET_TIMEOUT)
        try:
            super().quit()
        except Exception as e:
            getLogger("SELENIUM").warning(f"🦊 Firefox did not shut down cleanly ({type(e).__name__}: {e}), geckodriver was terminated")
        finally:
            setdefaulttimeout(previous)


def build_driver(LOGGER: Logger, action: Any):
    firefox_options = Options()
    local_geckodriver = "geckodriver" in listdir(Path.cwd())

    if not local_geckodriver:
        firefox_options.add_argument("--headless")
    firefox_options.log.level = "trace"  # type: ignore

    if not action.verify_ssl:
        firefox_options.accept_insecure_certs = True

    driver_func = partial(
        BoundedFirefox,
        service=Service(
            executable_path="./geckodriver" if local_geckodriver else "/usr/local/bin/geckodriver",
            log_output="./geckodriver.log",
        ),
        options=firefox_options,
    )

    LOGGER.info("🦊 Starting Firefox ...")
    return driver_func()
