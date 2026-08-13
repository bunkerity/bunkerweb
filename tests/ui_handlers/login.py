#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from time import sleep
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from utils.ui import access_page, assert_button_click, safe_get_element


def handle(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    base_url = ctx.base_url

    if "/login" not in driver.current_url:
        driver.get(f"{base_url}/login")
        sleep(0.3)
    else:
        sleep(0.3)

    safe_get_element(LOGGER, driver, By.TAG_NAME, "form", driver_wait=WebDriverWait(driver, 30))

    sleep(0.3)

    username_input = safe_get_element(LOGGER, driver, By.ID, "username")
    username_input.send_keys(step_data.username)

    sleep(0.3)

    password_input = safe_get_element(LOGGER, driver, By.ID, "password")
    password_input.send_keys(step_data.password)

    sleep(0.3)

    assert_button_click(LOGGER, driver, "bx-hide", By.CLASS_NAME)

    if step_data.remember:
        remember_me_checkbox = safe_get_element(LOGGER, driver, By.ID, "remember-me")
        if not driver.execute_script("return arguments[0].checked", remember_me_checkbox):
            assert_button_click(LOGGER, driver, remember_me_checkbox)

    sleep(1.5)

    if not step_data.login_success:
        access_page(LOGGER, driver, "//button[@type='submit']", step_data.next_page)
        return

    if "totp" in ctx.saved_data:
        access_page(LOGGER, driver, "//button[@type='submit']", "totp")
        sleep(0.3)
        totp_token_input = safe_get_element(LOGGER, driver, By.ID, "totp_token")
        totp_code = step_data.totp_code or ctx.saved_data["totp"].now()
        if isinstance(totp_code, str) and totp_code.startswith("%DATA:") and totp_code.endswith("%"):
            totp_code = ctx.saved_data.pop(totp_code[6:-1])
        totp_token_input.send_keys(totp_code)
        if not step_data.totp_success:
            access_page(LOGGER, driver, "//button[@type='submit']", "totp")
            return
        sleep(2)

    access_page(LOGGER, driver, "//button[@type='submit']", step_data.next_page)
    LOGGER.info("🦊 Got redirected to the home page, logged in successfully ✅")
