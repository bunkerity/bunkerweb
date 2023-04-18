from contextlib import suppress
from datetime import datetime, timedelta
from os import listdir
from os.path import join
from pathlib import Path
from time import sleep
from traceback import format_exc
from typing import List, Union
from requests import get
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            status_code = get("http://www.example.com/admin").status_code

            if status_code > 500:
                print("An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400

        if retries > 10:
            print("UI took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("Waiting for UI to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    print("UI is ready, starting tests ...", flush=True)

    firefox_options = Options()
    if "geckodriver" not in listdir(Path.cwd()):
        firefox_options.add_argument("--headless")

    print("Starting Firefox ...", flush=True)

    def safe_get_element(
        driver, by: By, _id: str, *, multiple: bool = False, error: bool = False
    ) -> Union[WebElement, List[WebElement]]:
        try:
            return WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((by, _id))
                if not multiple
                else EC.presence_of_all_elements_located((by, _id))
            )
        except TimeoutException as e:
            if error:
                raise e

            print(
                f'Element searched by {by}: "{_id}" not found, exiting ...', flush=True
            )
            exit(1)

    def assert_button_click(driver, button: Union[str, WebElement]):
        clicked = False
        while not clicked:
            with suppress(ElementClickInterceptedException):
                if isinstance(button, str):
                    button = safe_get_element(driver, By.XPATH, button)

                sleep(0.5)

                button.click()
                clicked = True

    def assert_alert_message(driver, message: str):
        safe_get_element(driver, By.XPATH, "//button[@flash-sidebar-open='']")

        sleep(0.3)

        assert_button_click(driver, "//button[@flash-sidebar-open='']")

        error = False
        while True:
            try:
                alerts = safe_get_element(
                    driver,
                    By.XPATH,
                    "//aside[@flash-sidebar='']/div[2]/div",
                    multiple=True,
                    error=True,
                )
                break
            except TimeoutException:
                if error:
                    print("Messages list not found, exiting ...", flush=True)
                    exit(1)
                error = True
                driver.refresh()

        is_in = False
        for alert in alerts:
            if message in alert.text:
                is_in = True
                break

        if not is_in:
            print(
                f'Message "{message}" not found in one of the messages in the list, exiting ...',
                flush=True,
            )
            exit(1)

        print(
            f'Message "{message}" found in one of the messages in the list', flush=True
        )

        assert_button_click(
            driver, "//aside[@flash-sidebar='']/*[local-name() = 'svg']"
        )

    def access_page(
        driver,
        driver_wait: WebDriverWait,
        button: Union[str, WebElement],
        name: str,
        message: bool = True,
        *,
        retries: int = 0,
    ):
        assert_button_click(driver, button)

        try:
            title = driver_wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/div/header/div/nav/h6")
                )
            )

            if title.text != name.replace(" ", "_").title():
                print(f"Didn't get redirected to {name} page, exiting ...", flush=True)
                exit(1)
        except TimeoutException:
            if retries < 3 and driver.current_url.split("/")[-1].startswith("/loading"):
                sleep(2)
                access_page(
                    driver, driver_wait, button, name, message, retries=retries + 1
                )

            print(f"{name.title()} page didn't load in time, exiting ...", flush=True)
            exit(1)

        if message:
            print(
                f"{name.title()} page loaded successfully",
                flush=True,
            )

    with webdriver.Firefox(
        service=Service(
            executable_path="./geckodriver"
            if "geckodriver" in listdir(Path.cwd())
            else "/usr/local/bin/geckodriver"
        ),
        options=firefox_options,
    ) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()
        driver_wait = WebDriverWait(driver, 15)

        print("Navigating to http://www.example.com/admin ...", flush=True)

        driver.get("http://www.example.com/admin")

        ### LOGIN PAGE

        if not driver.current_url.endswith("/login"):
            print("Didn't get redirected to login page, exiting ...", flush=True)
            exit(1)

        print("Redirected to login page, waiting for login form ...", flush=True)

        safe_get_element(driver, By.TAG_NAME, "form")

        print(
            "Form found, trying to access another page without being logged in ...",
            flush=True,
        )

        driver.get("http://www.example.com/admin/home")

        print("Waiting for toast ...", flush=True)

        toast = safe_get_element(driver, By.XPATH, "//div[@flash-message='']")

        print("Toast found", flush=True)

        if "Please log in to access this page." not in toast.text:
            print("Toast doesn't contain the expected message, exiting ...", flush=True)
            exit(1)

        print(
            "Toast contains the expected message, filling login form with wrong credentials ...",
            flush=True,
        )

        sleep(1)

        safe_get_element(driver, By.TAG_NAME, "form")

        username_input = safe_get_element(driver, By.ID, "username")
        password_input = safe_get_element(driver, By.ID, "password")
        username_input.send_keys("hackerman")
        password_input.send_keys("password")
        password_input.send_keys(Keys.RETURN)

        sleep(0.3)

        try:
            title = driver_wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/main/div[1]/div/h1")
                )
            )

            if title.text != "Log in":
                print("Didn't get redirected to login page, exiting ...", flush=True)
                exit(1)
        except TimeoutException:
            print("Login page didn't load in time, exiting ...", flush=True)
            exit(1)

        print(
            "Got redirected to login page successfully, filling login form with good credentials ...",
            flush=True,
        )

        username_input = safe_get_element(driver, By.ID, "username")
        password_input = safe_get_element(driver, By.ID, "password")
        username_input.send_keys("admin")
        password_input.send_keys("admin")

        access_page(
            driver,
            driver_wait,
            "//button[@value='login']",
            "home",
        )

        ## HOME PAGE

        print("Trying instances page ...", flush=True)

        access_page(
            driver,
            driver_wait,
            "/html/body/aside[1]/div[1]/div[2]/ul/li[2]/a",
            "instances",
        )

        ### INSTANCES PAGE

        no_errors = True
        retries = 0
        while no_errors:
            print("Trying to reload BunkerWeb instance ...", flush=True)

            try:
                form = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//form[starts-with(@id, 'form-instance-')]")
                    )
                )
            except TimeoutException:
                print("No instance form found, exiting ...", flush=True)
                exit(1)

            try:
                access_page(
                    driver,
                    driver_wait,
                    "//form[starts-with(@id, 'form-instance-')]//button[@value='reload']",
                    "instances",
                    False,
                )

                print(
                    "Instance was reloaded successfully, checking the message ...",
                    flush=True,
                )

                assert_alert_message(driver, "has been reloaded")

                no_errors = False
            except:
                if retries >= 3:
                    exit(1)
                retries += 1

                print(
                    "WARNING: message list doesn't contain the expected message or is empty, retrying..."
                )

        print("Trying global config page ...")

        access_page(
            driver,
            driver_wait,
            "/html/body/aside[1]/div[1]/div[2]/ul/li[3]/a",
            "global config",
        )

        ### GLOBAL CONFIG PAGE

        no_errors = True
        retries = 0
        while no_errors:
            try:
                print(
                    "Trying to save the global config without changing anything ...",
                    flush=True,
                )

                safe_get_element(driver, By.ID, "form-edit-global-configs")

                access_page(
                    driver,
                    driver_wait,
                    "//form[@id='form-edit-global-configs']//button[@type='submit']",
                    "global config",
                    False,
                )

                print(
                    "The page reloaded successfully, checking the message ...",
                    flush=True,
                )

                assert_alert_message(
                    driver,
                    "The global configuration was not edited because no values were changed.",
                )

                no_errors = False
            except:
                if retries >= 3:
                    exit(1)
                retries += 1

                print(
                    "WARNING: message list doesn't contain the expected message or is empty, retrying..."
                )

        print(
            'Checking if the "DATASTORE_MEMORY_SIZE" input have the overridden value ...',
            flush=True,
        )

        input_datastore = safe_get_element(driver, By.ID, "DATASTORE_MEMORY_SIZE")

        if not input_datastore.get_attribute("disabled"):
            print(
                'The input "DATASTORE_MEMORY_SIZE" is not disabled, even though it should be, exiting ...',
                flush=True,
            )
            exit(1)
        elif input_datastore.get_attribute("value") != "384m":
            print("The value is not the expected one, exiting ...", flush=True)
            exit(1)

        print(
            "The value is the expected one and the input is disabled, trying to edit the global config with wrong values ...",
            flush=True,
        )

        input_worker = safe_get_element(driver, By.ID, "WORKER_RLIMIT_NOFILE")

        input_worker.clear()
        input_worker.send_keys("ZZZ")

        assert_button_click(
            driver, "//form[@id='form-edit-global-configs']//button[@type='submit']"
        )

        assert_alert_message(
            driver,
            "The global configuration was not edited because no values were changed.",
        )

        print(
            "The form was not submitted, trying to edit the global config with good values ...",
            flush=True,
        )

        input_worker.clear()
        input_worker.send_keys("4096")

        access_page(
            driver,
            driver_wait,
            "//form[@id='form-edit-global-configs']//button[@type='submit']",
            "global config",
            False,
        )

        input_worker = safe_get_element(driver, By.ID, "WORKER_RLIMIT_NOFILE")

        if input_worker.get_attribute("value") != "4096":
            print("The value was not updated, exiting ...", flush=True)
            exit(1)

        print(
            "The value was updated successfully, trying to navigate through the global config tabs ...",
            flush=True,
        )

        buttons = safe_get_element(
            driver,
            By.XPATH,
            "//div[@global-config-tabs-desktop='']/button",
            multiple=True,
        )
        buttons.reverse()
        for button in buttons:
            assert_button_click(driver, button)

        print("Trying to filter the global config ...", flush=True)

        safe_get_element(driver, By.ID, "settings-filter").send_keys("Datastore")

        if (
            len(
                safe_get_element(
                    driver,
                    By.XPATH,
                    "//form[@id='form-edit-global-configs']//div[@setting-container='' and not(contains(@class, 'hidden'))]",
                    multiple=True,
                )
            )
            != 1
        ):
            print("The filter didn't work, exiting ...", flush=True)
            exit(1)

        print("Trying services page ...")

        access_page(
            driver,
            driver_wait,
            "/html/body/aside[1]/div[1]/div[2]/ul/li[4]/a",
            "services",
        )

        ## SERVICES PAGE

        print("Checking the services page ...", flush=True)

        try:
            service = safe_get_element(
                driver, By.XPATH, "//div[@services-service='']", error=True
            )
        except TimeoutException:
            print("Services not found, exiting ...", flush=True)
            exit(1)

        if service.find_element(By.TAG_NAME, "h5").text.strip() != "www.example.com":
            print("The service is not present, exiting ...", flush=True)
            exit(1)

        if service.find_element(By.TAG_NAME, "h6").text.strip() != "scheduler":
            print(
                "The service should have been created by the scheduler, exiting ...",
                flush=True,
            )
            exit(1)

        print("Service www.example.com is present, trying to delete it ...", flush=True)

        delete_button = None
        with suppress(TimeoutException):
            delete_button = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//button[@services-action='delete' and @services-name='www.example.com']",
                    )
                )
            )

        if delete_button is not None:
            print(
                "Delete button has been found, even though it shouldn't be, exiting ...",
                flush=True,
            )
            exit(1)

        print(
            "Delete button is not present, as expected, trying to edit it ...",
            flush=True,
        )

        assert_button_click(
            driver, service.find_element(By.XPATH, ".//button[@services-action='edit']")
        )

        try:
            modal = safe_get_element(
                driver, By.XPATH, "//div[@services-modal='']", error=True
            )
        except TimeoutException:
            print("Modal not found, exiting ...", flush=True)
            exit(1)

        if "hidden" in modal.get_attribute("class"):
            print(
                "Modal is hidden even though it shouldn't be, exiting ...", flush=True
            )
            exit(1)

        input_server_name = safe_get_element(driver, By.ID, "SERVER_NAME")

        if input_server_name.get_attribute("value") != "www.example.com":
            print("The value is not the expected one, exiting ...", flush=True)
            exit(1)

        print(
            'The value for the "SERVER_NAME" input is the expected one, trying to edit the config ...',
            flush=True,
        )

        assert_button_click(
            driver,
            safe_get_element(driver, By.XPATH, "//button[@tab-handler='gzip']"),
        )

        gzip_select = safe_get_element(
            driver, By.XPATH, "//button[@setting-select='gzip-comp-level']"
        )

        assert_button_click(driver, gzip_select)

        assert_button_click(
            driver,
            safe_get_element(
                driver,
                By.XPATH,
                "//button[@setting-select-dropdown-btn='gzip-comp-level' and @value='6']",
            ),
        )

        access_page(
            driver,
            driver_wait,
            "//button[@services-modal-submit='']",
            "services",
            False,
        )

        print(
            "The page reloaded successfully, checking if the setting has been updated ...",
            flush=True,
        )

        try:
            service = safe_get_element(
                driver, By.XPATH, "//div[@services-service='']", error=True
            )
        except TimeoutException:
            print("Services not found, exiting ...", flush=True)
            exit(1)

        assert_button_click(
            driver, service.find_element(By.XPATH, ".//button[@services-action='edit']")
        )

        modal = safe_get_element(driver, By.XPATH, "//div[@services-modal='']")

        if "hidden" in modal.get_attribute("class"):
            print(
                "Modal is hidden even though it shouldn't be, exiting ...", flush=True
            )
            exit(1)

        assert_button_click(
            driver,
            driver.find_element(By.XPATH, "//button[@tab-handler='gzip']"),
        )

        gzip_true_select = safe_get_element(driver, By.ID, "GZIP_COMP_LEVEL")

        if (
            safe_get_element(
                driver, By.XPATH, "//select[@id='GZIP_COMP_LEVEL']/option[@selected='']"
            ).get_attribute("value")
            != "6"
        ):
            print("The value is not the expected one, exiting ...", flush=True)
            exit(1)

        no_errors = True
        retries = 0
        while no_errors:
            try:
                print(
                    "The value is the expected one, trying to save without changes ...",
                    flush=True,
                )

                access_page(
                    driver,
                    driver_wait,
                    "//button[@services-modal-submit='']",
                    "services",
                    False,
                )

                print(
                    "The page reloaded successfully, checking the message ...",
                    flush=True,
                )

                assert_alert_message(
                    driver, "was not edited because no values were changed."
                )

                no_errors = False
            except:
                if retries >= 3:
                    exit(1)
                retries += 1

                print(
                    "WARNING: message list doesn't contain the expected message or is empty, retrying..."
                )

                try:
                    service = safe_get_element(
                        driver, By.XPATH, "//div[@services-service='']", error=True
                    )
                except TimeoutException:
                    print("Services not found, exiting ...", flush=True)
                    exit(1)

                assert_button_click(service, ".//button[@services-action='edit']")

        print("Creating a new service ...", flush=True)

        assert_button_click(driver, "//button[@services-action='new']")

        server_name_input: WebElement = safe_get_element(driver, By.ID, "SERVER_NAME")
        server_name_input.clear()
        server_name_input.send_keys("app1.example.com")

        assert_button_click(driver, "//button[@tab-handler='reverseproxy']")

        assert_button_click(
            driver, safe_get_element(driver, By.ID, "USE_REVERSE_PROXY")
        )

        assert_button_click(driver, "//button[@services-multiple-add='reverse-proxy']")

        safe_get_element(driver, By.ID, "REVERSE_PROXY_HOST").send_keys(
            "http://app1:8080"
        )
        safe_get_element(driver, By.ID, "REVERSE_PROXY_URL").send_keys("/")

        access_page(
            driver,
            driver_wait,
            "//button[@services-modal-submit='']",
            "services",
            False,
        )

        try:
            services = safe_get_element(
                driver,
                By.XPATH,
                "//div[@services-service='']",
                multiple=True,
                error=True,
            )
        except TimeoutException:
            print("Services not found, exiting ...", flush=True)
            exit(1)

        if len(services) < 2:
            print("The service hasn't been created, exiting ...", flush=True)
            exit(1)

        service = services[0]

        if service.find_element(By.TAG_NAME, "h5").text.strip() != "app1.example.com":
            print(
                'The service "app1.example.com" is not present, exiting ...', flush=True
            )
            exit(1)

        if service.find_element(By.TAG_NAME, "h6").text.strip() != "ui":
            print(
                "The service should have been created by the ui, exiting ...",
                flush=True,
            )
            exit(1)

        print("Service app1.example.com is present, trying it ...", flush=True)

        try:
            safe_get_element(
                driver,
                By.XPATH,
                "//button[@services-action='edit' and @services-name='www.example.com']//ancestor::div//a",
                error=True,
            )
        except TimeoutException:
            print(
                "Delete button hasn't been found, even though it should be, exiting ...",
                flush=True,
            )
            exit(1)

        ready = False
        retries = 0
        while not ready:
            with suppress(RequestException):
                status_code = get("http://app1.example.com/").status_code

                if status_code > 500:
                    print("The service is not working, exiting ...", flush=True)
                    exit(1)

                ready = status_code < 400

            if retries > 10:
                print("The service took too long to be ready, exiting ...", flush=True)
                exit(1)
            elif not ready:
                retries += 1
                print(
                    "Waiting for the service to be ready, retrying in 5s ...",
                    flush=True,
                )
                sleep(5)

        print("The service is working, trying to delete it ...", flush=True)

        try:
            delete_button = safe_get_element(
                driver,
                By.XPATH,
                "//button[@services-action='delete' and @services-name='app1.example.com']",
                error=True,
            )
        except TimeoutException:
            print(
                "Delete button hasn't been found, even though it should be, exiting ...",
                flush=True,
            )
            exit(1)

        print(
            "Delete button is present, as expected, deleting the service ...",
            flush=True,
        )

        assert_button_click(driver, delete_button)

        access_page(
            driver,
            driver_wait,
            "//form[@services-modal-form-delete='']//button[@type='submit']",
            "services",
            False,
        )

        assert_alert_message(driver, "has been deleted.")

        print(
            "Service app1.example.com has been deleted, checking if it's still present ...",
            flush=True,
        )

        try:
            services = safe_get_element(
                driver,
                By.XPATH,
                "//div[@services-service='']",
                multiple=True,
                error=True,
            )
        except TimeoutException:
            print("Services not found, exiting ...", flush=True)
            exit(1)

        if len(services) > 1:
            print("The service hasn't been deleted, exiting ...", flush=True)
            exit(1)

        print(
            "The service has been deleted, successfully, trying configs page ...",
            flush=True,
        )

        access_page(
            driver,
            driver_wait,
            "/html/body/aside[1]/div[1]/div[2]/ul/li[5]/a",
            "configs",
        )

        ### CONFIGS PAGE

        print("Trying to create a new config ...", flush=True)

        assert_button_click(
            driver, "//div[@configs-element='server-http' and @_type='folder']"
        )
        assert_button_click(driver, "//li[@configs-add-file='']/button")

        safe_get_element(
            driver, By.XPATH, "//div[@configs-modal-path='']/input"
        ).send_keys("hello")
        safe_get_element(
            driver, By.XPATH, "//div[@configs-modal-editor='']/textarea"
        ).send_keys(
            """
            location /hello {
                default_type 'text/plain';
                content_by_lua_block {
                    ngx.say('hello app1')
                }
            }
            """
        )

        access_page(
            driver, driver_wait, "//button[@configs-modal-submit='']", "configs", False
        )

        assert_alert_message(driver, "was successfully created")

        sleep(15)

        driver.execute_script("window.open('http://www.example.com/hello','_blank');")
        driver.switch_to.window(driver.window_handles[1])
        driver.switch_to.default_content()

        try:
            if (
                safe_get_element(driver, By.XPATH, "//pre", error=True).text.strip()
                != "hello app1"
            ):
                print(
                    "The config hasn't been created correctly, exiting ...", flush=True
                )
                exit(1)
        except TimeoutException:
            print("The config hasn't been created, exiting ...", flush=True)
            exit(1)

        print(
            "The config has been created and is working, trying to edit it ...",
            flush=True,
        )

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        assert_button_click(
            driver, "//div[@configs-element='server-http' and @_type='folder']"
        )
        assert_button_click(driver, "//div[@configs-action-button='hello.conf']")
        assert_button_click(
            driver,
            "//div[@configs-action-dropdown='hello.conf']/button[@value='delete' and @configs-action-dropdown-btn='hello.conf']",
        )

        access_page(
            driver, driver_wait, "//button[@configs-modal-submit='']", "configs", False
        )

        assert_alert_message(driver, "was successfully deleted")

        print("The config has been deleted, trying plugins page ...", flush=True)

        access_page(
            driver,
            driver_wait,
            "/html/body/aside[1]/div[1]/div[2]/ul/li[6]/a",
            "plugins",
        )

        ### PLUGINS PAGE

        print("Trying to reload the plugins without adding any ...", flush=True)

        reload_button = safe_get_element(
            driver, By.XPATH, "//div[@plugins-upload='']//button[@type='submit']"
        )

        if reload_button.get_attribute("disabled") is None:
            print("The reload button is not disabled, exiting ...", flush=True)
            exit(1)

        print("Trying to filter the plugins ...", flush=True)

        safe_get_element(
            driver, By.XPATH, "//input[@placeholder='key words']"
        ).send_keys("Anti")

        plugins = safe_get_element(
            driver, By.XPATH, "//div[@plugins-list='']", multiple=True
        )

        if len(plugins) != 1:
            print("The filter is not working, exiting ...", flush=True)
            exit(1)

        print("The filter is working, trying to add a bad plugin ...", flush=True)

        safe_get_element(
            driver, By.XPATH, "//input[@type='file' and @name='file']"
        ).send_keys(join(Path.cwd(), "test.zip"))

        access_page(
            driver,
            driver_wait,
            "//div[@plugins-upload='']//button[@type='submit']",
            "plugins",
            False,
        )

        assert_alert_message(driver, "is not a valid plugin")

        print(
            "The bad plugin has been rejected, trying to add a good plugin ...",
            flush=True,
        )

        safe_get_element(
            driver, By.XPATH, "//input[@type='file' and @name='file']"
        ).send_keys(join(Path.cwd(), "discord.zip"))

        access_page(
            driver,
            driver_wait,
            "//div[@plugins-upload='']//button[@type='submit']",
            "plugins",
            False,
        )

        assert_alert_message(driver, "Successfully created plugin")

        external_plugins = safe_get_element(
            driver, By.XPATH, "//div[@plugins-external=' external ']", multiple=True
        )

        if len(external_plugins) != 1:
            print("The plugin hasn't been added, exiting ...", flush=True)
            exit(1)

        print("The plugin has been added, trying delete it ...", flush=True)

        assert_button_click(
            driver,
            "//button[@plugins-action='delete' and @name='discord']",
        )

        access_page(
            driver,
            driver_wait,
            "//form[@plugins-modal-form-delete='']//button[@type='submit']",
            "plugins",
            False,
        )

        with suppress(TimeoutException):
            title = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[@plugins-action='delete' and @name='discord']")
                )
            )

            if title:
                print("The plugin hasn't been deleted, exiting ...", flush=True)
                exit(1)

        print("The plugin has been deleted, trying cache page ...", flush=True)

        access_page(
            driver, driver_wait, "/html/body/aside[1]/div[1]/div[2]/ul/li[7]/a", "cache"
        )

        ### CACHE PAGE

        print("Trying to open a cache file ...", flush=True)

        assert_button_click(driver, "//div[@cache-element='mmdb-asn/asn.mmdb']")

        if (
            safe_get_element(
                driver,
                By.XPATH,
                "//div[@cache-modal-editor='']/div[@class='ace_scroller']//div[@class='ace_line']",
            ).text.strip()
            != "Download file to view content"
        ):
            print("The cache file content is not correct, exiting ...", flush=True)
            exit(1)

        assert_button_click(driver, "//button[@cache-modal-submit='']")

        print(
            "The cache file content is correct, trying to download it ...", flush=True
        )

        assert_button_click(driver, "//div[@cache-action-button='mmdb-asn/asn.mmdb']")

        assert_button_click(
            driver,
            "//div[@cache-action-dropdown='mmdb-asn/asn.mmdb']/button[@value='download']",
        )

        sleep(0.3)

        if len(driver.window_handles) > 1:
            print("The cache file hasn't been downloaded, exiting ...", flush=True)
            exit(1)

        print("The cache file has been downloaded, trying logs page ...", flush=True)

        access_page(
            driver, driver_wait, "/html/body/aside[1]/div[1]/div[2]/ul/li[8]/a", "logs"
        )

        ### LOGS PAGE

        print("Selecting correct instance ...", flush=True)

        assert_button_click(driver, "//button[@logs-setting-select='instances']")

        instances = safe_get_element(
            driver,
            By.XPATH,
            "//div[@logs-setting-select-dropdown='instances']/button",
            multiple=True,
        )

        first_instance = instances[0].text

        if len(instances) == 0:
            print("No instances found, exiting ...", flush=True)
            exit(1)

        assert_button_click(driver, instances[0])
        assert_button_click(driver, safe_get_element(driver, By.ID, "submit-settings"))

        sleep(3)

        logs_list = safe_get_element(
            driver, By.XPATH, "//ul[@logs-list='']/li", multiple=True
        )

        if len(logs_list) == 0:
            print("No logs found, exiting ...", flush=True)
            exit(1)

        print("Logs found, trying auto refresh ...", flush=True)

        assert_button_click(driver, safe_get_element(driver, By.ID, "live-update"))
        assert_button_click(driver, safe_get_element(driver, By.ID, "submit-settings"))

        sleep(3)

        if len(logs_list) == len(
            safe_get_element(
                driver,
                By.XPATH,
                "//ul[@logs-list='']/li[not(contains(@class, 'hidden'))]",
                multiple=True,
            )
        ):
            print("Auto refresh is not working, exiting ...", flush=True)
            exit(1)

        print("Auto refresh is working, deactivating it ...", flush=True)

        assert_button_click(driver, safe_get_element(driver, By.ID, "live-update"))
        assert_button_click(driver, safe_get_element(driver, By.ID, "submit-settings"))

        sleep(3)

        logs_list = safe_get_element(
            driver, By.XPATH, "//ul[@logs-list='']/li", multiple=True
        )

        print("Trying filters ...", flush=True)

        filter_input = safe_get_element(driver, By.ID, "keyword")

        filter_input.send_keys("gen")

        sleep(3)

        if len(logs_list) == len(
            safe_get_element(
                driver,
                By.XPATH,
                "//ul[@logs-list='']/li[not(contains(@class, 'hidden'))]",
                multiple=True,
            )
        ):
            print("The keyword filter is not working, exiting ...", flush=True)
            exit(1)

        filter_input.clear()

        print("Keyword filter is working, trying type filter ...", flush=True)

        assert_button_click(driver, "//button[@logs-setting-select='types']")

        assert_button_click(
            driver,
            "//div[@logs-setting-select-dropdown='types']/button[@value='warn']",
        )

        if len(logs_list) == len(
            safe_get_element(
                driver,
                By.XPATH,
                "//ul[@logs-list='']/li[not(contains(@class, 'hidden'))]",
                multiple=True,
            )
        ):
            print("The keyword filter is not working, exiting ...", flush=True)
            exit(1)

        assert_button_click(driver, "//button[@logs-setting-select='types']")

        assert_button_click(
            driver,
            "//div[@logs-setting-select-dropdown='types']/button[@value='all']",
        )

        print("Type filter is working, trying to filter by date ...", flush=True)

        current_date = datetime.now()
        resp = get(
            f"http://www.example.com/admin/logs/{first_instance}?from_date={int(current_date.timestamp() - 86400000)}&to_date={int((current_date - timedelta(days=1)).timestamp())}",
            headers={"Host": "www.example.com"},
            cookies={"session": driver.get_cookies()[0]["value"]},
        )

        if len(resp.json()["logs"]) != 0:
            print("The date filter is not working, exiting ...", flush=True)
            exit(1)

        print("Date filter is working, trying jobs page ...", flush=True)

        access_page(
            driver, driver_wait, "/html/body/aside[1]/div[1]/div[2]/ul/li[9]/a", "jobs"
        )

        ### JOBS PAGE

        print("Trying to filter jobs ...", flush=True)

        jobs_list = safe_get_element(
            driver, By.XPATH, "//ul[@jobs-list='']/li", multiple=True
        )

        if len(jobs_list) == 0:
            print("No jobs found, exiting ...", flush=True)
            exit(1)

        filter_input = safe_get_element(driver, By.ID, "keyword")

        filter_input.send_keys("abcde")

        with suppress(TimeoutException):
            if len(jobs_list) == len(
                safe_get_element(
                    driver,
                    By.XPATH,
                    "//ul[@jobs-list='']/li[not(contains(@class, 'hidden'))]",
                    multiple=True,
                    error=True,
                )
            ):
                print("The keyword filter is not working, exiting ...", flush=True)
                exit(1)

        filter_input.clear()

        print(
            "Keyword filter is working, trying to filter by success state ...",
            flush=True,
        )

        sleep(0.3)

        assert_button_click(driver, "//button[@jobs-setting-select='success']")

        assert_button_click(
            driver,
            "//div[@jobs-setting-select-dropdown='success']/button[@value='false']",
        )

        with suppress(TimeoutException):
            if (
                len(jobs_list)
                == len(
                    safe_get_element(
                        driver,
                        By.XPATH,
                        "//ul[@jobs-list='']/li[not(contains(@class, 'hidden'))]",
                        multiple=True,
                        error=True,
                    )
                )
            ) and len(jobs_list) != len(
                safe_get_element(
                    driver,
                    By.XPATH,
                    "//ul[@jobs-list='']//p[@jobs-success='false']",
                    multiple=True,
                    error=True,
                )
            ):
                print("The success filter is not working, exiting ...", flush=True)
                exit(1)

        assert_button_click(driver, "//button[@jobs-setting-select='success']")

        assert_button_click(
            driver,
            "//div[@jobs-setting-select-dropdown='success']/button[@value='all']",
        )

        print(
            "Success filter is working, trying to filter by reload state ...",
            flush=True,
        )

        sleep(0.3)

        assert_button_click(driver, "//button[@jobs-setting-select='reload']")

        assert_button_click(
            driver,
            "//div[@jobs-setting-select-dropdown='reload']/button[@value='true']",
        )

        with suppress(TimeoutException):
            if (
                len(jobs_list)
                == len(
                    safe_get_element(
                        driver,
                        By.XPATH,
                        "//ul[@jobs-list='']/li[not(contains(@class, 'hidden'))]",
                        multiple=True,
                        error=True,
                    )
                )
            ) and len(jobs_list) != len(
                safe_get_element(
                    driver,
                    By.XPATH,
                    "//ul[@jobs-list='']//p[@jobs-reload='true']",
                    multiple=True,
                    error=True,
                )
            ):
                print("The reload filter is not working, exiting ...", flush=True)
                exit(1)

        assert_button_click(driver, "//button[@jobs-setting-select='reload']")

        assert_button_click(
            driver,
            "//div[@jobs-setting-select-dropdown='reload']/button[@value='all']",
        )

        print("Reload filter is working, trying jobs cache ...", flush=True)

        sleep(0.3)

        resp = get(
            "http://www.example.com/admin/jobs/download?job_name=mmdb-country&file_name=country.mmdb"
        )

        if resp.status_code != 200:
            print("The cache download is not working, exiting ...", flush=True)
            exit(1)

        print("Cache download is working, trying to log out ...", flush=True)

        assert_button_click(driver, "//a[@href='logout']")

        try:
            title = driver_wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/main/div[1]/div/h1")
                )
            )

            if title.text != "Log in":
                print("Didn't get redirected to login page, exiting ...", flush=True)
                exit(1)
        except TimeoutException:
            print("Login page didn't load in time, exiting ...", flush=True)
            exit(1)

        print("Successfully logged out, tests are done", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)

exit(0)
