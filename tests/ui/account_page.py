from logging import info as log_info, exception as log_exception, error as log_error
from time import sleep
from pyotp import TOTP

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from wizard import DRIVER, UI_PASSWORD
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the logs page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[2]/a", "account")

    log_info("Try to click on all available tabs ...")

    assert_button_click(DRIVER, "//button[@data-tab-handler='version']")
    assert_button_click(DRIVER, "//button[@data-tab-handler='username']")
    assert_button_click(DRIVER, "//button[@data-tab-handler='password']")
    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    log_info("All tabs working, start username tab ...")

    assert_button_click(DRIVER, "//button[@data-tab-handler='username']")

    username_input = safe_get_element(DRIVER, By.ID, "admin_username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"

    if username_input.get_attribute("value") != "admin":
        log_error("The username is not correct, exiting ...")
        exit(1)

    log_info("username 'admin' is correctly set by default, trying username update ...")

    DRIVER.execute_script("return arguments[0].value = 'admin2'", username_input)

    password_input = safe_get_element(DRIVER, By.ID, "curr_password")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"

    if password_input.get_attribute("value") != "":
        log_error("The current password is not empty, exiting ...")
        exit(1)

    # execute script using create password_input
    DRIVER.execute_script(f"return arguments[0].value = '{UI_PASSWORD}'", password_input)
    assert_button_click(DRIVER, "//button[@id='username-button' and @class='edit-btn']")

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div[1]/div/h1", error=True)
        assert isinstance(title, WebElement), "The title is not an instance of WebElement"

        if title.text != "Log in":
            log_error("Didn't get redirected to login page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Login page didn't load in time, exiting ...")
        exit(1)

    log_info("Successfully changed username, trying to log in with new username ...")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"
    username_input.send_keys("admin2")

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"
    password_input.send_keys(UI_PASSWORD)

    access_page(DRIVER, "//button[@value='login']", "home")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[2]/a", "account")

    assert_button_click(DRIVER, "//button[@data-tab-handler='username']")

    username_input = safe_get_element(DRIVER, By.ID, "admin_username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"

    if username_input.get_attribute("value") != "admin2":
        log_error("The username is not correct, exiting ...")
        exit(1)

    log_info("Successfully logged in with new username, trying to change password ...")

    assert_button_click(DRIVER, "//button[@data-tab-handler='password']")

    password_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-tab-item='password']//input[@id='curr_password']")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"

    if password_input.get_attribute("value") != "":
        log_error("The current password is not empty, exiting ...")
        exit(1)

    password_input.send_keys(UI_PASSWORD)

    new_password_input = safe_get_element(DRIVER, By.ID, "admin_password")
    assert isinstance(new_password_input, WebElement), "The new password input is not an instance of WebElement"

    if new_password_input.get_attribute("value") != "":
        log_error("The new password is not empty, exiting ...")
        exit(1)

    new_password_input.send_keys("P@ssw0rd")

    new_password_check_input = safe_get_element(DRIVER, By.ID, "admin_password_check")
    assert isinstance(new_password_check_input, WebElement), "The new password check input is not an instance of WebElement"

    if new_password_check_input.get_attribute("value") != "":
        log_error("The new password check is not empty, exiting ...")
        exit(1)

    new_password_check_input.send_keys("P@ssw0rd")

    assert_button_click(DRIVER, "//button[@id='pw-button' and @class='edit-btn']")

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div[1]/div/h1", error=True)
        assert isinstance(title, WebElement), "The title is not an instance of WebElement"

        if title.text != "Log in":
            log_error("Didn't get redirected to login page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Login page didn't load in time, exiting ...")
        exit(1)

    log_info("Successfully changed username, trying to log in with new password ...")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"
    username_input.send_keys("admin2")

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"
    password_input.send_keys("P@ssw0rd")

    access_page(DRIVER, "//button[@value='login']", "home")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[2]/a", "account")

    log_info("Successfully logged in with new password, trying 2FA ...")

    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    secret_token_input = safe_get_element(DRIVER, By.ID, "secret_token")
    assert isinstance(secret_token_input, WebElement), "The secret token input is not an instance of WebElement"
    secret_token = secret_token_input.get_attribute("value")

    DRIVER.refresh()

    WebDriverWait(DRIVER, 45).until(EC.presence_of_element_located((By.XPATH, "/html/body/div/header/div/nav/h6")))

    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    secret_token_input = safe_get_element(DRIVER, By.ID, "secret_token")
    assert isinstance(secret_token_input, WebElement), "The secret token input is not an instance of WebElement"
    new_secret_token = secret_token_input.get_attribute("value")

    if new_secret_token == secret_token:
        log_error("The secret token hasn't been changed, exiting ...")
        exit(1)
    assert new_secret_token, "The new secret token is empty"

    log_info("The secret token has been changed, trying to activate 2FA ...")

    totp = TOTP(new_secret_token)
    totp_input = safe_get_element(DRIVER, By.ID, "totp_token")
    assert isinstance(totp_input, WebElement), "The TOTP input is not an instance of WebElement"
    totp_input.send_keys(totp.now())

    password_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-tab-item='totp']//input[@id='curr_password']")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"

    if password_input.get_attribute("value") != "":
        log_error("The new password check is not empty, exiting ...")
        exit(1)

    password_input.send_keys("P@ssw0rd")

    access_page(DRIVER, "//button[@id='totp-button' and @class='valid-btn']", "account")

    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    try:
        totp_state = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/form[2]/h5")
        assert isinstance(totp_state, WebElement), "The TOTP state is not an instance of WebElement"

        if totp_state.text != "TOTP IS CURRENTLY ON":
            log_error("TOTP is not activated, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("TOTP has not been activated, exiting ...")
        exit(1)

    log_info("2FA has been activated, trying to log out ...")

    assert_button_click(DRIVER, "//a[@href='logout']")

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div[1]/div/h1", error=True)
        assert isinstance(title, WebElement), "The title is not an instance of WebElement"

        if title.text != "Log in":
            log_error("Didn't get redirected to login page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Login page didn't load in time, exiting ...")
        exit(1)

    log_info("Successfully logged out, trying to log in with 2FA ...")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"
    username_input.send_keys("admin2")

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"
    password_input.send_keys("P@ssw0rd")

    assert_button_click(DRIVER, "//button[@value='login']")

    try:
        totp_input = safe_get_element(DRIVER, By.ID, "totp_token")
        assert isinstance(totp_input, WebElement), "The TOTP input is not an instance of WebElement"
    except TimeoutException:
        log_error("Didn't get redirected to 2FA page, exiting ...")
        exit(1)

    totp_input.send_keys("0000000")
    assert_button_click(DRIVER, "//button[@value='login']")

    sleep(5)

    if not DRIVER.current_url.endswith("/totp"):
        log_error("Didn't get redirected back to 2FA page, exiting ...")
        exit(1)

    totp_input = safe_get_element(DRIVER, By.ID, "totp_token")
    assert isinstance(totp_input, WebElement), "The TOTP input is not an instance of WebElement"
    totp_input.send_keys(totp.now())

    access_page(DRIVER, "//button[@value='login']", "home")

    log_info("Successfully logged in with 2FA, trying to deactivate 2FA ...")

    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[2]/a", "account")

    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    totp_input = safe_get_element(DRIVER, By.ID, "totp_token")
    assert isinstance(totp_input, WebElement), "The TOTP input is not an instance of WebElement"
    totp_input.send_keys(totp.now())

    password_input = safe_get_element(DRIVER, By.XPATH, "//form[@data-tab-item='totp']//input[@id='curr_password']")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"
    password_input.send_keys("P@ssw0rd")

    access_page(DRIVER, "//button[@id='totp-button' and @class='delete-btn']", "account")

    assert_button_click(DRIVER, "//button[@data-tab-handler='totp']")

    try:
        totp_state = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div/div/form[2]/h5")
        assert isinstance(totp_state, WebElement), "The TOTP state is not an instance of WebElement"

        if totp_state.text != "TOTP IS CURRENTLY OFF":
            log_error("TOTP is not deactivated, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("TOTP has not been deactivated, exiting ...")
        exit(1)

    log_info("2FA has been deactivated, trying to log out ...")

    assert_button_click(DRIVER, "//a[@href='logout']")

    try:
        title = safe_get_element(DRIVER, By.XPATH, "/html/body/main/div[1]/div/h1", error=True)
        assert isinstance(title, WebElement), "The title is not an instance of WebElement"

        if title.text != "Log in":
            log_error("Didn't get redirected to login page, exiting ...")
            exit(1)
    except TimeoutException:
        log_exception("Login page didn't load in time, exiting ...")
        exit(1)

    log_info("Successfully logged out, trying to log in without 2FA ...")

    username_input = safe_get_element(DRIVER, By.ID, "username")
    assert isinstance(username_input, WebElement), "The username input is not an instance of WebElement"
    username_input.send_keys("admin2")

    password_input = safe_get_element(DRIVER, By.ID, "password")
    assert isinstance(password_input, WebElement), "The password input is not an instance of WebElement"
    password_input.send_keys("P@ssw0rd")

    access_page(DRIVER, "//button[@value='login']", "home")

    log_info("Successfully logged in without 2FA")

    log_info("✅ Account page tests finished successfully")
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
