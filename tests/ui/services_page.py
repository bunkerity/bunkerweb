from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error
from time import sleep
from requests import RequestException, get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_alert_message, assert_button_click, safe_get_element, wait_for_service, verify_select_filters

exit_code = 0


try:
    log_info("Navigating to the services page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[4]/a", "services")

    service_name_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='www.example.com']//h5")
    assert isinstance(service_name_elem, WebElement), "Service name element is not a WebElement"
    if service_name_elem.text.strip() != "www.example.com":
        log_error("The service is not present, exiting ...")
        exit(1)

    service_method_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='www.example.com']//h6")
    assert isinstance(service_method_elem, WebElement), "Service method element is not a WebElement"
    if service_method_elem.text.strip() != "ui":
        log_error("The service should have been created by the ui, exiting ...")
        exit(1)

    log_info("Service www.example.com is present, trying to edit it ...")

    assert_button_click(DRIVER, "//div[@data-services-service='www.example.com']//button[@data-services-action='edit']")

    modal = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-modal='']")
    assert isinstance(modal, WebElement), "Modal is not a WebElement"
    if "hidden" in (modal.get_attribute("class") or ""):
        log_error("Modal is hidden even though it shouldn't be, exiting ...")
        exit(1)

    input_server_name = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(input_server_name, WebElement), "Input is not a WebElement"
    if input_server_name.get_attribute("value") != "www.example.com":
        log_error("The value is not the expected one, exiting ...")
        exit(1)

    log_info('The value for the "SERVER_NAME" input is the expected one, trying to edit the config ...')

    assert_button_click(DRIVER, "//button[@data-tab-handler='gzip']")
    gzip_select = safe_get_element(DRIVER, By.XPATH, "//button[@data-setting-select='gzip-comp-level']")
    assert isinstance(gzip_select, WebElement), "Gzip select is not a WebElement"
    assert_button_click(DRIVER, gzip_select)

    assert_button_click(DRIVER, "//button[@data-setting-select-dropdown-btn='gzip-comp-level' and @value='6']")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    log_info("The page reloaded successfully, checking if the setting has been updated ...")

    assert_button_click(DRIVER, "//div[@data-services-service='www.example.com']//button[@data-services-action='edit']")

    modal = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-modal='']")
    assert isinstance(modal, WebElement), "Modal is not a WebElement"
    if "hidden" in (modal.get_attribute("class") or ""):
        log_error("Modal is hidden even though it shouldn't be, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-tab-handler='gzip']")

    gzip_comp_level_selected_elem = safe_get_element(DRIVER, By.XPATH, "//select[@id='GZIP_COMP_LEVEL']/option[@selected='']")
    assert isinstance(gzip_comp_level_selected_elem, WebElement), "Gzip comp level selected element is not a WebElement"
    if gzip_comp_level_selected_elem.get_attribute("value") != "6":
        log_error("The value is not the expected one, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-services-modal-close='']/*[local-name() = 'svg']")

    log_info("Creating a new service ...")

    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    server_name_input = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    server_name_input.clear()
    server_name_input.send_keys("app1.example.com")

    if TEST_TYPE == "docker":
        assert_button_click(DRIVER, "//button[@data-tab-handler='reverseproxy']")

        use_reverse_proxy_checkbox = safe_get_element(DRIVER, By.ID, "USE_REVERSE_PROXY")
        assert isinstance(use_reverse_proxy_checkbox, WebElement), "Use reverse proxy checkbox is not a WebElement"
        assert_button_click(DRIVER, use_reverse_proxy_checkbox)

        reverse_proxy_host_input = safe_get_element(DRIVER, By.ID, "REVERSE_PROXY_HOST")
        assert isinstance(reverse_proxy_host_input, WebElement), "Reverse proxy host input is not a WebElement"
        reverse_proxy_host_input.send_keys("http://app1:8080")

        reverse_proxy_url_input = safe_get_element(DRIVER, By.ID, "REVERSE_PROXY_URL")
        assert isinstance(reverse_proxy_url_input, WebElement), "Reverse proxy url input is not a WebElement"
        reverse_proxy_url_input.send_keys("/")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service("app1.example.com")

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service]", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) < 2:
        log_error("The service hasn't been created, exiting ...")
        exit(1)

    server_name_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app1.example.com']//h5")
    assert isinstance(server_name_elem, WebElement), "Server name element is not a WebElement"
    if server_name_elem.text.strip() != "app1.example.com":
        log_error('The service "app1.example.com" is not present, exiting ...')
        exit(1)

    service_method_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app1.example.com']//h6")
    assert isinstance(service_method_elem, WebElement), "Service method element is not a WebElement"
    if service_method_elem.text.strip() != "ui":
        log_error("The service should have been created by the ui, exiting ...")
        exit(1)

    log_info("Service app1.example.com is present, trying it ...")

    try:
        safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='edit' and @data-services-name='app1.example.com']//ancestor::div//a", error=True)
    except TimeoutException:
        log_exception("Delete button hasn't been found, even though it should be, exiting ...")
        exit(1)

    wait_for_service("app1.example.com")

    log_info("The service is working, trying to clone it ...")

    try:
        clone_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='clone' and @data-services-name='app1.example.com']", error=True)
        assert isinstance(clone_button, WebElement), "Clone button is not a WebElement"
    except TimeoutException:
        log_exception("Clone button hasn't been found, even though it should be, exiting ...")
        exit(1)

    assert_button_click(DRIVER, clone_button)

    server_name_input = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    if server_name_input.get_attribute("value"):
        log_error("The cloned service input is not empty, exiting ...")
        exit(1)

    server_name_input.clear()
    server_name_input.send_keys("app2.example.com")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service("app2.example.com")

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service]", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) < 3:
        log_error(f"The service hasn't been created ({len(services)} services found), exiting ...")
        exit(1)

    server_name_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app2.example.com']//h5")
    assert isinstance(server_name_elem, WebElement), "Server name element is not a WebElement"
    if server_name_elem.text.strip() != "app2.example.com":
        log_error('The service "app2.example.com" is not present, exiting ...')
        exit(1)

    service_method_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app2.example.com']//h6")
    assert isinstance(service_method_elem, WebElement), "Service method element is not a WebElement"
    if service_method_elem.text.strip() != "ui":
        log_error("The service should have been created by the ui, exiting ...")
        exit(1)

    log_info("Service app2.example.com is present, trying it ...")

    try:
        safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='edit' and @data-services-name='app2.example.com']//ancestor::div//a", error=True)
    except TimeoutException:
        log_error("Delete button hasn't been found, even though it should be, exiting ...")
        exit(1)

    wait_for_service("app2.example.com")

    log_info("The service is working, trying to set it as draft ...")

    assert_button_click(DRIVER, "//div[@data-services-service='app2.example.com']//button[@data-services-action='edit']")

    assert_button_click(DRIVER, "//button[@data-toggle-draft-btn='']")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service]", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) < 3:
        log_error(f"The service has been deleted ({len(services)} services found), exiting ...")
        exit(1)

    sleep(30)

    log_info("Service app2.example.com has been set as draft, making sure it's not working anymore ...")

    for _ in range(5):
        with suppress(RequestException):
            if get("http://app2.example.com").status_code < 400:
                log_error("The service is still working, exiting ...")
                exit(1)

    log_info("Create another service app3.example.com to get filters (need at least 4 services on page)")

    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    server_name_input = safe_get_element(DRIVER, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    server_name_input.clear()
    server_name_input.send_keys("app3.example.com")

    access_page(DRIVER, "//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service("app3.example.com")

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service]", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) < 4:
        log_error(f"The service hasn't been created ({len(services)} services found), exiting ...")
        exit(1)

    server_name_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app3.example.com']//h5")
    assert isinstance(server_name_elem, WebElement), "Server name element is not a WebElement"
    if server_name_elem.text.strip() != "app3.example.com":
        log_error('The service "app3.example.com" is not present, exiting ...')
        exit(1)

    service_method_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='app3.example.com']//h6")
    assert isinstance(service_method_elem, WebElement), "Service method element is not a WebElement"
    if service_method_elem.text.strip() != "ui":
        log_error("The service should have been created by the ui, exiting ...")
        exit(1)

    log_info("Service app3.example.com is present, trying filters...")

    # Set keyword with no matching settings
    keyword_no_match = "dqz48 é84 dzq 584dz5qd4"
    btn_keyword = safe_get_element(DRIVER, "js", 'document.querySelector("button#service-name-keyword")')
    btn_keyword.send_keys(keyword_no_match)
    sleep(0.1)

    # Check that the no matching element is shown and other card hide
    is_no_match = DRIVER.execute_script('return document.querySelector("[data-services-nomatch-card]").classList.contains("hidden") ? false : true')
    if not is_no_match:
        log_error(f"Filter keyword with value {keyword_no_match} shouldn't match something.")
        exit(1)

    # Reset
    btn_keyword.send_keys("")

    # Test select filters
    select_filters = [
        {"name": "Method", "id": "method", "value": "all", "update_value": "123456"},
        {"name": "State", "id": "state", "value": "all", "update_value": "123456"},
    ]

    verify_select_filters(DRIVER, "services", select_filters)

    log_info("Filters working as expected, trying to delete app2.example.com ...")

    try:
        delete_button = safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='delete' and @data-services-name='app2.example.com']", error=True)
        assert isinstance(delete_button, WebElement), "Delete button is not a WebElement"
    except TimeoutException:
        log_exception("Delete button hasn't been found, even though it should be, exiting ...")
        exit(1)

    log_info("Delete button is present, as expected, deleting the service ...")

    assert_button_click(DRIVER, delete_button)

    access_page(DRIVER, "//form[@data-services-modal-form-delete='']//button[@type='submit']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    assert_alert_message(DRIVER, "has been deleted.")

    log_info("Service app2.example.com has been deleted, checking if it's still present ...")

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='']", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) > 2:
        log_error(f"The service hasn't been deleted ({len(services)} services found), exiting ...")
        exit(1)

    log_info("Service app2.example.com has been deleted successfully")

    log_info("✅ Services page tests finished successfully")
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
