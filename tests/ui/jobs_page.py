from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER, UI_URL
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the jobs page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[10]/a", "jobs")

    log_info("Trying to filter jobs ...")

    jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']/li", multiple=True)
    assert isinstance(jobs_list, list), "Jobs list is not a list"

    if len(jobs_list) == 0:
        log_error("No jobs found, exiting ...")
        exit(1)

    filter_input = safe_get_element(DRIVER, By.ID, "keyword")
    assert isinstance(filter_input, WebElement), "Keyword filter input is not a WebElement"
    filter_input.send_keys("abcde")

    with suppress(TimeoutException):
        new_jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True, error=True)
        assert isinstance(new_jobs_list, list), "New jobs list is not a list"
        if len(jobs_list) == len(new_jobs_list):
            log_error("The keyword filter is not working, exiting ...")
            exit(1)

    # Reset
    filter_input.send_keys(Keys.CONTROL, "a")
    filter_input.send_keys(Keys.BACKSPACE)

    # Test select filters
    select_filters = [
        {"name": "Success state", "id": "success", "value": "all"},
        {"name": "Reload state", "id": "reload", "value": "all"},
        {"name": "Run time", "id": "every", "value": "all"},
    ]

    for item in select_filters:
        DRIVER.execute_script(f"""return document.querySelector('[data-jobs-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()""")

    log_info("Keyword filter is working, trying to filter by success state ...")

    assert_button_click(DRIVER, "//button[@data-jobs-setting-select='success']")
    assert_button_click(DRIVER, "//div[@data-jobs-setting-select-dropdown='success']/button[@value='false']")

    with suppress(TimeoutException):
        new_jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True, error=True)
        assert isinstance(new_jobs_list, list), "New jobs list is not a list"
        failed_jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']//p[@data-jobs-success='false']", multiple=True, error=True)
        assert isinstance(failed_jobs_list, list), "Failed jobs list is not a list"
        if len(jobs_list) == len(new_jobs_list) and len(jobs_list) != len(failed_jobs_list):
            log_error("The success filter is not working, exiting ...")
            exit(1)

    assert_button_click(DRIVER, "//button[@data-jobs-setting-select='success']")
    assert_button_click(DRIVER, "//div[@data-jobs-setting-select-dropdown='success']/button[@value='all']")

    log_info("Success filter is working, trying to filter by reload state ...")

    assert_button_click(DRIVER, "//button[@data-jobs-setting-select='reload']")
    assert_button_click(DRIVER, "//div[@data-jobs-setting-select-dropdown='reload']/button[@value='true']")

    with suppress(TimeoutException):
        new_jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']/li[not(contains(@class, 'hidden'))]", multiple=True, error=True)
        assert isinstance(new_jobs_list, list), "New jobs list is not a list"
        reload_jobs_list = safe_get_element(DRIVER, By.XPATH, "//ul[@data-jobs-list='']//p[@data-jobs-reload='true']", multiple=True, error=True)
        assert isinstance(reload_jobs_list, list), "Reload jobs list is not a list"
        if len(jobs_list) == len(new_jobs_list) and len(jobs_list) != len(reload_jobs_list):
            log_error("The reload filter is not working, exiting ...")
            exit(1)

    assert_button_click(DRIVER, "//button[@data-jobs-setting-select='reload']")
    assert_button_click(DRIVER, "//div[@data-jobs-setting-select-dropdown='reload']/button[@value='all']")

    log_info("Reload filter is working, trying jobs cache ...")

    cookie = DRIVER.get_cookies()[0]
    resp = get(
        f"https://www.example.com{UI_URL}/jobs/download?plugin_id=jobs&job_name=mmdb-country&file_name=country.mmdb",
        headers={"Host": "www.example.com", "User-Agent": DRIVER.execute_script("return navigator.userAgent;")},
        cookies={cookie["name"]: cookie["value"]},
        verify=False,
    )

    if resp.status_code != 200:
        log_error("The cache download is not working, exiting ...")
        exit(1)

    log_info("Jobs cache download is working")

    log_info("✅ Jobs page tests finished successfully")
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
