#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from utils.ui import access_page, assert_button_click, safe_get_element


def handle_click(LOGGER: Logger, ctx, step_data: Any) -> None:
    assert_button_click(LOGGER, ctx.driver, step_data.selector, step_data.by)
    LOGGER.info(f"🦊 Clicked on element {step_data.selector} ✅")


def handle_access_page(LOGGER: Logger, ctx, step_data: Any) -> None:
    access_page(LOGGER, ctx.driver, step_data.selector, step_data.page)
    LOGGER.info(f"🦊 Got redirected to the {step_data.page} page ✅")


def handle_send_keys(LOGGER: Logger, ctx, step_data: Any) -> None:
    element = safe_get_element(LOGGER, ctx.driver, step_data.by, step_data.selector)
    if step_data.clear:
        element.clear()
    value = step_data.value
    if value == "%TOTP_TOKEN%":
        value = ctx.saved_data["totp"].now()
    if isinstance(value, str) and value.startswith("%DATA:") and value.endswith("%"):
        value = ctx.saved_data[value[6:-1]]
    element.send_keys(value)
    if not value:
        from selenium.webdriver.common.keys import Keys

        element.send_keys(Keys.RETURN)
    LOGGER.info(f"🦊 Filled element {step_data.selector} with value {step_data.value} ✅")


def handle_refresh(LOGGER: Logger, ctx, step_data: Any) -> None:
    ctx.driver.refresh()
    LOGGER.info("🦊 Refreshed the page ✅")
