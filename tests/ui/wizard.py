from datetime import datetime, timedelta
from logging import error as log_error, exception as log_exception, info as log_info
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException

from base import DEFAULT_SERVER, DRIVER
from utils import access_page, assert_button_click, safe_get_element

UI_USERNAME = "admin"
UI_PASSWORD = "S$cr3tP@ssw0rd"

UI_URL = ""
exit_code = None

log_info("Starting the setup wizard ...")

try:
    DRIVER.delete_all_cookies()
    DRIVER.maximize_window()
    driver_wait = WebDriverWait(DRIVER, 45)

    log_info(f"Navigating to http://{DEFAULT_SERVER}/setup ...")
    DRIVER.get(f"http://{DEFAULT_SERVER}/setup")

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/h1", driver_wait=driver_wait)
        assert isinstance(title, WebElement), "Title is not a WebElement"

        if title.text != "Setup Wizard":
            log_error("Didn't get redirected to setup page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Didn't get redirected to setup page, exiting ...")
        exit(1)

    log_info("Setup page loaded successfully, filling the form ...")

    admin_username_input = safe_get_element(DRIVER, By.ID, "admin_username")
    assert isinstance(admin_username_input, WebElement), "Admin username input is not a WebElement"
    admin_username_input.send_keys(UI_USERNAME)

    password_input = safe_get_element(DRIVER, By.ID, "admin_password")
    assert isinstance(password_input, WebElement), "Password input is not a WebElement"
    password_input.send_keys(UI_PASSWORD)

    password_check_input = safe_get_element(DRIVER, By.ID, "admin_password_check")
    assert isinstance(password_check_input, WebElement), "Password check input is not a WebElement"
    password_check_input.send_keys(UI_PASSWORD)

    ui_url_elem = safe_get_element(DRIVER, By.ID, "ui_url")
    assert isinstance(ui_url_elem, WebElement), "UI URL input is not a WebElement"
    UI_URL = ui_url_elem.get_attribute("value")

    assert_button_click(DRIVER, "//button[@id='setup-button']")

    log_info("Submitted the form, waiting for the wizard to finish ...")

    current_time = datetime.now()

    while current_time + timedelta(minutes=5) > datetime.now() and not DRIVER.current_url.endswith("/login"):
        sleep(1)

    if not DRIVER.current_url.endswith("/login"):
        log_error("Didn't get redirected to login page, exiting ...")
        exit(1)

    log_info("Redirected to login page, waiting for login form ...")

    safe_get_element(DRIVER, By.TAG_NAME, "form")

    log_info("Form found, trying to access another page without being logged in ...")

    DRIVER.get(f"http://www.example.com{UI_URL}/home")

    log_info("Waiting for toast ...")

    toast = safe_get_element(DRIVER, By.XPATH, "//div[@data-flash-message='']")
    assert isinstance(toast, WebElement), "Toast is not a WebElement"

    log_info("Toast found")

    if "Please log in to access this page." not in toast.text:
        log_error("Toast doesn't contain the expected message, exiting ...")
        exit(1)

    log_info("Toast contains the expected message, filling login form with wrong credentials ...")

    sleep(1)

    safe_get_element(DRIVER, By.TAG_NAME, "form")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "Username input is not a WebElement"
    username_input.send_keys("hackerman")

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "Password input is not a WebElement"
    password_input.send_keys("password")
    password_input.send_keys(Keys.RETURN)

    sleep(0.3)

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div[1]/div/h1", driver_wait=driver_wait)
        assert isinstance(title, WebElement), "Title is not a WebElement"

        if title.text != "Log in":
            log_error("Didn't get redirected to login page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Login page didn't load in time, exiting ...")
        exit(1)

    log_info("Got redirected to login page successfully, filling login form with good credentials ...")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "Username input is not a WebElement"
    username_input.send_keys(UI_USERNAME)

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "Password input is not a WebElement"
    password_input.send_keys(UI_PASSWORD)

    access_page(DRIVER, "//button[@value='login']", "home")
except SystemExit as e:
    exit_code = e.code
except KeyboardInterrupt:
    exit_code = 1
except:
    log_exception("Something went wrong, exiting ...")
    DRIVER.save_screenshot("error.png")
    exit_code = 1
finally:
    if exit_code is not None:
        DRIVER.quit()
        exit(exit_code)
