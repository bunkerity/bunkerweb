#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from logging import Logger
from typing import Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

from utils.ui import safe_get_element


def handle_save_data(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    element = None
    with suppress(TimeoutException):
        element = safe_get_element(
            LOGGER,
            driver,
            step_data.by,
            step_data.selector,
            error=False,
            driver_wait=WebDriverWait(driver, 4),
        )

    if step_data.attribute:
        ctx.saved_data[step_data.key] = element.get_attribute(step_data.attribute)
        if step_data.key == "totp_secret":
            from pyotp import TOTP

            LOGGER.debug(f"🦊 Got TOTP secret: {ctx.saved_data[step_data.key]}")
            ctx.saved_data["totp"] = TOTP(ctx.saved_data[step_data.key].replace("-", ""))
    else:
        ctx.saved_data[step_data.key] = element.text.strip()


def handle_find(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    element = None
    with suppress(TimeoutException):
        element = safe_get_element(
            LOGGER,
            driver,
            step_data.by,
            step_data.selector,
            error=not step_data.findable,
            driver_wait=WebDriverWait(driver, 4 if step_data.findable else 1),
        )

    if step_data.findable:
        LOGGER.info(f"🦊 Element {step_data.selector} is found ✅")
    else:
        if element:
            LOGGER.error(f"🦊 Element {step_data.selector} is found, but it shouldn't be")
            driver.save_screenshot("error.png")
            exit(1)
        LOGGER.info(f"🦊 Element {step_data.selector} is not found, as expected ✅")
