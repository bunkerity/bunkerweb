from logging import info as log_info, exception as log_exception, error as log_error, warning as log_warning

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_alert_message, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the global config page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[3]/a", "global config")

    log_info("Trying filters ...")

    # Set keyword with no matching settings
    input_keyword = safe_get_element(DRIVER, By.ID, "keyword")
    input_keyword.send_keys("dqz48 é84 dzq 584dz5qd4")

    # Check that the no matching element is shown and other card hide
    is_no_match_hidden = DRIVER.execute_script('return document.querySelector("[data-global-config-nomatch]").classList.contains("hidden")')

    if is_no_match_hidden:
        log_error("Filter keyword shouldn't match something.")
        exit(1)

    # Reset
    input_keyword.send_keys(Keys.CONTROL, "a")
    input_keyword.send_keys(Keys.BACKSPACE)

    log_info("Filter with unmatched keyword works as expected, try to match a setting ...")

    input_keyword.send_keys("http port")

    # Check that the matching element is shown and other card hide
    is_http_port_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-http-port').classList.contains('hidden')")

    if is_http_port_hidden:
        log_error("hidden http port should be match.")
        exit(1)

    is_https_port_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-https-port').classList.contains('hidden')")

    if not is_https_port_hidden:
        log_error("Setting https port should not be match.")
        exit(1)

    # Reset
    input_keyword.send_keys(Keys.CONTROL, "a")
    input_keyword.send_keys(Keys.BACKSPACE)

    log_info("Matching a setting done, try context global filter ...")

    select_context = safe_get_element(DRIVER, By.XPATH, "//button[@data-global-config-setting-select='context']")
    assert_button_click(DRIVER, select_context)
    assert_button_click(DRIVER, "//button[@data-global-config-setting-select-dropdown-btn='context' and @value='global']")

    is_server_type_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-server-type').classList.contains('hidden')")

    if not is_server_type_hidden:
        log_error("Setting server type should be hidden.")
        exit(1)

    is_http_port_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-http-port').classList.contains('hidden')")

    if is_http_port_hidden:
        log_error("Setting http port shouldn't be hidden.")
        exit(1)

    log_info("Context global filter working, trying context multisite filter ...")

    select_context = safe_get_element(DRIVER, By.XPATH, "//button[@data-global-config-setting-select='context']")
    assert_button_click(DRIVER, select_context)
    assert_button_click(DRIVER, "//button[@data-global-config-setting-select-dropdown-btn='context' and @value='multisite']")

    is_server_type_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-server-type').classList.contains('hidden')")

    if is_server_type_hidden:
        log_error("Setting server type shouldn't be hidden.")
        exit(1)

    is_http_port_hidden = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-http-port').classList.contains('hidden')")

    if not is_http_port_hidden:
        log_error("Setting http port should be hidden.")
        exit(1)

    select_context = safe_get_element(DRIVER, By.XPATH, "//button[@data-global-config-setting-select='context']")
    assert_button_click(DRIVER, select_context)
    assert_button_click(DRIVER, "//button[@data-global-config-setting-select-dropdown-btn='context' and @value='all']")

    log_info("Context multisite filter working with setting, trying filter with multiple settings using Headers plugin ...")

    select_plugin = safe_get_element(DRIVER, By.XPATH, "//button[@data-tab-select-dropdown-btn='']")
    assert_button_click(DRIVER, select_plugin)
    assert_button_click(DRIVER, "//button[@data-tab-select-handler='headers']")

    log_info("Start keyword to show only one multiple ...")

    input_keyword = safe_get_element(DRIVER, By.ID, "keyword")
    input_keyword.send_keys("custom header")

    is_remove_headers = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-remove-headers').classList.contains('hidden')")

    if not is_remove_headers:
        log_error("Setting remove headers should be hidden.")
        exit(1)

    is_multiple_handle_headers = DRIVER.execute_script(
        """return document.querySelector('[data-multiple-handler="custom-headers"]').classList.contains('hidden')"""
    )

    if is_multiple_handle_headers:
        log_error("Multiple setting custom headers shouldn't be hidden.")
        exit(1)

    is_multiple_handle_cookie_flag = DRIVER.execute_script(
        """return document.querySelector('[data-multiple-handler="cookie-flags"]').classList.contains('hidden')"""
    )

    if not is_multiple_handle_cookie_flag:
        log_error("Multiple setting cookie flags should be hidden.")
        exit(1)

    # Reset
    input_keyword.send_keys(Keys.CONTROL, "a")
    input_keyword.send_keys(Keys.BACKSPACE)

    log_info("Filter to keep only one multiple worked, trying to hide all multiples ...")

    input_keyword.send_keys("remove headers")

    is_remove_headers = DRIVER.execute_script("return document.querySelector('#form-edit-global-config-remove-headers').classList.contains('hidden')")

    if is_remove_headers:
        log_error("Setting remove headers shouldn't be hidden.")
        exit(1)

    is_multiple_handle_headers = DRIVER.execute_script(
        """return document.querySelector('[data-multiple-handler="custom-headers"]').classList.contains('hidden')"""
    )

    if not is_multiple_handle_headers:
        log_error("Multiple setting custom headers should be hidden.")
        exit(1)

    is_multiple_handle_cookie_flag = DRIVER.execute_script(
        """return document.querySelector('[data-multiple-handler="cookie-flags"]').classList.contains('hidden')"""
    )

    if not is_multiple_handle_cookie_flag:
        log_error("Multiple setting cookie flags should be hidden.")
        exit(1)

    # Reset
    input_keyword.send_keys(Keys.CONTROL, "a")
    input_keyword.send_keys(Keys.BACKSPACE)

    log_info("Filter to keep only regular setting and hide all multiple done ...")

    log_info("Filters working, trying settings interaction, start with multiple settings ...")

    DRIVER.execute_script("""document.querySelector('[data-global-config-multiple-add="custom-headers"]').click()""")
    DRIVER.execute_script("""document.querySelector('[data-global-config-multiple-toggle="custom-headers"]').click()""")
    DRIVER.execute_script("""document.querySelector('[data-global-config-multiple-toggle="custom-headers"]').click()""")
    DRIVER.execute_script("""document.querySelector('[data-global-config-multiple-delete="Headers"]').click()""")

    log_info("Multiple settings interaction worked, trying general settings ...")

    select_plugin = safe_get_element(DRIVER, By.XPATH, "//button[@data-tab-select-dropdown-btn='']")
    assert_button_click(DRIVER, select_plugin)
    assert_button_click(DRIVER, "//button[@data-tab-select-handler='general']")

    log_info("Select from dropdown ...")

    select = safe_get_element(DRIVER, By.XPATH, "//button[@data-setting-select='timers-log-level']")
    assert_button_click(DRIVER, select)

    select_active_item = safe_get_element(DRIVER, By.XPATH, "//button[@data-setting-select-dropdown-btn='timers-log-level' and contains(@class, 'active')]")
    assert_button_click(DRIVER, select_active_item)

    log_info("Select dropdown done, trying toggle checkbox...")

    checkbox_api = safe_get_element(DRIVER, By.ID, "USE_API")
    assert_button_click(DRIVER, checkbox_api)
    assert_button_click(DRIVER, checkbox_api)

    log_info("Toggle checkbox done, trying to update global config ...")

    no_errors = True
    retries = 0
    while no_errors:
        try:
            log_info("Trying to save the global config without changing anything ...")
            access_page(DRIVER, "//form[@id='form-edit-global-config']//button[@type='submit']", "global config", False)

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

    # Reset
    input_worker.send_keys(Keys.CONTROL, "a")
    input_worker.send_keys(Keys.BACKSPACE)

    input_worker.send_keys("ZZZ")

    assert_button_click(DRIVER, "//form[@id='form-edit-global-config']//button[@type='submit']")
    assert_alert_message(DRIVER, "The global configuration was not edited because no values were changed.")

    log_info("The form was not submitted, trying to edit the global config with good values ...")

    # Reset
    input_worker.send_keys(Keys.CONTROL, "a")
    input_worker.send_keys(Keys.BACKSPACE)

    input_worker.send_keys("4096")

    access_page(DRIVER, "//form[@id='form-edit-global-config']//button[@type='submit']", "global config", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    input_worker = safe_get_element(DRIVER, By.ID, "WORKER_RLIMIT_NOFILE")
    assert isinstance(input_worker, WebElement), "Input is not a WebElement"

    if input_worker.get_attribute("value") != "4096":
        log_error(f"The value was not updated ({input_worker.get_attribute('value')} instead of 4096), exiting ...")
        exit(1)

    log_info("The value was updated successfully, trying to select all plugins ...")

    # Open dropdown to select all plugins and click on them
    buttons_plugin = DRIVER.execute_script('return document.querySelectorAll("button[data-tab-select-handler]")')

    for button in buttons_plugin:
        DRIVER.execute_script("arguments[0].click()", button)

    log_info("Selecting all plugins worked ...")

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
