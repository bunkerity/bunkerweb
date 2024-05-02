from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from pathlib import Path
from time import sleep
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER, UI_URL
from base import TEST_TYPE
from utils import access_page, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the plugins page to create a new service ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[6]/a", "plugins")

    for _ in range(5):
        get(f"http://www.example.com{UI_URL}/?id=/etc/passwd")
        sleep(1)

    sleep(7)

    log_info("Trying to reload the plugins without adding any ...")

    reload_button = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-upload='']//button[@type='submit']")
    assert isinstance(reload_button, WebElement), "Reload button is not a WebElement"
    if reload_button.get_attribute("disabled") is None:
        log_error("The reload button is not disabled, exiting ...")
        exit(1)

    log_info("Trying to filter the plugins ...")

    # Get total plugins
    plugins = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-type]", multiple=True)
    plugins_total = len(plugins)

    key_word_filter_input = safe_get_element(DRIVER, "js", 'document.querySelector("input#keyword")')
    assert isinstance(key_word_filter_input, WebElement), "Key word filter input is not a WebElement"
    key_word_filter_input.send_keys("Antibot")

    plugins_hidden = safe_get_element(DRIVER, "js", 'document.querySelectorAll("[data-plugins-type][class*=hidden]")')

    if len(plugins_hidden) == 0:
        log_error("The keyword filter is not working, exiting ...")
        exit(1)

    # Reset
    key_word_filter_input.send_keys(Keys.CONTROL, "a")
    key_word_filter_input.send_keys(Keys.BACKSPACE)

    # Test select filters
    select_filters = [
        {"name": "Types", "id": "types", "value": "all"},
    ]

    for item in select_filters:
        DRIVER.execute_script(
            f"""return document.querySelector('[data-plugins-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()"""
        )

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

    external_plugins = safe_get_element(DRIVER, By.XPATH, "//div[@data-plugins-type='external']", multiple=True)
    assert isinstance(external_plugins, list), "External plugins list is not a list"

    if len(external_plugins) != 1:
        log_error("The plugin hasn't been added, exiting ...")
        exit(1)

    log_info("The plugin has been added, trying delete it ...")

    assert_button_click(DRIVER, "//button[@data-plugins-action='delete' and @name='discord']")

    access_page(DRIVER, "//form[@data-plugins-modal-form-delete='']//button[@type='submit']", "plugins", False)

    sleep(30)

    if TEST_TYPE == "linux":
        wait_for_service()

    with suppress(TimeoutException):
        if safe_get_element(DRIVER, By.XPATH, "//button[@data-plugins-action='delete' and @name='discord']", error=True):
            log_error("The plugin hasn't been deleted, exiting ...")
            exit(1)

    log_info("The plugin has been deleted")

    DEACTIVATED_PLUGINS = ("antibot", "blacklist", "bunkernet", "cors", "country", "greylist", "redis", "reversescan")
    for plugin in DEACTIVATED_PLUGINS:
        log_info(f"Trying {plugin} plugin page ...")
        DRIVER.get(f"http://www.example.com{UI_URL}/plugins/{plugin}")
        first_card = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/div/div[1]/h5")
        assert isinstance(first_card, WebElement), "First card is not a WebElement"

        if first_card.text != "Plugin deactivated":
            log_error(f"The {plugin} page should show that the plugin is deactivated, exiting ...")
            exit(1)

        log_info(f"{plugin} page shows that the plugin is deactivated, as expected")
        DRIVER.back()

    log_info("Trying bad behavior plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/badbehavior")

    sleep(5)

    badbehavior_list = safe_get_element(DRIVER, By.XPATH, '//li[@class="core-card-list-item"]', multiple=True)
    assert isinstance(badbehavior_list, list), "Bad behavior list is not a list"

    found_403 = False
    for item in badbehavior_list:
        if "403" in item.text:
            found_403 = True
            break

    if not found_403:
        log_error("Bad behavior list doesn't show 403, exiting ...")
        exit(1)

    log_info("Bad behavior list shows 403, as expected")
    DRIVER.back()

    log_info("Trying dnsbl plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/dnsbl")

    sleep(5)

    dnsbl_count = safe_get_element(DRIVER, By.XPATH, '//h5[@data-count=""]')
    assert isinstance(dnsbl_count, WebElement), "DNSBL count is not a WebElement"

    if dnsbl_count.text != "0":
        log_error("DNSBL count is not 0, exiting ...")
        exit(1)

    log_info("DNSBL count is 0, as expected")
    DRIVER.back()

    log_info("Trying errors plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/errors")

    sleep(5)

    errors_list = safe_get_element(DRIVER, By.XPATH, '//li[@class="core-card-list-item"]', multiple=True)
    assert isinstance(errors_list, list), "Errors list is not a list"

    found_403 = False
    for item in errors_list:
        if "403" in item.text:
            found_403 = True
            break

    if not found_403:
        log_error("Errors list doesn't show 403, exiting ...")
        exit(1)

    log_info("Errors list shows 403, as expected")
    DRIVER.back()

    log_info("Trying limit plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/limit")

    limit_info_elem = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/div[1]/h5")
    assert isinstance(limit_info_elem, WebElement), "Limit info element is not a WebElement"

    if limit_info_elem.text != "INFO":
        log_error("Limit page doesn't show the limit, exiting ...")
        exit(1)

    log_info("Limit page is shown, as expected")
    DRIVER.back()

    log_info("Trying miscellaneous plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/misc")

    sleep(5)

    misc_disallowed_count = safe_get_element(
        DRIVER, By.XPATH, '//p[@class="core-card-metrics-name" and contains(text(), "DISALLOWED METHODS")]/following-sibling::h5[@data-count=""]'
    )
    assert isinstance(misc_disallowed_count, WebElement), "Miscellaneous disallowed count is not a WebElement"

    if misc_disallowed_count.text != "0":
        log_error("Miscellaneous disallowed count is not 0, exiting ...")
        exit(1)

    log_info("Miscellaneous disallowed count is 0, as expected")
    DRIVER.back()

    log_info("Trying whitelist plugin page ...")
    DRIVER.get(f"http://www.example.com{UI_URL}/plugins/whitelist")

    sleep(5)

    dnsbl_count = safe_get_element(DRIVER, By.XPATH, '//h5[@data-count=""]')
    assert isinstance(dnsbl_count, WebElement), "Whitelist count is not a WebElement"

    if dnsbl_count.text != "0":
        log_error("Whitelist count is not 0, exiting ...")
        exit(1)

    log_info("Whitelist count is 0, as expected")

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
