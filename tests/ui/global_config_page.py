from logging import info as log_info, exception as log_exception, error as log_error, warning as log_warning
from random import shuffle
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_alert_message, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the global config page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[3]/a", "global config")

    log_info("Looking that tabs are working programmatically ...")

    DRIVER.execute_script(f"""document.querySelector('button[data-tab-handler-mobile="blacklist"]').click()""")
    DRIVER.execute_script(f"""document.querySelector('button[data-tab-handler="general"]').click()""")

    log_info("Trying filters ...")

    # Set keyword with no matching settings
    keyword_no_match = "dqz48 é84 dzq 584dz5qd4"
    btn_keyword = safe_get_element(DRIVER, "js", 'document.querySelector("input#settings-filter")')
    btn_keyword.send_keys(keyword_no_match)
    sleep(0.1)

    # Check that the no matching element is shown and other card hide
    is_no_match = DRIVER.execute_script('return document.querySelector("[data-global-config-nomatch]").classList.contains("hidden")')
    if not is_no_match:
        log_error(f"Filter keyword with value {keyword_no_match} shouldn't match something.")
        exit(1)

    # Reset
    btn_keyword.send_keys("")

    no_errors = True
    retries = 0
    while no_errors:
        try:
            log_info("Trying to save the global config without changing anything ...")
            access_page(DRIVER, "//form[@id='form-edit-global-configs']//button[@type='submit']", "global config", False)

            log_info("The page reloaded successfully, checking the message ...")
            assert_alert_message(DRIVER, "The global configuration was not edited because no values were changed.")

            no_errors = False
        except:
            if retries >= 3:
                exit(1)
            retries += 1
            log_warning("message list doesn't contain the expected message or is empty, retrying...")

    log_info('Checking if the "DATASTORE_MEMORY_SIZE" input have the overridden value ...')

    input_datastore = safe_get_element(DRIVER, By.ID, "DATASTORE_MEMORY_SIZE")
    assert isinstance(input_datastore, WebElement), "Input is not a WebElement"

    if not input_datastore.get_attribute("disabled"):
        log_error('The input "DATASTORE_MEMORY_SIZE" is not disabled, even though it should be, exiting ...')
        exit(1)
    elif input_datastore.get_attribute("value") != "384m":
        log_error(f"The value is not the expected one ({input_datastore.get_attribute('value')} instead of 384m), exiting ...")
        exit(1)

    log_info("The value is the expected one and the input is disabled, trying to edit the global config with wrong values ...")

    input_worker = safe_get_element(DRIVER, By.ID, "WORKER_RLIMIT_NOFILE")
    assert isinstance(input_worker, WebElement), "Input is not a WebElement"

    input_worker.clear()
    input_worker.send_keys("ZZZ")

    assert_button_click(DRIVER, "//form[@id='form-edit-global-configs']//button[@type='submit']")
    assert_alert_message(DRIVER, "The global configuration was not edited because no values were changed.")

    log_info("The form was not submitted, trying to edit the global config with good values ...")

    input_worker.clear()
    input_worker.send_keys("4096")

    access_page(DRIVER, "//form[@id='form-edit-global-configs']//button[@type='submit']", "global config", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    input_worker = safe_get_element(DRIVER, By.ID, "WORKER_RLIMIT_NOFILE")
    assert isinstance(input_worker, WebElement), "Input is not a WebElement"

    if input_worker.get_attribute("value") != "4096":
        log_error(f"The value was not updated ({input_worker.get_attribute('value')} instead of 4096), exiting ...")
        exit(1)

    log_info("The value was updated successfully, trying to navigate through the global config tabs ...")

    buttons = safe_get_element(DRIVER, By.XPATH, "//div[@data-global-config-tabs-desktop='']/button", multiple=True)
    assert isinstance(buttons, list), "Buttons is not a list of WebElements"

    shuffle(buttons)
    for button in buttons:
        assert_button_click(DRIVER, button)

    log_info("Trying to filter the global config ...")

    setting_filter_elem = safe_get_element(DRIVER, By.ID, "settings-filter")
    assert isinstance(setting_filter_elem, WebElement), "Setting filter input is not a WebElement"
    setting_filter_elem.send_keys("Datastore")

    settings = safe_get_element(
        DRIVER,
        By.XPATH,
        "//form[@id='form-edit-global-configs']//div[@data-setting-container='' and not(contains(@class, 'hidden'))]",
        multiple=True,
    )
    assert isinstance(settings, list), "Hidden settings is not a list of WebElements"

    if len(settings) != 1:
        log_error(f"The filter didn't work (found {len(settings)} settings instead of 1), exiting ...")
        exit(1)

    log_info("✅ Global config page tests finished successfully")
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
