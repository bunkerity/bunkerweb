from contextlib import suppress
from logging import info as log_info, error as log_error, exception as log_exception
from time import sleep
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER
from utils import access_page, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the reports page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[8]/a", "reports")

    with suppress(TimeoutException):
        safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/div/h5", error=True)
        log_info("No reports found, generating some ...")

        for _ in range(5):
            get("http://www.example.com/?id=/etc/passwd")
            sleep(1)

        sleep(7)

        DRIVER.refresh()

    log_info("Check if reports generated ...")

    reports_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-reports-list='']/li", multiple=True)
    assert isinstance(reports_list, list), "Reports list is not a list"

    if not reports_list:
        log_error("No reports found, exiting ...")
        exit(1)

    log_info("Reports found, trying to filter the reports ...")

    # Test select filters
    select_filters = [
        {"name": "Country", "id": "country", "value": "all"},
        {"name": "Method", "id": "method", "value": "all"},
        {"name": "Status code", "id": "status", "value": "all"},
        {"name": "Reason", "id": "reason", "value": "all"},
    ]

    for item in select_filters:
        DRIVER.execute_script(
            f"""return document.querySelector('[data-reports-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()"""
        )

    filter_input = safe_get_element(DRIVER, By.ID, "keyword")
    assert isinstance(filter_input, WebElement), "Keyword filter input is not a WebElement"
    filter_input.send_keys("abcde")

    with suppress(TimeoutException):
        safe_get_element(DRIVER, By.XPATH, "//ul[@data-reports-list='']/li[not(contains(@class, 'hidden'))]", error=True)
        log_error("The keyword filter is not working, exiting ...")
        exit(1)

    log_info("The reports have been filtered")

    log_info("✅ Reports page tests finished successfully")
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
