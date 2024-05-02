from contextlib import suppress
from logging import info as log_info, exception as log_exception, error as log_error, warning as log_warning
from time import sleep
from requests import RequestException, get

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException


from wizard import DRIVER
from base import TEST_TYPE
from utils import access_page, assert_button_click, safe_get_element, wait_for_service

exit_code = 0


try:
    log_info("Navigating to the services page ...")

    access_page(DRIVER, "/html/body/aside[1]/div[2]/ul[1]/li[4]/a", "services")

    log_info("Check if default www.example.com service is here ...")

    service_name_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='www.example.com']//h5")
    assert isinstance(service_name_elem, WebElement), "Service name element is not a WebElement"
    if service_name_elem.text.strip() != "www.example.com":
        log_error("The service is not present, exiting ...")
        exit(1)

    log_info("Service correctly checked, check if right method ...")

    service_method_elem = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='www.example.com']//h6")
    assert isinstance(service_method_elem, WebElement), "Service method element is not a WebElement"
    if service_method_elem.text.strip() != "ui":
        log_error("The service should have been created by the ui, exiting ...")
        exit(1)

    log_info("Service method 'ui' correctly checked, additional check ...")

    assert_button_click(DRIVER, "//div[@data-services-service='www.example.com']//button[@data-services-action='edit']")

    modal = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-modal='']")
    assert isinstance(modal, WebElement), "Modal is not a WebElement"
    if "hidden" in (modal.get_attribute("class") or ""):
        log_error("Modal is hidden even though it shouldn't be, exiting ...")
        exit(1)

    log_info("Service edit modal checked ...")

    input_server_name = safe_get_element(DRIVER, By.XPATH, "//input[@id='SERVER_NAME']")
    assert isinstance(input_server_name, WebElement), "Input is not a WebElement"
    if input_server_name.get_attribute("value") != "www.example.com":
        log_error("The value is not the expected one, exiting ...")
        exit(1)

    log_info("Input service checked ...")

    assert_button_click(DRIVER, "//button[@data-services-modal-close='']")
    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    log_info("Toggle modal checked, trying settings ...")

    assert_button_click(DRIVER, "//button[@data-toggle-settings-mode-btn='simple']")

    log_info("Start trying combobox filter ...")

    # Open plugins select
    DRIVER.execute_script("""document.querySelector('button[data-tab-select-dropdown-btn]').click()""")

    select_combobox = safe_get_element(DRIVER, By.XPATH, "//input[@data-combobox='']")
    assert isinstance(select_combobox, WebElement), "Combobox is not a WebElement"
    # Test simulate keyboard from js
    DRIVER.execute_script(
        "arguments[0].value = 'no plugin matching normally'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));",
        select_combobox,
    )

    # All tabs should be hidden
    total_tabs = DRIVER.execute_script("""return document?.querySelector('[data-tab-select-dropdown]')?.querySelectorAll('[data-tab-select-handler]').length""")
    hidden_tabs = DRIVER.execute_script(
        """return document?.querySelector('[data-tab-select-dropdown]')?.querySelectorAll('button[data-tab-select-handler][class*="hidden"]').length"""
    )

    if total_tabs != hidden_tabs:
        log_error("All tabs should be hidden.")
        exit(1)

    # Reset
    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", select_combobox)

    # Show only one tab
    DRIVER.execute_script(
        "arguments[0].value = 'blacklist'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", select_combobox
    )

    hidden_tabs = DRIVER.execute_script(
        """return document?.querySelector('[data-tab-select-dropdown]')?.querySelectorAll('button[data-tab-select-handler][class*="hidden"]').length"""
    )

    if hidden_tabs != total_tabs - 1:
        log_error("Only one tab should be visible.")
        exit(1)

    # Click on the visible tab
    DRIVER.execute_script("""document.querySelector('button[data-tab-select-handler="blacklist"]').click()""")

    sleep(1)

    # Reopen select and check if combobox input is empty
    DRIVER.execute_script("""document.querySelector('button[data-tab-select-dropdown-btn]').click()""")
    combo_value = select_combobox.get_property("value")

    if combo_value:
        log_error("Combobox input should be empty.")
        exit(1)

    hidden_tabs = DRIVER.execute_script(
        """return document?.querySelector('[data-tab-select-dropdown]')?.querySelectorAll('button[data-tab-select-handler][class*="hidden"]').length"""
    )

    if hidden_tabs:
        log_error("All tabs should be visible.")
        exit(1)

    # Reset to general
    DRIVER.execute_script("""document.querySelector('button[data-tab-select-handler="general"]').click()""")

    log_info("Combobox filtering done, trying filter keywords ...")

    log_info("Check only one plugin is visible ...")

    is_general_plugin_hidden = DRIVER.execute_script(
        """return document.querySelector('form[data-services-modal-form][data-advanced] [data-plugin-item="general"]').classList.contains('hidden')"""
    )

    if is_general_plugin_hidden:
        log_error("Plugin general should be visible.")
        exit(1)

    is_antibot_plugin_hidden = DRIVER.execute_script(
        """return document.querySelector('form[data-services-modal-form][data-advanced] [data-plugin-item="antibot"]').classList.contains('hidden')"""
    )

    if not is_antibot_plugin_hidden:
        log_error("Plugin antibot should not be visible.")
        exit(1)

    log_info("Only one plugin visible checked, trying keyword no match ...")

    # Set keyword with no matching settings
    input_keyword = safe_get_element(DRIVER, By.ID, "settings-filter")
    assert isinstance(input_keyword, WebElement), "Settings filter element is not a WebElement"

    input_keyword.clear()
    input_keyword.send_keys("dqz48 é84 dzq 584dz5qd4")

    sleep(0.5)

    # Check that the no matching element is shown and other card hide
    is_no_match = DRIVER.execute_script('return document.querySelector("[data-services-nomatch]").classList.contains("hidden")')
    if is_no_match:
        log_error("Filter keyword shouldn't match something.")
        exit(1)

    # Reset
    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", input_keyword)

    log_info("Filter with unmatched keyword works as expected, try to match a setting ...")

    DRIVER.execute_script(
        "arguments[0].value = 'server type'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", input_keyword
    )

    # Check that the matching element is shown and other card hide
    is_server_type_hidden = DRIVER.execute_script(
        "return document.querySelector('form[data-services-modal-form][data-advanced] #form-edit-services-server-type').classList.contains('hidden')"
    )

    if is_server_type_hidden:
        log_error("Setting server type should be match.")
        exit(1)

    is_server_name_hidden = DRIVER.execute_script(
        "return document.querySelector('form[data-services-modal-form][data-advanced] #form-edit-services-server-name').classList.contains('hidden')"
    )

    if not is_server_name_hidden:
        log_error("Setting server name should not be match.")
        exit(1)

    # Reset
    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", input_keyword)

    log_info("Matching a setting done, trying select dropdown ...")

    DRIVER.execute_script("""document.querySelector('button[data-tab-select-dropdown-btn]').click()""")

    select = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//button[@data-setting-select='server-type']")
    assert_button_click(DRIVER, select)

    select_active_item = safe_get_element(
        DRIVER,
        By.XPATH,
        "//form[@data-services-modal-form and @data-advanced]//button[@data-setting-select-dropdown-btn='server-type' and contains(@class, 'active')]",
    )
    assert_button_click(DRIVER, select_active_item)

    log_info("Select dropdown done, trying toggle checkbox...")

    checkbox_api = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='LISTEN_STREAM']")
    assert_button_click(DRIVER, checkbox_api)
    assert_button_click(DRIVER, checkbox_api)

    log_info("Toggle checkbox done, trying multiple plugins select ...")

    # Open dropdown to select all plugins and click on them
    buttons_plugin = DRIVER.execute_script('return document.querySelectorAll("button[data-tab-select-handler]")')

    for button in buttons_plugin:
        DRIVER.execute_script("arguments[0].click()", button)

    assert_button_click(DRIVER, "//button[@data-services-modal-close='']")

    log_info("Multiple plugins select done ...")

    log_info("Additional checks done, trying to edit the config ...")

    assert_button_click(DRIVER, "//div[@data-services-service='www.example.com']//button[@data-services-action='edit']")

    assert_button_click(DRIVER, "//button[@data-tab-select-dropdown-btn='']")
    assert_button_click(DRIVER, "//button[@data-tab-select-handler='gzip']")
    gzip_select = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//button[@data-setting-select='gzip-comp-level']")
    assert isinstance(gzip_select, WebElement), "Gzip select is not a WebElement"
    assert_button_click(DRIVER, gzip_select)

    assert_button_click(
        DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-setting-select-dropdown-btn='gzip-comp-level' and @value='6']"
    )

    access_page(DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-services-modal-submit='']", "services", False)

    if TEST_TYPE == "linux":
        wait_for_service()

    log_info("The page reloaded successfully, checking if the setting has been updated ...")

    assert_button_click(DRIVER, "//div[@data-services-service='www.example.com']//button[@data-services-action='edit']")

    modal = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-modal='']")
    assert isinstance(modal, WebElement), "Modal is not a WebElement"
    if "hidden" in (modal.get_attribute("class") or ""):
        log_error("Modal is hidden even though it shouldn't be, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-tab-select-dropdown-btn='']")
    assert_button_click(DRIVER, "//button[@data-tab-select-handler='gzip']")

    gzip_comp_level_selected_elem = safe_get_element(
        DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//select[@id='GZIP_COMP_LEVEL']/option[@selected='']"
    )
    assert isinstance(gzip_comp_level_selected_elem, WebElement), "Gzip comp level selected element is not a WebElement"
    if gzip_comp_level_selected_elem.get_attribute("value") != "6":
        log_error("The value is not the expected one, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-services-modal-close='']/*[local-name() = 'svg']")

    log_info("Setting updated, creating a new service in advanced mode ...")

    assert_button_click(DRIVER, "//button[@data-services-action='new']")

    current_mode = DRIVER.execute_script("return document.querySelector('button[data-toggle-settings-mode-btn]').getAttribute('data-toggle-settings-mode-btn')")
    if current_mode != "simple":
        log_error(f"""Default mode for new service need to be simple and not {current_mode}...""")
        exit(1)

    # Switch to advanced mode
    DRIVER.execute_script("document.querySelector('button[data-toggle-settings-mode-btn]').click()")

    current_mode = DRIVER.execute_script("return document.querySelector('button[data-toggle-settings-mode-btn]').getAttribute('data-toggle-settings-mode-btn')")

    if current_mode != "advanced":
        log_error(f"""Switching mode needed to return advanced mode, but he have {current_mode}...""")
        exit(1)

    server_name_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='SERVER_NAME']")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    # Reset
    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input)

    # Search service
    DRIVER.execute_script(
        "arguments[0].value = 'app1.example.com'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input
    )

    if TEST_TYPE == "docker":
        assert_button_click(DRIVER, "//button[@data-tab-select-dropdown-btn='']")
        assert_button_click(DRIVER, "//button[@data-tab-select-handler='reverseproxy']")

        use_reverse_proxy_checkbox = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='USE_REVERSE_PROXY']")
        assert isinstance(use_reverse_proxy_checkbox, WebElement), "Use reverse proxy checkbox is not a WebElement"
        assert_button_click(DRIVER, use_reverse_proxy_checkbox)

        reverse_proxy_host_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='REVERSE_PROXY_HOST']")
        assert isinstance(reverse_proxy_host_input, WebElement), "Reverse proxy host input is not a WebElement"
        DRIVER.execute_script(
            """return document.querySelector('form[data-services-modal-form][data-advanced] input#REVERSE_PROXY_HOST[data-setting-input]').value = 'http://app1:8080' """
        )

        reverse_proxy_url_input = safe_get_element(DRIVER, By.XPATH, "//input[@id='REVERSE_PROXY_URL']")
        assert isinstance(reverse_proxy_url_input, WebElement), "Reverse proxy url input is not a WebElement"
        DRIVER.execute_script("""return document.querySelector('input#REVERSE_PROXY_URL[data-setting-input]').value = '/' """)

    log_info("Set new service values, trying to save ...")

    access_page(DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-services-modal-submit='']", "services", False)

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

    log_info("New service 'app1.example.com' is present, trying it ...")

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

    server_name_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='SERVER_NAME']")
    assert isinstance(server_name_input, WebElement), "Input is not a WebElement"

    if server_name_input.get_attribute("value"):
        log_error("The cloned service input is not empty, exiting ...")
        exit(1)

    # Update name
    DRIVER.execute_script(
        "arguments[0].value = 'app2.example.com'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input
    )

    access_page(DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-services-modal-submit='']", "services", False)

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

    wait_for_service("app2.example.com")

    try:
        safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='edit' and @data-services-name='app2.example.com']//ancestor::div//a", error=True)
    except TimeoutException:
        log_error("Delete button hasn't been found, even though it should be, exiting ...")
        exit(1)

    log_info("The service is working, trying to set it as draft ...")

    assert_button_click(DRIVER, "//div[@data-services-service='app2.example.com']//button[@data-services-action='edit']")

    assert_button_click(DRIVER, "//button[@data-toggle-draft-btn='']")

    access_page(DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-services-modal-submit='']", "services", False)

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

    log_info("Service app2.example.com has been set as draft, making sure it's not working anymore ...")

    retry = 0
    for x in range(5):
        retry += 1
        with suppress(RequestException):
            req = get("http://app2.example.com")
            if req.status_code < 400 and retry >= 5 and "Nothing to see here..." not in req.text:
                log_error("The service is still working, exiting ...")
                log_error(f"Status code = {str(req.status_code)}")
                log_error(f"Content = {req.text}")
                exit(1)
            if req.status_code < 400 and retry < 5 and "Nothing to see here..." not in req.text:
                log_warning("The service is still working, retry in 5 seconds ...")
                sleep(5)

    log_info("Create another service app3.example.com to get filters (need at least 4 services on page)")

    try:
        clone_button_2 = safe_get_element(DRIVER, By.XPATH, "//button[@data-services-action='clone' and @data-services-name='app1.example.com']", error=True)
        assert isinstance(clone_button_2, WebElement), "Clone button is not a WebElement"
    except TimeoutException:
        log_exception("Clone button hasn't been found, even though it should be, exiting ...")
        exit(1)

    assert_button_click(DRIVER, clone_button_2)

    server_name_input_2 = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-advanced]//input[@id='SERVER_NAME']")
    assert isinstance(server_name_input_2, WebElement), "Input is not a WebElement"

    if server_name_input_2.get_attribute("value"):
        log_error("The cloned service input is not empty, exiting ...")
        exit(1)

    # Reset

    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input_2)

    DRIVER.execute_script(
        "arguments[0].value = 'app3.example.com'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input_2
    )

    access_page(DRIVER, "//form[@data-services-modal-form and @data-advanced]//button[@data-services-modal-submit='']", "services", False)

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

    log_info(f"We need at least 4 services to test filter, currently {len(services)}")

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

    log_info("Service app3.example.com is present, trying service card filters...")

    # Set keyword with no matching settings
    input_card_keyword = safe_get_element(DRIVER, By.ID, "service-name-keyword")
    assert isinstance(input_card_keyword, WebElement), "Service name element is not a WebElement"

    input_card_keyword.clear()
    input_card_keyword.send_keys("dqz48 é84 dzq 584dz5qd4")

    sleep(0.5)

    # Check that the no matching element is shown and other card hide
    is_no_match = DRIVER.execute_script('return document.querySelector("[data-services-nomatch-card]").classList.contains("hidden")')
    if is_no_match:
        log_error("Filter keyword shouldn't match something.")
        exit(1)

    # Reset
    DRIVER.execute_script("arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", input_card_keyword)

    log_info("Service card keyword filter working, trying select filters ...")

    # Test select filters
    select_filters = [
        {"name": "Method", "id": "method", "value": "all"},
        {"name": "State", "id": "state", "value": "all"},
    ]

    for item in select_filters:
        DRIVER.execute_script(
            f"""return document.querySelector('[data-services-setting-select-dropdown-btn="{item["id"]}"][value="{item["value"]}"]').click()"""
        )

    log_info("Filters working as expected, trying to delete app3.example.com ...")

    try:
        delete_card_button = safe_get_element(
            DRIVER, By.XPATH, "//button[@data-services-action='delete' and @data-services-name='app3.example.com']", error=True
        )
        assert isinstance(delete_card_button, WebElement), "Delete button is not a WebElement"
        assert_button_click(DRIVER, delete_card_button)

    except TimeoutException:
        log_exception("Delete button hasn't been found, even though it should be, exiting ...")
        exit(1)

    log_info("Delete button is present, as expected, deleting the service ...")

    access_page(DRIVER, "//form[@data-services-modal-form-delete='']//button[@type='submit']", "services", False)

    log_info("Delete service modal button clicked, check if delete ...")

    if TEST_TYPE == "linux":
        wait_for_service()

    log_info("Service app3.example.com has been deleted, checking if it's still present ...")

    try:
        services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service='']", multiple=True, error=True)
        assert isinstance(services, list), "Services is not a list"
    except TimeoutException:
        log_exception("Services not found, exiting ...")
        exit(1)

    if len(services) > 4:
        log_error(f"The service hasn't been deleted ({len(services)} services found), exiting ...")
        exit(1)

    log_info("Service app3.example.com has been deleted successfully, making sure it's not working anymore ...")

    retry = 0
    for x in range(5):
        retry += 1
        with suppress(RequestException):
            req = get("http://app3.example.com")
            if req.status_code < 400 and retry >= 5 and "Nothing to see here..." not in req.text:
                log_error("The service is still working, exiting ...")
                log_error(f"Status code = {str(req.status_code)}")
                log_error(f"Content = {req.text}")
                exit(1)
            if req.status_code < 400 and retry < 5 and "Nothing to see here..." not in req.text:
                log_warning("The service is still working, retry in 5 seconds ...")
                sleep(5)

    # log_info("Service app3.example.com is not working, as expected, trying to recreate app3.example.com using simple mode ...")

    # assert_button_click(DRIVER, "//button[@data-services-action='new']")

    # current_mode = DRIVER.execute_script("return document.querySelector('button[data-toggle-settings-mode-btn]').getAttribute('data-toggle-settings-mode-btn')")
    # if current_mode != "simple":
    #     log_error(f"""Default mode for new service need to be simple and not {current_mode}...""")
    #     exit(1)

    # log_info("Start checking steps buttons and default SERVER_NAME state ...")

    # # Check that actions are disabled and server name empty
    # server_name_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-simple]//input[@id='SERVER_NAME']")
    # assert isinstance(server_name_input, WebElement), "Input is not a WebElement"
    # if server_name_input.get_attribute("value"):
    #     log_error("Server name input is not empty, exiting ...")
    #     exit(1)

    # # Check that button back is disabled
    # back_button = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-simple]//button[@data-simple-back='']")
    # assert isinstance(back_button, WebElement), "Back button is not a WebElement"
    # if not back_button.get_attribute("disabled"):
    #     log_error("Back button should be disabled, exiting ...")
    #     exit(1)

    # # Check that button next is disabled
    # next_button = safe_get_element(DRIVER, By.XPATH, "//form[@data-services-modal-form and @data-simple]//button[@data-simple-next='']")
    # assert isinstance(next_button, WebElement), "Next button is not a WebElement"
    # if not next_button.get_attribute("disabled"):
    #     log_error("Next button should be disabled, exiting ...")
    #     exit(1)

    # log_info("Steps buttons and SERVER_NAME state checked, fill first step and go to next one ...")

    # DRIVER.execute_script(
    #     "arguments[0].value = 'app3.example.com'; arguments[0].dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));", server_name_input
    # )

    # # Click on next button
    # assert_button_click(DRIVER, "//button[@data-simple-next='']")

    # # Check if data-step is 2 looking for hidden
    # is_step_2 = DRIVER.execute_script("""return document.querySelector("[data-step='2']").classList.contains("hidden")""")
    # if is_step_2:
    #     log_error("Step 2 should be visible.")
    #     exit(1)

    # log_info("Fill first step and move to step 2 done, edit step 2 value ...")

    # # Select antibot plugin and click on javascript value
    # assert_button_click(DRIVER, "//div[@id='antibot-simple']//button[@data-setting-select='use-antibot']")

    # # Click on javascript value
    # assert_button_click(DRIVER, "//div[@id='antibot-simple']//button[@data-setting-select-dropdown-btn='use-antibot' and @value='javascript']")

    # # Check that value is updated
    # antibot_button_text = safe_get_element(
    #     DRIVER, By.XPATH, "//div[@id='antibot-simple']//button[@data-setting-select='use-antibot']//span[@data-setting-select-text='use-antibot']"
    # )
    # assert isinstance(antibot_button_text, WebElement), "Antibot button text is not a WebElement"
    # if antibot_button_text.get_attribute("data-value") != "javascript":
    #     log_error("Value should be javascript.")
    #     exit(1)

    # log_info("Edit step 2 value, done, trying to go back, change security level and check antibot value ...")

    # # Click on back button
    # assert_button_click(DRIVER, "//button[@data-simple-back='']")

    # # Check if data-step is 1 looking for hidden
    # is_step_1 = DRIVER.execute_script("""return document.querySelector("[data-step='1']").classList.contains("hidden")""")
    # if is_step_1:
    #     log_error("Step 1 should be visible.")
    #     exit(1)

    # # Change security level
    # assert_button_click(DRIVER, "//div[@id='security-level-simple']//button[@data-setting-select='security-level']")

    # # Click on standard value
    # assert_button_click(DRIVER, "//div[@id='security-level-simple']//button[@data-setting-select-dropdown-btn='security-level' and @value='standard']")

    # # Check that value is updated
    # value_standard_security = safe_get_element(
    #     DRIVER, By.XPATH, "//div[@id='security-level-simple']//button[@data-setting-select='security-level']//span[@data-setting-select-text='security-level']"
    # )
    # assert isinstance(value_standard_security, WebElement), "Security level button text is not a WebElement"
    # if value_standard_security.get_attribute("data-value") != "standard":
    #     log_error("Value should be standard.")
    #     exit(1)

    # # Click on next button
    # assert_button_click(DRIVER, "//button[@data-simple-next='']")

    # # Check if data-step is 2 looking for hidden
    # is_step_2 = DRIVER.execute_script("""return document.querySelector("[data-step='2']").classList.contains("hidden")""")
    # if is_step_2:
    #     log_error("Step 2 should be visible.")
    #     exit(1)

    # # Check antibot value
    # antibot_button_text = safe_get_element(
    #     DRIVER, By.XPATH, "//div[@id='antibot-simple']//button[@data-setting-select='use-antibot']//span[@data-setting-select-text='use-antibot']"
    # )
    # assert isinstance(antibot_button_text, WebElement), "Antibot button text is not a WebElement"
    # if antibot_button_text.get_attribute("data-value") != "no":
    #     log_error("Value should be no.")
    #     exit(1)

    # log_info("Changing security level and check update done, create app ...")
    # access_page(DRIVER, "//form[@data-services-modal-form and @data-simple]//button[@data-services-modal-submit='']", "services", False)

    # if TEST_TYPE == "linux":
    #     wait_for_service("app3.example.com")

    # try:
    #     services = safe_get_element(DRIVER, By.XPATH, "//div[@data-services-service]", multiple=True, error=True)
    #     assert isinstance(services, list), "Services is not a list"
    # except TimeoutException:
    #     log_exception("Services not found, exiting ...")
    #     exit(1)

    # if len(services) < 4:
    #     log_error(f"The service hasn't been created ({len(services)} services found), exiting ...")
    #     exit(1)

    # log_info("Service app3.example.com has been created successfully...")

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
