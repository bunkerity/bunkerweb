#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from typing import Any

_FETCH_SCRIPT = """
const [url, method, headers, count, body, csrf, done] = arguments;
(async () => {
  const statuses = [];
  const init = { method, headers: { ...headers }, credentials: "same-origin", redirect: "manual" };
  if (body !== null) {
    init.body = body;
    init.headers["Content-Type"] = "application/x-www-form-urlencoded";
  }
  if (csrf) {
    const input = document.querySelector('input[name="csrf_token"]');
    if (!input) {
      done(["no csrf_token input on the current page"]);
      return;
    }
    init.headers["X-CSRFToken"] = input.value;
  }
  for (let i = 0; i < count; i++) {
    try {
      const response = await fetch(url, init);
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
    statuses = driver.execute_async_script(_FETCH_SCRIPT, url, step_data.method, step_data.headers, step_data.count, step_data.body, step_data.csrf)
    LOGGER.info(f"🦊 {step_data.method} {url} x{step_data.count} answered {statuses}")

    if step_data.status is not None and any(status != step_data.status for status in statuses):
        LOGGER.error(f"🦊 Expected status {step_data.status} for every request to {url}, got {statuses}")
        driver.save_screenshot("error.png")
        exit(1)
    LOGGER.info(f"🦊 Fetched {url} ✅")
