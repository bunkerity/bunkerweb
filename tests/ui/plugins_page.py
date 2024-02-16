from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the plugins page to create a new service ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[6]/a", "plugins")

    log_info("Trying to reload the plugins without adding any ...")

    reload_button = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-upload='']//button[@type='submit']")
    assert isinstance(reload_button, WebElement), "Reload button is not a WebElement"
    if reload_button.get_attribute("disabled") is None:
        log_error("The reload button is not disabled, exiting ...")
        exit(1)

    log_info("Trying to filter the plugins ...")

    key_word_filter_input = safe_get_element(DRIVER, By.XPATH, "//input[@placeholder='key words']")
    assert isinstance(key_word_filter_input, WebElement), "Key word filter input is not a WebElement"
    key_word_filter_input.send_keys("Anti")

    plugins = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-list='']", multiple=True)
    assert isinstance(plugins, list), "Plugins list is not a list"

    if len(plugins) != 1:
        log_error("The filter is not working, exiting ...")
        exit(1)

    log_info("The filter is working, trying to add a bad plugin ...")

    file_input = safe_get_element(DRIVER, By.XPATH, "//input[@type='file' and @name='file']")
    assert isinstance(file_input, WebElement), "File input is not a WebElement"
    file_input.send_keys(Path.cwd().joinpath("test.zip").as_posix())

    access_page(DRIVER, "//div[@data-plugins-upload='']//button[@type='submit']", "plugins", False)

    log_info("The bad plugin has been rejected, trying to add a good plugin ...")

    file_input = safe_get_element(DRIVER, By.XPATH, "//input[@type='file' and @name='file']")
    assert isinstance(file_input, WebElement), "File input is not a WebElement"
    file_input.send_keys(Path.cwd().joinpath("discord.zip").as_posix())

    access_page(DRIVER, "//div[@data-plugins-upload='']//button[@type='submit']", "plugins", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    external_plugins = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-external=' external ']", multiple=True)
    assert isinstance(external_plugins, list), "External plugins list is not a list"

    if len(external_plugins) != 1:
        log_error("The plugin hasn't been added, exiting ...")
        exit(1)

    log_info("The plugin has been added, trying delete it ...")

    assert_button_click(DRIVER, "//button[@data-plugins-action='delete' and @name='discord']")

    access_page(DRIVER, "//form[@data-plugins-modal-form-delete='']//button[@type='submit']", "plugins", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    with suppress(TimeoutException):
        if safe_get_element(DRIVER, By.XPATH, "//button[@data-plugins-action='delete' and @name='discord']", error=True):
            log_error("The plugin hasn't been deleted, exiting ...")
            exit(1)

    log_info("The plugin has been deleted")

    # TODO add test for plugin pages

    log_info("✅ Plugins page tests finished successfully")
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
