from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from time import sleep
from requests import get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_alert_message, assert_button_click, safe_get_element, wait_for_service

exit_code = 0

try:
    log_info("Navigating to the services page to create a new service ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[4]/a", "services")

    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    # assert_button_click(DRIVER, "//button[@data-toggle-settings-mode-btn='simple']")

    server_name_input = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    # Reset
    server_name_input.send_keys(Keys.CONTROL, "a")
    server_name_input.send_keys(Keys.BACKSPACE)

    server_name_input.send_keys("app1.example.com")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    wait_for_service("app1.example.com")

    log_info("Navigating to the configs page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[5]/a", "configs")

    DRIVER.refresh()

    log_info("Trying to create a new config ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//button[@data-configs-add-file='']")

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

    assert_alert_message(DRIVER, "Created")

    sleep(5)

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

    log_info("The config has been created and is working with both services, trying filters ... ...")

    for _ in range(2):
        DRIVER.close()
        DRIVER.switch_to.window(DRIVER.window_handles[len(DRIVER.window_handles) - 1])

    log_info("Check path with conf only filter ...")

    assert_button_click(DRIVER, "//button[@data-configs-setting-select='withconf']")
    assert_button_click(DRIVER, "//button[@data-configs-setting-select-dropdown-btn='withconf' and @value='true']")

    is_server_http_folder_hidden = DRIVER.execute_script(
        """return document.querySelector("[data-configs-element='server-http']").classList.contains("hidden")"""
    )

    if is_server_http_folder_hidden:
        log_error("Server http folder should be visible.")
        exit(1)

    is_http_folder_hidden = DRIVER.execute_script("""return document.querySelector("[data-configs-element='http']").classList.contains("hidden")""")

    if not is_http_folder_hidden:
        log_error("Http folder should be hidden.")
        exit(1)

    # Reset
    assert_button_click(DRIVER, "//button[@data-configs-setting-select='withconf']")
    assert_button_click(DRIVER, "//button[@data-configs-setting-select-dropdown-btn='withconf' and @value='false']")

    log_info("Check path with conf only filter done, check show global conf only ...")

    assert_button_click(DRIVER, "//button[@data-configs-setting-select='globalconf']")
    assert_button_click(DRIVER, "//button[@data-configs-setting-select-dropdown-btn='globalconf' and @value='true']")
    assert_button_click(DRIVER, "//div[@data-configs-element='http' and @data-_type='folder']")

    is_app1_example_com_folder_hidden = DRIVER.execute_script(
        """return document.querySelector("[data-configs-element='app1.example.com']").classList.contains("hidden")"""
    )

    if not is_app1_example_com_folder_hidden:
        log_error("app1.example.com folder should be hidden.")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-configs-setting-select='globalconf']")
    assert_button_click(DRIVER, "//button[@data-configs-setting-select-dropdown-btn='globalconf' and @value='false']")

    log_info("Check show global conf only  done...")

    log_info("Filters working, trying breadcrumb ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//li[@data-configs-breadcrumb-item]")
    assert_button_click(DRIVER, "//div[@data-configs-element='http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//li[@data-configs-breadcrumb-item and @data-level='0']/button")

    log_info("Breadcrumb working, trying to delete the config ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//div[@data-configs-action-button='hello.conf']")
    assert_button_click(DRIVER, "//div[@data-configs-action-dropdown='hello.conf']/button[@value='delete' and @data-configs-action-dropdown-btn='hello.conf']")

    access_page(DRIVER, "//button[@data-configs-modal-submit='']", "configs", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    assert_alert_message(DRIVER, "Deleted")

    DRIVER.refresh()

    sleep(5)

    resp = get("http://www.example.com/hello", verify=False)

    if resp.status_code != 404:
        log_error("The config hasn't been deleted correctly, exiting ...")
        exit(1)

    DRIVER.refresh()

    log_info("The config has been deleted, trying the same for a specific service ...")

    assert_button_click(DRIVER, "//div[@data-configs-element='server-http' and @data-_type='folder']")
    assert_button_click(DRIVER, "//div[@data-path='/etc/bunkerweb/configs/server-http/app1.example.com' and @data-_type='folder']")
    assert_button_click(DRIVER, "//button[@data-configs-add-file='']")

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

    assert_alert_message(DRIVER, "Created")

    sleep(5)

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

    resp = get("http://www.example.com/hello", verify=False)

    if resp.status_code != 404:
        log_error("The config didn't get created only for the app1.example.com service, exiting ...")
        exit(1)

    log_info("The config has been created only for the app1.example.com service, trying to delete the service to see if the config gets deleted ...")

    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[4]/a", "services")

    assert_button_click(DRIVER, "//button[@data-services-action='delete' and @data-services-name='app1.example.com']")
    access_page(DRIVER, "//form[@data-services-modal-form-delete='']//button[@type='submit']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    log_info("The service has been deleted, checking if the config has been deleted as well ...")

    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[5]/a", "configs")

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
