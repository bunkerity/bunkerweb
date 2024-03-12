from logging import info as log_info, exception as log_exception
from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from wizard import DRIVER
from utils import access_page, assert_button_click, safe_get_element

exit_code = 0

try:
    log_info("Navigating to the cache page ...")
    access_page(DRIVER, "/html/body/aside[1]/div[1]/div[3]/ul/li[7]/a", "cache")

    log_info("Trying to open a cache file ...")

    assert_button_click(DRIVER, "//div[@data-cache-element='mmdb-asn/asn.mmdb']")

    file_content_elem = safe_get_element(DRIVER, By.XPATH, "//div[@id='editor']//div[@class='ace_content']")
    assert isinstance(file_content_elem, WebElement), "The file content element is not an instance of WebElement"
    if file_content_elem.text.strip() != "Download file to view content":
        log_exception("The cache file content is not correct, exiting ...")
        exit(1)

    assert_button_click(DRIVER, "//button[@data-cache-modal-submit='']")

    sleep(3)

    log_info("The cache file content is correct")

    log_info("✅ Cache page tests finished successfully")
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
