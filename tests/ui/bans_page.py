from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from random import randint

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the bans page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[9]/a", "bans")

    try:
        safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div[2]/div/h5", error=True)
    except TimeoutException:
        log_exception("Bans present even though they shouldn't be, exiting ...")
        exit(1)

    log_info("No bans found, as expected, trying to add a ban ...")

    assert_button_click(DRIVER, "//button[@data-add-ban='']")

    log_info("Add ban modal clicked ...")

    try:
        safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-add-ban-list='']/li", error=True)
    except TimeoutException:
        log_exception("No bans found, exiting ...")
        exit(1)

    log_info("Add one ban to try delete entry button ...")

    add_entry_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-ban-add-new='']")
    assert isinstance(add_entry_button, WebElement), "Add entry button not found"

    assert_button_click(DRIVER, add_entry_button)

    ip_input = safe_get_element(DRIVER, By.ID, "ip-1")
    assert isinstance(ip_input, WebElement), "IP input not found"
    ip_input.send_keys(f"127.0.0.{randint(10, 122)}")

    assert_button_click(DRIVER, "//button[@data-add-ban-delete-all-item='']")

    log_info("Delete all add bans from button clicked ...")

    with suppress(TimeoutException):
        safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-add-ban-list='']/li", error=True)
        log_error("Bans present even though they shouldn't be, exiting ...")
        exit(1)

    log_info("Toggle modal, then trying to add multiple bans ...")

    close_modal = safe_get_element(DRIVER, By.XPATH, "//button[@data-bans-modal-close='']")
    assert isinstance(close_modal, WebElement), "Add entry button not found"

    assert_button_click(DRIVER, close_modal)

    assert_button_click(DRIVER, "//button[@data-add-ban='']")

    add_entry_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-ban-add-new='']")
    assert isinstance(add_entry_button, WebElement), "Add entry button not found"

    assert_button_click(DRIVER, add_entry_button)

    ip_input = safe_get_element(DRIVER, By.ID, "ip-2")
    ip_input_value = f"127.0.0.{randint(10, 122)}"
    assert isinstance(ip_input, WebElement), "IP input not found"
    ip_input.send_keys(ip_input_value)

    assert_button_click(DRIVER, add_entry_button)

    ip_input_2 = safe_get_element(DRIVER, By.ID, "ip-3")
    ip_input_value_2 = f"127.0.0.{randint(123, 255)}"
    assert isinstance(ip_input_2, WebElement), "IP input not found"
    ip_input_2.send_keys(ip_input_value_2)

    log_info("Added 2 bans entries to modal, click on save ...")

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

    log_info("Bans added successfully, trying to filter ...")

    # Get total bans
    bans = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-bans-list-item]")')
    bans_total = len(bans)

    if bans_total == 0:
        log_error("Need at least one ban to test filters ...")
        exit(1)

    log_info("Start with keyword filtering ...")

    key_word_filter_input = safe_get_element(DRIVER, By.XPATH, "//input[@id='keyword']")
    assert isinstance(key_word_filter_input, WebElement), "Key word filter input is not a WebElement"
    key_word_filter_input.send_keys("dzq841czqdeqzzd")

    bans_hidden = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-bans-list-item][class*=hidden]")')
    bans_hidden_total = len(bans_hidden)

    log_info(f"Added 'dzq841czqdeqzzd' value, bans hidden {bans_hidden_total} / {bans_total} ...")

    if bans_hidden_total != 2:
        log_error("Keyword filtering error, should have match nothing ...")
        exit(1)

    # Reset
    key_word_filter_input.send_keys(Keys.CONTROL, "a")
    key_word_filter_input.send_keys(Keys.BACKSPACE)

    log_info("Keyword filter with no match worked, trying to match a  ban value ...")
    key_word_filter_input.send_keys(ip_input_value_2)

    bans_hidden = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-bans-list-item][class*=hidden]")')
    bans_hidden_total = len(bans_hidden)

    if bans_hidden_total != 1:
        log_error("Keyword filtering error, should have match one ban ...")
        exit(1)

    log_info("Keyword filter to show only one ban worked, trying select filters ...")

    # Test select filters
    select_filters = [{"name": "reason", "id": "reason", "value": "all"}, {"name": "range", "id": "term", "value": "all"}]

    for item in select_filters:
        DRIVER.execute_script(f"""return document.querySelector('[data-bans-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()""")

    log_info("Trying to delete 1 ban ...")

    try:
        entries = safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-list='']/li", multiple=True, error=True)
        assert isinstance(entries, list), "Bans not found"
        log_info(f"Currently {len(entries)} bans items ...")
    except TimeoutException:
        log_exception("No bans found, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//input[@id='ban-item-2']")

    log_info("Ban item 2 checkbox clicked ...")
    delete_ban_checkbox = safe_get_element(DRIVER, By.XPATH, "//input[@id='ban-item-2']")
    delete_ban_state = DRIVER.execute_script("return arguments[0].checked", delete_ban_checkbox)

    if not delete_ban_state:
        log_exception("Checkbox not checked...")
        exit(1)

    unban_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-unban-btn='']")
    assert isinstance(unban_button, WebElement), "Delete button is not WebElement"

    unban_disabled_state = DRIVER.execute_script("return arguments[0].hasAttribute('disabled')", delete_ban_checkbox)

    if unban_disabled_state:
        log_exception("Disabled attribute is on unban button ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-unban-btn='']")

    log_info("Unban button clicked, access bans ...")

    access_page(DRIVER, False, "bans")

    try:
        entries = safe_get_element(DRIVER, By.XPATH, "//ul[@data-bans-list='']/li", multiple=True, error=True)
        assert isinstance(entries, list), "Bans not found"
        log_info(f"Currently {len(entries)} bans items ...")
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
