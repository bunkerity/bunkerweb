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

            if resp.status_code >= 500:
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

    test_type = getenv("USE_ANTIBOT", "no")
    antibot_uri = getenv("ANTIBOT_URI", "/challenge")

    if test_type != "javascript":
        print("ℹ️ Starting Firefox ...", flush=True)
        with webdriver.Firefox(options=firefox_options) as driver:
            driver.delete_all_cookies()
            driver.maximize_window()

            print("ℹ️ Navigating to http://www.example.com ...", flush=True)

            driver.get("http://www.example.com")

            if driver.current_url.endswith(antibot_uri) and test_type == "no":
                print("❌ Antibot is enabled, it shouldn't be ...", flush=True)
                exit(1)
            elif test_type == "captcha":
                if not driver.current_url.endswith(antibot_uri):
                    print("❌ Antibot is disabled or the endpoint is wrong ...", flush=True)
                    exit(1)
                try:
                    driver.find_element(By.XPATH, "//input[@name='captcha']")
                except NoSuchElementException:
                    print("❌ The captcha input is missing ...", flush=True)
                    exit(1)

                print(
                    f"✅ The captcha input is present{' and the endpoint is correct' if antibot_uri != '/challenge' else ''} ...",
                    flush=True,
                )
            else:
                print("✅ Antibot is disabled, as expected ...", flush=True)
    else:
        status_code = get(
            "http://www.example.com",
            headers={"Host": "www.example.com"},
            allow_redirects=False,
        ).status_code
        if status_code >= 500:
            print("ℹ️ An error occurred with the server, exiting ...", flush=True)
            exit(1)
        elif status_code != 302:
            print(
                "❌ The server should have redirected to the antibot page ...",
                flush=True,
            )
            exit(1)

        print("✅ Status code is 302, as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
