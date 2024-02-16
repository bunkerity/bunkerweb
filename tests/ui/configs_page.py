from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from time import sleep
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_alert_message, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the services page to create a new service ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[4]/a", "services")

    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    server_name_input = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    server_name_input.clear()
    server_name_input.send_keys("app1.example.com")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service("app1.example.com")

    log_info("Navigating to the configs page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[5]/a", "configs")

    log_info("Trying to create a new config ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//li[@data-configs-add-file='']/button")

    configs_modal_path_input = safe_get_element(DRIVER, By.XPATH, "//div[@data-configs-modal-path='']/input")
    assert isinstance(configs_modal_path_input, WebElement), "The path input is not an instance of WebElement"
    configs_modal_path_input.send_keys("hello")

    configs_modal_editor_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-configs-modal-editor='']/textarea")
    assert isinstance(configs_modal_editor_elem, WebElement), "The editor element is not an instance of WebElement"
    configs_modal_editor_elem.send_keys(
        """
location /hello {
    default_type 'text/plain';
    content_by_lua_block {
        ngx.say('hello app1')
    }
}"""
    )

    access_page(DRIVER, "//button[@data-configs-modal-submit='']", "configs", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    assert_alert_message(DRIVER, "was successfully created")

    sleep(10)

    DRIVER.execute_script("window.open('http://www.example.com/hello','_blank');")
    DRIVER.switch_to.window(DRIVER.window_handles[1])
    DRIVER.switch_to.default_content()

    try:
        pre_elem = safe_get_element(DRIVER, By.XPATH, "//pre", error=True)
        assert isinstance(pre_elem, WebElement), "The pre element is not an instance of WebElement"
        if pre_elem.text.strip() != "hello app1":
            log_error("The config hasn't been created correctly, exiting ...")
            exit(1)
    except TimeoutException:
        log_info("The config hasn't been created, exiting ...")
        exit(1)

    DRIVER.execute_script("window.open('http://app1.example.com/hello','_blank');")
    DRIVER.switch_to.window(DRIVER.window_handles[1])
    DRIVER.switch_to.default_content()

    try:
        pre_elem = safe_get_element(DRIVER, By.XPATH, "//pre", error=True)
        assert isinstance(pre_elem, WebElement), "The pre element is not an instance of WebElement"
        if pre_elem.text.strip() != "hello app1":
            log_error("The config hasn't been created correctly, exiting ...")
            exit(1)
    except TimeoutException:
        log_info("The config hasn't been created, exiting ...")
        exit(1)

    log_info("The config has been created and is working with both services, trying to delete it ...")

    for _ in range(2):
        DRIVER.close()
        DRIVER.switch_to.window(DRIVER.window_handles[len(DRIVER.window_handles) - 1])

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//div[@data-configs-action-button='hello.conf']")
    assert_button_click(DRIVER, "//div[@data-configs-action-dropdown='hello.conf']/button[@value='delete' and @data-configs-action-dropdown-btn='hello.conf']")

    access_page(DRIVER, "//button[@data-configs-modal-submit='']", "configs", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    assert_alert_message(DRIVER, "was successfully deleted")

    sleep(10)

    resp = get("http://www.example.com/hello")

    if resp.status_code != 404:
        log_error("The config hasn't been deleted correctly, exiting ...")
        exit(1)

    log_info("The config has been deleted, trying the same for a specific service ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//div[@data-path='/etc/bunkerweb/configs/server-http/app1.example.com' and @data-_type='folder']")
    assert_button_click(DRIVER, "//li[@data-configs-add-file='']/button")

    configs_modal_path_input = safe_get_element(DRIVER, By.XPATH, "//div[@data-configs-modal-path='']/input")
    assert isinstance(configs_modal_path_input, WebElement), "The path input is not an instance of WebElement"
    configs_modal_path_input.send_keys("hello")

    configs_modal_editor_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-configs-modal-editor='']/textarea")
    assert isinstance(configs_modal_editor_elem, WebElement), "The editor element is not an instance of WebElement"
    configs_modal_editor_elem.send_keys(
        """
location /hello {
    default_type 'text/plain';
    content_by_lua_block {
        ngx.say('hello app1')
    }
}"""
    )

    access_page(DRIVER, "//button[@data-configs-modal-submit='']", "configs", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    assert_alert_message(DRIVER, "was successfully created")

    sleep(10)

    DRIVER.execute_script("window.open('http://app1.example.com/hello','_blank');")
    DRIVER.switch_to.window(DRIVER.window_handles[1])
    DRIVER.switch_to.default_content()

    try:
        pre_elem = safe_get_element(DRIVER, By.XPATH, "//pre", error=True)
        assert isinstance(pre_elem, WebElement), "The pre element is not an instance of WebElement"
        if pre_elem.text.strip() != "hello app1":
            log_error("The config hasn't been created correctly, exiting ...")
            exit(1)
    except TimeoutException:
        log_info("The config hasn't been created, exiting ...")
        exit(1)

    DRIVER.close()
    DRIVER.switch_to.window(DRIVER.window_handles[0])

    resp = get("http://www.example.com/hello")

    if resp.status_code != 404:
        log_error("The config didn't get created only for the app1.example.com service, exiting ...")
        exit(1)

    log_info("The config has been created only for the app1.example.com service, trying to delete the service to see if the config gets deleted ...")

    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[4]/a", "services")

    assert_button_click(DRIVER, "//button[@data-services-action='delete' and @data-services-name='app1.example.com']")

    access_page(DRIVER, "//form[@data-services-modal-form-delete='']//button[@type='submit']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    log_info("The service has been deleted, checking if the config has been deleted as well ...")

    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[5]/a", "configs")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")

    with suppress(TimeoutException):
        safe_get_element(DRIVER, By.XPATH, "//div[@data-configs-element='app2.example.com' and @data-_type='folder']", error=True)
        log_error("The config hasn't been deleted, exiting ...")
        exit(1)

    log_info("The config has been deleted")

    log_info("✅ Configs page tests finished successfully")
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
