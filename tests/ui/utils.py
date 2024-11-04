from contextlib import suppress
from datetime import datetime
from logging import error as log_error, exception as log_exception, info as log_info, warning as log_warning
from time import sleep
from typing import List, Optional, Union
from requests import RequestException, get
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, WebDriverException


def safe_get_element(
    driver, by: str, selector: str, *, driver_wait: Optional[WebDriverWait] = None, multiple: bool = False, error: bool = False
) -> Union[WebElement, List[WebElement]]:
    try:
        # Retrieve by js script
        if by == "js":
            # Run every wait seconds trying to get elements
            wait = driver_wait or 4
            el = None
            for x in range(wait):
                try:
                    el = driver.execute_script(f"return {selector} || null")
                    if not el:
                        sleep(1)
                        continue
                    else:
                        break
                except:
                    el = None
            # Case no el found
            if not el:
                log_exception(f'Element searched by {by}: "{selector}" not found, exiting ...')
                raise TimeoutException

            return el

        # Retrieve with XPATH
        return (driver_wait or WebDriverWait(driver, 4)).until(
            EC.presence_of_element_located((by, selector)) if not multiple else EC.presence_of_all_elements_located((by, selector))
        )
    except TimeoutException as e:

        if error:
            raise e

        log_exception(f'Element searched by {by}: "{selector}" not found, exiting ...')
        exit(1)


def assert_button_click(driver, button: Union[str, WebElement], by: str = "xpath"):  # type: ignore
    clicked = False
    current_date = datetime.now()
    while not clicked:
        with suppress(ElementClickInterceptedException):
            if isinstance(button, str):
                # Retrieve with js script
                if by == "js":
                    button: Union[WebElement, List[WebElement]] = safe_get_element(driver, by, button)
                # Retrieve by XPATH
                else:
                    button: Union[WebElement, List[WebElement]] = safe_get_element(driver, By.XPATH, button)
                assert isinstance(button, WebElement), "Button is not a WebElement"

            sleep(0.5)

            button.click()

            clicked = True

        if (datetime.now() - current_date).seconds > 15:
            log_error("Button click failed, exiting ...")
            exit(1)

    return clicked


def assert_alert_message(driver, message: str):
    safe_get_element(driver, By.XPATH, "//button[@data-flash-sidebar-open='']")

    sleep(0.3)

    assert_button_click(driver, "//button[@data-flash-sidebar-open='']")

    error = False
    while True:
        try:
            alerts: Union[WebElement, List[WebElement]] = safe_get_element(
                driver,
                By.XPATH,
                "//aside[@data-flash-sidebar='']/div[2]/div",
                multiple=True,
                error=True,
            )
            assert isinstance(alerts, list), "Alerts is not a list of WebElements"
            break
        except TimeoutException:
            if error:
                log_exception("Messages list not found, exiting ...")
                exit(1)
            error = True
            driver.refresh()

    is_in = False
    for alert in alerts:
        if message in alert.text:
            is_in = True
            break

    if not is_in:
        log_error(f'Message "{message}" not found in one of the messages in the list, exiting ...')
        exit(1)

    log_info(f'Message "{message}" found in one of the messages in the list')
    assert_button_click(driver, "//button[@data-flash-sidebar-close='']/*[local-name() = 'svg']")


def access_page(driver, button: Union[bool, str, WebElement], name: str, message: bool = True, *, retries: int = 0, clicked: bool = False):
    if retries > 5:
        log_error("Too many retries...")
        exit(1)

    try:
        if not isinstance(button, bool) and not clicked:
            clicked = assert_button_click(driver, button)

        sleep(1)

        title: Union[WebElement, List[WebElement]] = safe_get_element(
            driver, By.XPATH, "/html/body/div[3]/header/div/nav/h6", driver_wait=WebDriverWait(driver, 45)
        )
        assert isinstance(title, WebElement), "Title is not a WebElement"

        if title.text != name.title():
            log_error(f"Didn't get redirected to {name} page, exiting ...")
            exit(1)
    except TimeoutException:
        if "/loading" in driver.current_url:
            sleep(2)
            return access_page(driver, button, name, message, retries=retries + 1, clicked=clicked)

        log_error(f"{name.title()} page didn't load in time, exiting ...")
        exit(1)
    except WebDriverException as we:
        if "connectionFailure" in str(we):
            log_warning("Connection failure, retrying in 5s ...")
            driver.refresh()
            sleep(5)
            return access_page(driver, button, name, message, retries=retries + 1, clicked=clicked)
        raise we

    if message:
        log_info(f"{name.title()} page loaded successfully")


def wait_for_service(service: str = "www.example.com"):
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get(f"http://{service}/ready", headers={"Host": service}, verify=False)
            status_code = resp.status_code
            text = resp.text

            if resp.status_code >= 500:
                log_error(f"An error occurred while trying to reach {service}, exiting ...")
                exit(1)

            ready = status_code < 400 and "ready" in text

        if retries > 10:
            log_error(f"Service {service} took too long to be ready, exiting ...")
            exit(1)
        elif not ready:
            retries += 1
            log_warning(f"Waiting for {service} to be ready, retrying in 5s ...")
            sleep(5)
