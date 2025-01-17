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

            ready = status_code <= 401 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    firefox_options = Options()
    firefox_options.add_argument("--headless")

    use_auth_basic = getenv("USE_AUTH_BASIC", "no")
    auth_basic_location = getenv("AUTH_BASIC_LOCATION", "sitewide")
    auth_basic_username = getenv("AUTH_BASIC_USER", "bunkerity")
    auth_basic_password = getenv("AUTH_BASIC_PASSWORD", "Secr3tP@ssw0rd")

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        if use_auth_basic == "no" or auth_basic_location != "sitewide":
            print("ℹ️ Navigating to http://www.example.com ...", flush=True)
            driver.get("http://www.example.com")

            sleep(2)

            try:
                driver.find_element(By.XPATH, "//img[@alt='NGINX Logo']")
            except NoSuchElementException:
                print("❌ The page is not accessible ...", flush=True)
                exit(1)

            if use_auth_basic == "no":
                print("✅ Auth-basic is disabled, as expected ...", flush=True)
            else:
                print(
                    f"ℹ️ Trying to access http://www.example.com{auth_basic_location} ...",
                    flush=True,
                )
                status_code = get(
                    f"http://www.example.com{auth_basic_location}",
                    headers={"Host": "www.example.com"},
                ).status_code

                if status_code != 401:
                    print("❌ The page is accessible without auth-basic ...", flush=True)
                    exit(1)
                print(
                    "✅ Auth-basic is enabled and working in the expected location ...",
                )
        else:
            print("ℹ️ Trying to access http://www.example.com ...", flush=True)
            status_code = get("http://www.example.com", headers={"Host": "www.example.com"}).status_code

            if status_code != 401:
                print("❌ The page is accessible without auth-basic ...", flush=True)
                exit(1)

            sleep(2)

            print(
                f"ℹ️ Trying to access http://{auth_basic_username}:{auth_basic_password}@www.example.com ...",
                flush=True,
            )
            driver.get(f"http://{auth_basic_username}:{auth_basic_password}@www.example.com")

            try:
                driver.find_element(By.XPATH, "//img[@alt='NGINX Logo']")
            except NoSuchElementException:
                print("❌ The page is not accessible ...", flush=True)
                exit(1)
            print("✅ Auth-basic is enabled and working, as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
