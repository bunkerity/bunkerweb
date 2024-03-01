from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from random import randint

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the bans page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[9]/a", "bans")

    try:
        safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div[2]/div/h5", error=True)
    except TimeoutException:
        log_exception("Bans present even though they shouldn't be, exiting ...")
        exit(1)

    log_info("No bans found, as expected, trying to add a ban ...")

    assert_button_click(DRIVER, "//button[@data-add-ban='']")

    try:
        safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-add-ban-list='']/li", error=True)
    except TimeoutException:
        log_exception("No bans found, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-add-ban-delete-all-item='']")

    with suppress(TimeoutException):
        safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-add-ban-list='']/li", error=True)
        log_error("Bans present even though they shouldn't be, exiting ...")
        exit(1)

    log_info("No bans found, as expected, trying to add multiple bans ...")

    add_entry_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-ban-add-new='']")
    assert isinstance(add_entry_button, WebElement), "Add entry button not found"

    assert_button_click(DRIVER, add_entry_button)

    ip_input = safe_get_element(DRIVER, By.ID, "ip-1")
    assert isinstance(ip_input, WebElement), "IP input not found"
    ip_input.send_keys(f"127.0.0.{randint(10, 122)}")

    assert_button_click(DRIVER, add_entry_button)

    ip_input = safe_get_element(DRIVER, By.ID, "ip-2")
    assert isinstance(ip_input, WebElement), "IP input not found"
    ip_input.send_keys(f"127.0.0.{randint(123, 255)}")

    access_page(DRIVER, "//button[@data-bans-modal-submit='']", "bans", False)

    try:
        entries = safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-list='']/li", multiple=True, error=True)
        assert isinstance(entries, list), "Bans not found"
    except TimeoutException:
        log_exception("No ban found, exiting ...")
        exit(1)

    if len(entries) != 2:
        log_error("The bans are present but there should be 2, exiting ...")
        exit(1)

    log_info("Bans found, trying filters ...")

    # Get total bans
    bans = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-bans-list-item]")')
    bans_total = len(bans)

    key_word_filter_input = safe_get_element(DRIVER, "js", 'document.querySelector("input#keyword")')
    assert isinstance(key_word_filter_input, WebElement), "Key word filter input is not a WebElement"
    key_word_filter_input.send_keys("dzq841czqdeqzzd")

    bans_hidden = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-bans-list-item][class*=hidden]")')

    if len(bans_hidden) == 0:
        log_error("The keyword filter is not working, exiting ...")
        exit(1)

    # Reset
    key_word_filter_input.send_keys("")

    # Test select filters
    select_filters = [{"name": "reason", "id": "reason", "value": "all"}, {"name": "range", "id": "term", "value": "all"}]

    for item in select_filters:
        DRIVER.execute_script(f"""document.querySelector('[data-bans-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()""")

    log_info("Bans found, trying to delete them ...")

    delete_ban_checkbox = safe_get_element(DRIVER, By.XPATH, "//input[@id='ban-item-2']")
    assert isinstance(delete_ban_checkbox, WebElement), "Delete checkbox is not WebElement"
    DRIVER.execute_script("arguments[0].click()", delete_ban_checkbox)

    unban_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-unban-btn='']")
    assert isinstance(unban_button, WebElement), "Delete button is not WebElement"

    DRIVER.execute_script("arguments[0].click()", unban_button)

    refresh = safe_get_element(DRIVER, By.XPATH, "//button[@data-unban-btn='']", 5)

    try:
        entries = safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-list='']/li", multiple=True, error=True)
        assert isinstance(entries, list), "Bans not found"
    except TimeoutException:
        log_exception("No bans found, exiting ...")
        exit(1)

    if len(entries) != 1:
        log_error("The bans are present but there should be 1, exiting ...")
        exit(1)

    log_info("Ban deleted successfully")

    log_info("✅ Bans page tests finished successfully")
except SystemExit as e:
    exit_code = e.code
except KeyboardInterrupt:
    exit_code = 1
except:
    log_exception("Something went wrong, exiting ...")
    exit_code = 1
finally:
    if exit_code:
        DRIVER.save_screenshot("error.png")
    DRIVER.quit()
    exit(exit_code)
