#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from re import match as re_match
from typing import Any

from .selenium_common import build_driver


def handle(LOGGER: Logger, action: Any) -> None:
    driver = build_driver(LOGGER, action)
    try:
        if action.clear_cookies:
            driver.delete_all_cookies()

        driver.maximize_window()

        LOGGER.info(f"🦊 Navigating to {action.url} ...")
        driver.get(str(action.url))

        LOGGER.debug(f"🦊 Page source: {driver.page_source}")
        LOGGER.debug(f"🦊 Page URL: {driver.current_url}")

        cookie_name = action.cookie_name
        cookie_rx = action.cookie_rx
        cookie_secure_flag = action.cookie_secure_flag
        cookie_http_only_flag = action.cookie_http_only_flag
        cookie_same_site_flag = action.cookie_same_site_flag

        cookie = driver.get_cookie(cookie_name)
        if cookie is not None:
            if cookie_rx is None:
                LOGGER.error(f"🍪 Cookie {cookie_name} found in page, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            elif not re_match(cookie_rx, cookie["value"]):
                LOGGER.error(f"🍪 Cookie {cookie_name} who matches regex {cookie_rx} not found in page, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            elif cookie.get("secure", False) != cookie_secure_flag:
                LOGGER.error(f"🍪 Cookie {cookie_name} doesn't have the right secure flag, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            elif cookie.get("httpOnly", False) != cookie_http_only_flag:
                LOGGER.error(f"🍪 Cookie {cookie_name} doesn't have the right HttpOnly flag, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            elif cookie.get("sameSite", None) != cookie_same_site_flag:
                LOGGER.error(f"🍪 Cookie {cookie_name} doesn't have the right SameSite flag, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            LOGGER.info(f"🍪 Cookie {cookie_name} who matches regex {cookie_rx} found in page, flags are correct")
        elif cookie_rx is not None:
            LOGGER.error(f"🍪 Cookie {cookie_name} who matches regex {cookie_rx} not found in page, exiting ...\ncookies: {driver.get_cookies()}")
            exit(1)
        else:
            LOGGER.info(f"🍪 Cookie {cookie_name} not found in page")
    finally:
        driver.quit()
