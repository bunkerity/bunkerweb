#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

from selenium.webdriver.support.ui import WebDriverWait


def handle_switch_tab(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    if not driver.window_handles or step_data.tab >= len(driver.window_handles):
        LOGGER.error(f"🦊 Cannot switch to tab {step_data.tab}, not enough tabs available")
        driver.save_screenshot("error.png")
        exit(1)
    driver.switch_to.window(driver.window_handles[step_data.tab])
    driver.switch_to.default_content()
    WebDriverWait(driver, 30)


def handle_close_tab(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    if step_data.tab is not None:
        if not driver.window_handles or step_data.tab >= len(driver.window_handles):
            LOGGER.error(f"🦊 Cannot close tab {step_data.tab}, not enough tabs available")
            driver.save_screenshot("error.png")
            exit(1)
        driver.switch_to.window(driver.window_handles[step_data.tab])
        driver.switch_to.default_content()
    active_tab = driver.window_handles.index(driver.current_window_handle)
    driver.close()
    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[max(0, active_tab - 1)])
        driver.switch_to.default_content()
        WebDriverWait(driver, 30)
