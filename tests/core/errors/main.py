from contextlib import suppress
from os import getenv
from requests import get
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException
from time import sleep
from traceback import format_exc

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"})
            status_code = resp.status_code
            text = resp.text

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    firefox_options = Options()
    firefox_options.add_argument("--headless")

    errors = getenv("ERRORS", "")
    intercepted_error_codes = getenv("INTERCEPTED_ERROR_CODES", "400 401 403 404 405 413 429 500 501 502 503 504")

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print(
            "ℹ️ Navigating to http://www.example.com/?id=/etc/passwd ...",
            flush=True,
        )
        driver.get("http://www.example.com/?id=/etc/passwd")

        default_message = None
        with suppress(NoSuchElementException):
            default_message = driver.find_element(By.XPATH, "//p[contains(text(), 'This website is protected with')]")

        if default_message and (errors or intercepted_error_codes != "400 401 403 404 405 413 429 500 501 502 503 504"):
            print(
                "❌ The default error page is being displayed, exiting ...",
                flush=True,
            )
            exit(1)
        elif not default_message and not errors and intercepted_error_codes == "400 401 403 404 405 413 429 500 501 502 503 504":
            print(
                "❌ The default error page is not being displayed, exiting ...",
                flush=True,
            )
            exit(1)

        if errors:
            custom_message = None
            with suppress(NoSuchElementException):
                custom_message = driver.find_element(By.XPATH, "//h1[contains(text(), 'It Works!')]")

            if not custom_message:
                print(
                    "❌ The custom error page is not being displayed while a custom one has been provided, exiting ...",
                    flush=True,
                )
                exit(1)

        if intercepted_error_codes != "400 401 403 404 405 413 429 500 501 502 503 504":
            nginx_message = None
            with suppress(NoSuchElementException):
                nginx_message = driver.find_element(By.XPATH, "//center[contains(text(), 'nginx')]")

            if not nginx_message:
                print(
                    "❌ The default nginx error page is not being displayed while a custom one has been provided, exiting ...",
                    flush=True,
                )
                exit(1)

    print("✅ Errors are working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
