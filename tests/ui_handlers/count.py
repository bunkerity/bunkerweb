#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from time import sleep, time
from typing import Any

from selenium.webdriver.common.by import By


def _count(ctx, step_data: Any) -> int:
    by = {"xpath": By.XPATH, "id": By.ID, "name": By.NAME, "css selector": By.CSS_SELECTOR}[step_data.by]
    return len(ctx.driver.find_elements(by, step_data.selector))


def handle_count(LOGGER: Logger, ctx, step_data: Any) -> None:
    if step_data.key and not step_data.greater_than:
        ctx.saved_data[step_data.key] = _count(ctx, step_data)
        LOGGER.info(f"🦊 Saved {ctx.saved_data[step_data.key]} match(es) of {step_data.selector} as {step_data.key} ✅")
        return

    previous = ctx.saved_data[step_data.greater_than]
    deadline = time() + step_data.timeout
    while True:
        current = _count(ctx, step_data)
        if current > previous:
            LOGGER.info(f"🦊 {step_data.selector} has {current} match(es), more than the {previous} saved as {step_data.greater_than} ✅")
            return
        if time() > deadline:
            LOGGER.error(f"🦊 {step_data.selector} still has {current} match(es), expected more than {previous}")
            ctx.driver.save_screenshot("error.png")
            exit(1)
        sleep(10)
        # Server-rendered pages only show new rows after a reload
        ctx.driver.refresh()
