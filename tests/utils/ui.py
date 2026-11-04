from contextlib import suppress
from datetime import datetime, timedelta
from logging import Logger
from time import sleep
from typing import List, Optional, Union
from urllib.parse import urlparse
from requests import RequestException, get
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)


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


def assert_button_click(logger: Logger, driver, button: Union[str, WebElement], by: Optional[str] = None, *, error: bool = False):
    """Click `button`, retrying for 10s. `error=True` re-raises instead of ending the run, for the
    call sites where the target is optional (the wizard's confirm-DNS step only exists sometimes)
    and the caller suppresses the failure itself."""
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

    # A selector is re-resolved on every attempt. The DataTables pages redraw themselves (the
    # responsive plugin recomputes on every resize and tab switch), so a node found once can be
    # detached, replaced or momentarily unclickable by the time the click lands -- which is what
    # "could not be scrolled into view" and StaleElementReference mean here. Only a target that
    # stays unusable for the whole budget is a real failure.
    selector: Optional[str] = button if isinstance(button, str) else None
    deadline = datetime.now() + timedelta(seconds=10)
    reason = "button click failed"
    last_error: BaseException = TimeoutException(reason)

    while True:
        try:
            if selector is not None:
                # All matches, then the first DISPLAYED one. A DataTable renders more than one
                # node for the same cell (hidden columns keep their markup, and the scrolling
                # variants duplicate rows), so taking the first match in document order can hand
                # back a `display: none` twin. Firefox then answers "could not be scrolled into
                # view" -- and the in-view wait below does not catch it either, since a hidden
                # element's rect is all zeroes and passes `top >= 0 and bottom <= innerHeight`.
                # error=True: a missing element is retried here rather than ending the run, since
                # the redraw that makes a node stale also removes it for a frame or two.
                candidates: List[WebElement] = safe_get_element(logger, driver, by or By.XPATH, selector, multiple=True, error=True)  # type: ignore[assignment]
                if not isinstance(candidates, list):
                    candidates = [candidates]
                visible = [candidate for candidate in candidates if candidate.is_displayed()]
                if not visible:
                    # DataTables Responsive collapses the right-hand columns of a narrow table:
                    # the cell keeps its markup but is hidden until the row is expanded, and only
                    # then does Responsive move it into the visible child row. Expand the parent
                    # row of the first match and let the next attempt re-resolve it.
                    if not isinstance(driver, WebElement):
                        driver.execute_script(
                            "const tr = arguments[0].closest && arguments[0].closest('tr');"
                            "if (tr && !tr.classList.contains('parent')) {"
                            "  const control = tr.querySelector('td.dtr-control');"
                            "  if (control) control.click();"
                            "}",
                            candidates[0],
                        )
                    raise ElementNotInteractableException(f"matched {len(candidates)} node(s), none of them displayed")
                button = visible[0]

            assert isinstance(button, WebElement), "Button is not a WebElement"

            # Scroll to element and wait until it's in view.
            # `inline: 'center'` matters as much as `block`: the row-action icons live at the
            # right edge of a wide `table-responsive` table, and Firefox refuses to click an
            # element it cannot bring into the viewport horizontally ("could not be scrolled into
            # view") however well centred it is vertically. `instant` rather than `smooth` so the
            # click below does not race an animation that is still running.
            if not isinstance(driver, WebElement):
                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });", button)
                WebDriverWait(driver, 5).until(
                    lambda d: d.execute_script(
                        "const rect = arguments[0].getBoundingClientRect();" "return rect.top >= 0 && rect.bottom <= window.innerHeight;", button
                    )
                )

            button.click()
            return True
        except (ElementClickInterceptedException, ElementNotInteractableException, StaleElementReferenceException, TimeoutException) as e:
            reason = (getattr(e, "msg", None) or str(e) or e.__class__.__name__).strip().splitlines()[0]
            last_error = e

        if datetime.now() > deadline:
            if error:
                raise last_error
            logger.error(f'🦊 Could not click "{selector or "element"}" : {reason}, exiting ...')
            if not isinstance(driver, WebElement):
                driver.save_screenshot("error.png")
            exit(1)

        sleep(0.5)


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


# How long a navigation may take before we call it a failure. Generous on purpose: a page reached
# through the loading interstitial waits on the scheduler clearing the *_changed metadata flags,
# and the scheduler polls for changes once a minute -- so a wizard that saves at T+0 is only
# noticed at T+60, then has to render and push the configuration, and on SQLite it may sit behind
# a "Database is locked, waiting for it to be unlocked (timeout: 30s)" on top. The old 45s budget
# expired mid-cycle and reported "didn't get redirected" for a UI that was working correctly.
# This is a wait-until, so a fast environment still returns as soon as the page is there.
PAGE_LOAD_TIMEOUT_SECONDS = 180


def on_page(driver, name: str) -> bool:
    """Is the browser on the `name` page?

    Matches the URL *path* only. Matching the whole URL made
    `/loading?next=/home` count as the home page, so every login step declared success one
    second in, while still on the interstitial -- and the assertions that followed ran against
    the loading screen and failed on things that were simply not rendered there yet.
    """
    return f"/{name}" in urlparse(driver.current_url).path


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

        while current_time + timedelta(seconds=PAGE_LOAD_TIMEOUT_SECONDS) > datetime.now() and not on_page(driver, name):
            sleep(1)

        if not on_page(driver, name):
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
