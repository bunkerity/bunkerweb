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
        # Scoped to the modal instead of the label: server-rendered labels go through gettext
        # now, so `data-i18n` is gone from everything the templates emit (it survives only in
        # JS-built markup). Both instance modals are in the DOM at once, so the id scope is what
        # keeps this unambiguous; inside one modal the submit button is unique. The dot-free
        # predicate is the raw-key guard -- see the long note in ui_handlers/services.py; a red here
        # is either the button moving or its label rendering as `button.delete_instance`.
        '//div[@id="modal-delete-instances"]//button[@type="submit"][not(contains(normalize-space(.), "."))]',
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
    assert_button_click(LOGGER, driver, "//button[@id='instances-create-btn']")
    sleep(1)

    hostname_field = safe_get_element(LOGGER, driver, By.ID, "hostname")
    hostname_field.send_keys(step_data.hostname)

    name_field = safe_get_element(LOGGER, driver, By.ID, "name")
    name_field.send_keys(step_data.name)

    access_page(
        LOGGER,
        driver,
        # Scoped to the modal instead of the label: server-rendered labels go through gettext
        # now, so `data-i18n` is gone from everything the templates emit (it survives only in
        # JS-built markup). Both instance modals are in the DOM at once, so the id scope is what
        # keeps this unambiguous; inside one modal the submit button is unique. The dot-free
        # predicate is the raw-key guard -- see the long note in ui_handlers/services.py; a red here
        # is either the button moving or its label rendering as `button.delete_instance`.
        '//div[@id="modal-create-instance"]//button[@type="submit"][not(contains(normalize-space(.), "."))]',
        "instances",
    )

    safe_get_element(
        LOGGER,
        driver,
        By.XPATH,
        f'//table[@id="instances"]//td[contains(text(), "{step_data.hostname}")]',
    )

    LOGGER.info(f"🦊 Created instance {step_data.hostname} ✅")
