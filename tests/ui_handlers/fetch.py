#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

_FETCH_SCRIPT = """
const [url, method, headers, count, done] = arguments;
(async () => {
  const statuses = [];
  for (let i = 0; i < count; i++) {
    try {
      const response = await fetch(url, { method, headers, credentials: "same-origin", redirect: "manual" });
      statuses.push(response.status);
    } catch (e) {
      statuses.push(String(e));
    }
  }
  done(statuses);
})();
"""


def handle_fetch(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver
    driver.set_script_timeout(120)
    url = step_data.url.replace("%BASE_URL%", ctx.base_url)
    statuses = driver.execute_async_script(_FETCH_SCRIPT, url, step_data.method, step_data.headers, step_data.count)
    LOGGER.info(f"🦊 {step_data.method} {url} x{step_data.count} answered {statuses}")

    if step_data.status is not None and any(status != step_data.status for status in statuses):
        LOGGER.error(f"🦊 Expected status {step_data.status} for every request to {url}, got {statuses}")
        driver.save_screenshot("error.png")
        exit(1)
    LOGGER.info(f"🦊 Fetched {url} ✅")
