#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from time import sleep
from typing import Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from utils.ui import access_page, assert_button_click, safe_get_element


def handle_instance_delete(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    assert_button_click(
        LOGGER,
        driver,
        f'//button[@data-instance="{step_data.hostname}" and contains(@class, "delete-instance")]',
    )
    sleep(1)

    access_page(
        LOGGER,
        driver,
        '//button[@type="submit" and contains(@data-i18n, "button.delete_instance")]',
        "instances",
    )

    instance = None
    with suppress(TimeoutException):
        instance = safe_get_element(
            LOGGER,
            driver,
            By.XPATH,
            f'//table[@id="instances"]//td[contains(text(), "{step_data.hostname}")]',
            driver_wait=WebDriverWait(driver, 0.3),
            error=True,
        )

    if instance:
        LOGGER.error(f"🦊 instance {step_data.hostname} is not deleted")
        driver.save_screenshot("error.png")
        exit(1)

    LOGGER.info(f"🦊 Deleted instance {step_data.hostname} ✅")


def handle_instance_create(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    assert_button_click(LOGGER, driver, "//button[@aria-controls='instances' and contains(@class, 'btn-bw-green')]")
    sleep(1)

    hostname_field = safe_get_element(LOGGER, driver, By.ID, "hostname")
    hostname_field.send_keys(step_data.hostname)

    name_field = safe_get_element(LOGGER, driver, By.ID, "name")
    name_field.send_keys(step_data.name)

    access_page(
        LOGGER,
        driver,
        '//button[@type="submit" and contains(@data-i18n, "button.create_instance")]',
        "instances",
    )

    safe_get_element(
        LOGGER,
        driver,
        By.XPATH,
        f'//table[@id="instances"]//td[contains(text(), "{step_data.hostname}")]',
    )

    LOGGER.info(f"🦊 Created instance {step_data.hostname} ✅")
