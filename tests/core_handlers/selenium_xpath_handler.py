#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from .selenium_common import build_driver


def handle(LOGGER: Logger, action: Any) -> None:
    driver = build_driver(LOGGER, action)
    try:
        if action.clear_cookies:
            driver.delete_all_cookies()

        driver.maximize_window()
        driver_wait = WebDriverWait(driver, 10)

        LOGGER.info(f"🦊 Navigating to {action.url} ...")
        driver.get(str(action.url))

        LOGGER.debug(f"🦊 Page source: {driver.page_source}")
        LOGGER.debug(f"🦊 Page URL: {driver.current_url}")

        xpath = action.xpath
        try:
            driver_wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            LOGGER.info(f"🔎 Xpath {xpath} found in page")
        except TimeoutException:
            LOGGER.exception(f"🔎 Xpath {xpath} not found in page")
            exit(1)

        if action.current_url_contains and action.current_url_contains not in driver.current_url:
            LOGGER.error(f"🔎 URL {driver.current_url} does not contain {action.current_url_contains}")
            exit(1)
    finally:
        driver.quit()
