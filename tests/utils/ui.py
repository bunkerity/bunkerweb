from contextlib import suppress
from datetime import datetime, timedelta
from logging import Logger
from time import sleep
from typing import List, Optional, Union
from requests import RequestException, get
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, WebDriverException


def safe_get_element(
    logger: Logger,
    driver,
    by: str,
    selector: str,
    *,
    driver_wait: Optional[Union[WebDriverWait, int]] = None,
    multiple: bool = False,
    error: bool = False,
) -> Union[WebElement, List[WebElement]]:
    try:
        # Retrieve by js script
        if by == "js":
            # Run every wait seconds trying to get elements
            # Accept either a WebDriverWait instance or an integer seconds value
            if isinstance(driver_wait, WebDriverWait):
                wait_seconds = int(getattr(driver_wait, "_timeout", 4) or 4)
            elif isinstance(driver_wait, int):
                wait_seconds = driver_wait
            else:
                wait_seconds = 4

            el = None
            for _ in range(max(wait_seconds, 1)):
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
                logger.exception(f'🦊 Element searched by {by}: "{selector}" not found, exiting ...')
                raise TimeoutException

            return el

        # Retrieve with XPATH
        # Accept either a WebDriverWait instance or an integer seconds value
        if isinstance(driver_wait, WebDriverWait):
            waiter = driver_wait
        elif isinstance(driver_wait, int):
            waiter = WebDriverWait(driver, max(driver_wait, 1))
        else:
            waiter = WebDriverWait(driver, 4)

        return waiter.until(EC.presence_of_element_located((by, selector)) if not multiple else EC.presence_of_all_elements_located((by, selector)))
    except TimeoutException as e:

        if error:
            raise e

        logger.exception(f'🦊 Element searched by {by}: "{selector}" not found, exiting ...')
        if not isinstance(driver, WebElement):
            driver.save_screenshot("error.png")
        exit(1)


def assert_button_click(logger: Logger, driver, button: Union[str, WebElement], by: Optional[str] = None):
    # Get all toast dismiss buttons and click them
    dismissed_toasts = False
    try:
        toast_dismiss_buttons = driver.find_elements(By.XPATH, '//div[@id="feedback-toast-container"]//button[@data-bs-dismiss="toast"]')
        for dismiss_button in toast_dismiss_buttons:
            dismiss_button.click()
            dismissed_toasts = True
            sleep(0.1)
    except Exception:
        pass
    finally:
        if dismissed_toasts:
            sleep(0.5)

    clicked = False
    current_date = datetime.now()
    if isinstance(button, str):
        button: Union[WebElement, List[WebElement]] = safe_get_element(logger, driver, by or By.XPATH, button)
    assert isinstance(button, WebElement), "Button is not a WebElement"
    while not clicked:
        with suppress(ElementClickInterceptedException):
            # Scroll to element and wait until it's in view
            if not isinstance(driver, WebElement):
                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", button)
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script(
                        "const rect = arguments[0].getBoundingClientRect();" "return rect.top >= 0 && rect.bottom <= window.innerHeight;", button
                    )
                )

            button.click()

            clicked = True

        if (datetime.now() - current_date).seconds > 10:
            logger.error("🦊 Button click failed, exiting ...")
            if not isinstance(driver, WebElement):
                driver.save_screenshot("error.png")
            exit(1)

    return clicked


def assert_alert_message(logger: Logger, driver, message: str):
    safe_get_element(logger, driver, By.XPATH, "//button[@data-flash-sidebar-open='']")

    sleep(0.3)

    assert_button_click(logger, driver, "//button[@data-flash-sidebar-open='']")

    error = False
    start_time = datetime.now()
    while (datetime.now() - start_time).seconds < 120:
        try:
            alerts: Union[WebElement, List[WebElement]] = safe_get_element(
                logger,
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
                logger.exception("🦊 Messages list not found, exiting ...")
                if not isinstance(driver, WebElement):
                    driver.save_screenshot("error.png")
                exit(1)
            error = True
            driver.refresh()

    is_in = False
    for alert in alerts:
        if message in alert.text:
            is_in = True
            break

    if not is_in:
        logger.error(f'🦊 Message "{message}" not found in one of the messages in the list, exiting ...')
        if not isinstance(driver, WebElement):
            driver.save_screenshot("error.png")
        exit(1)

    logger.info(f'🦊 Message "{message}" found in one of the messages in the list')
    assert_button_click(logger, driver, "//button[@data-flash-sidebar-close='']/*[local-name() = 'svg']")


def access_page(logger: Logger, driver, button: Union[bool, str, WebElement], name: str, message: bool = True, *, retries: int = 0, clicked: bool = False):
    if retries > 5:
        logger.error("🦊 Too many retries...")
        if not isinstance(driver, WebElement):
            driver.save_screenshot("error.png")
        exit(1)

    try:
        if not isinstance(button, bool) and not clicked:
            clicked = assert_button_click(logger, driver, button)

        sleep(1)

        current_time = datetime.now()

        while current_time + timedelta(seconds=45) > datetime.now() and f"/{name}" not in driver.current_url:
            sleep(1)

        if f"/{name}" not in driver.current_url:
            logger.error(f"🦊 Didn't get redirected to {name} page: {driver.current_url}, exiting ...")
            if not isinstance(driver, WebElement):
                driver.save_screenshot("error.png")
            exit(1)
    except TimeoutException:
        if "/loading" in driver.current_url:
            sleep(2)
            return access_page(logger, driver, button, name, message, retries=retries + 1, clicked=clicked)

        logger.error(f"🦊 {name.title()} page didn't load in time, exiting ...")
        if not isinstance(driver, WebElement):
            driver.save_screenshot("error.png")
        exit(1)
    except WebDriverException as we:
        if "connectionFailure" in str(we):
            logger.warning("🦊 Connection failure, retrying in 5s ...")
            driver.refresh()
            sleep(5)
            return access_page(logger, driver, button, name, message, retries=retries + 1, clicked=clicked)
        raise we

    if message:
        logger.info(f"🦊 {name.title()} page loaded successfully")


def wait_for_service(logger: Logger, service: str = "www.example.com"):
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get(f"http://{service}/ready", headers={"Host": service}, verify=False)
            status_code = resp.status_code
            text = resp.text

            if resp.status_code >= 500:
                logger.error(f"🦊 An error occurred while trying to reach {service}, exiting ...")
                exit(1)

            ready = status_code < 400 and "ready" in text

        if retries > 10:
            logger.error(f"🦊 Service {service} took too long to be ready, exiting ...")
            exit(1)
        elif not ready:
            retries += 1
            logger.warning(f"🦊 Waiting for {service} to be ready, retrying in 5s ...")
            sleep(5)
