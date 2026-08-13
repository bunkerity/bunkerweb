#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from selenium.webdriver.support.ui import WebDriverWait


def handle(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    if step_data.new_tab:
        driver.execute_script("window.open()")
        driver.switch_to.window(driver.window_handles[-1])
        driver.switch_to.default_content()
        WebDriverWait(driver, 30)

    if step_data.url:
        driver.get(step_data.url.replace("%BASE_URL%", ctx.base_url))
    else:
        driver.get(f"{ctx.base_url}/{step_data.page}")
        if not driver.current_url.endswith(step_data.page):
            LOGGER.error(f"Didn't get redirected to {step_data.page} page: {driver.current_url}, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)

    LOGGER.info(f"🦊 Got redirected to the {step_data.page} page ✅")
