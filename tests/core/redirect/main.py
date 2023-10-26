from contextlib import suppress
from os import getenv
from requests import get
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
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

    redirect_to = getenv("REDIRECT_TO", "")
    redirect_to_request_uri = getenv("REDIRECT_TO_REQUEST_URI", "no")

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print("ℹ️ Navigating to http://www.example.com/test ...", flush=True)
        driver.get("http://www.example.com/test")

        if redirect_to_request_uri == "yes":
            redirect_to += "/test"

        if not driver.current_url == redirect_to:
            print(
                f"❌ Expected redirect to {redirect_to}, got {driver.current_url} instead, exiting ...",
                flush=True,
            )
            exit(1)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
