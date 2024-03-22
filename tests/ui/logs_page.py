from datetime import datetime, timedelta
from logging import info as log_info, exception as log_exception, error as log_error
from time import sleep
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER, UI_URL
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the logs page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[11]/a", "logs")

    log_info("Trying filters ...")

    key_word_filter_input = safe_get_element(DRIVER, "js", 'document.querySelector("input#keyword")')
    assert isinstance(key_word_filter_input, WebElement), "Key word filter input is not a WebElement"
    key_word_filter_input.send_keys("Antibot")

    # Reset
    key_word_filter_input.send_keys("")

    # Test select filters
    select_filters = [
        {"name": "Types", "id": "types", "value": "all"},
    ]

    for item in select_filters:
        DRIVER.execute_script(f"""return document.querySelector('[data-logs-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()""")

    log_info("Selecting correct instance ...")

    assert_button_click(DRIVER, "//button[@data-logs-setting-select='instances']")

    instances = safe_get_element(DRIVER, By.XPATH, "//div[@data-logs-setting-select-dropdown='instances']/button", multiple=True)
    assert isinstance(instances, list), "Instances is not a list"

    first_instance = instances[0].text

    if len(instances) == 0:
        log_error("No instances found, exiting ...")
        exit(1)

    assert_button_click(DRIVER, instances[0])

    submit_button = safe_get_element(DRIVER, By.ID, "submit-data")
    assert isinstance(submit_button, WebElement), "Submit button is not a WebElement"
    assert_button_click(DRIVER, submit_button)

    sleep(3)

    logs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-logs-list='']/li", multiple=True)
    assert isinstance(logs_list, list), "Logs list is not a list"

    if len(logs_list) == 0:
        log_error("No logs found, exiting ...")
        exit(1)

    log_info("Logs found, trying auto refresh ...")

    live_update_button = safe_get_element(DRIVER, By.ID, "live-update")
    assert isinstance(live_update_button, WebElement), "Live update button is not a WebElement"
    assert_button_click(DRIVER, live_update_button)

    submit_live_button = safe_get_element(DRIVER, By.ID, "submit-live")
    assert isinstance(submit_live_button, WebElement), "Submit live button is not a WebElement"
    assert_button_click(DRIVER, submit_live_button)

    sleep(3)

    new_logs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-logs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True)
    assert isinstance(new_logs_list, list), "New logs list is not a list"

    if len(logs_list) == len(new_logs_list):
        log_error("Auto refresh is not working, exiting ...")
        exit(1)

    log_info("Auto refresh is working, deactivating it ...")

    live_update_button = safe_get_element(DRIVER, By.ID, "live-update")
    assert isinstance(live_update_button, WebElement), "Live update button is not a WebElement"
    assert_button_click(DRIVER, live_update_button)

    submit_button = safe_get_element(DRIVER, By.ID, "submit-data")
    assert isinstance(submit_button, WebElement), "Submit button is not a WebElement"
    assert_button_click(DRIVER, submit_button)

    sleep(3)

    logs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-logs-list='']/li", multiple=True)
    assert isinstance(logs_list, list), "Logs list is not a list"

    log_info("Trying filters ...")

    filter_input = safe_get_element(DRIVER, By.ID, "keyword")
    assert isinstance(filter_input, WebElement), "Filter input is not a WebElement"

    filter_input.send_keys("gen")

    sleep(3)

    new_logs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-logs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True)
    assert isinstance(new_logs_list, list), "New logs list is not a list"

    if len(logs_list) == len(new_logs_list):
        log_error("The keyword filter is not working, exiting ...")
        exit(1)

    # Reset
    filter_input.send_keys(Keys.CONTROL, "a")
    filter_input.send_keys(Keys.BACKSPACE)

    log_info("Keyword filter is working, trying type filter ...")

    assert_button_click(DRIVER, "//button[@data-logs-setting-select='types']")
    assert_button_click(DRIVER, "//div[@data-logs-setting-select-dropdown='types']/button[@value='warn']")

    new_logs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-logs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True)
    assert isinstance(new_logs_list, list), "New logs list is not a list"

    if len(logs_list) == len(new_logs_list):
        log_error("The keyword filter is not working, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-logs-setting-select='types']")
    assert_button_click(DRIVER, "//div[@data-logs-setting-select-dropdown='types']/button[@value='all']")

    log_info("Type filter is working, trying to filter by date ...")

    current_date = datetime.now()
    resp = get(
        f"http://www.example.com{UI_URL}/logs/{first_instance}?from_date={int((current_date - timedelta(weeks=1)).timestamp())}&to_date={int((current_date - timedelta(days=1)).timestamp())}",
        headers={"Host": "www.example.com", "User-Agent": DRIVER.execute_script("return navigator.userAgent;")},
        cookies={"session": DRIVER.get_cookies()[0]["value"]},
    )

    if len(resp.json()["logs"]) != 0:
        log_error("The date filter is not working, exiting ...")
        exit(1)

    log_info("Date filter is working, trying jobs page ...")

    log_info("✅ Lobs page tests finished successfully")
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
