from contextlib import suppress
from os import getenv
from subprocess import run
from requests import get, post
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

    sessions_secret = getenv("SESSIONS_SECRET", "random")  # TODO : also test the secret
    sessions_name = getenv("SESSIONS_NAME", "random")
    TEST_TYPE = getenv("TEST_TYPE", "docker")
    first_cookie = None

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print("ℹ️ Navigating to http://www.example.com ...", flush=True)
        driver.get("http://www.example.com")

        if sessions_name != "random":
            if not driver.get_cookie(sessions_name):
                print(f"❌ Cookie {sessions_name} not found, exiting ...", flush=True)
                exit(1)
            print(f"✅ Cookie {sessions_name} found", flush=True)
            exit(0)

        first_cookie = driver.get_cookies()[0]

    print("ℹ️ Reloading BunkerWeb ...", flush=True)

    if TEST_TYPE == "docker":
        response = post("http://192.168.0.2:5000/reload", headers={"Host": "bwapi"})

        if response.status_code != 200:
            print("❌ An error occurred when restarting BunkerWeb, exiting ...", flush=True)
            exit(1)

        data = response.json()

        if data["status"] != "success":
            print("❌ An error occurred when restarting BunkerWeb, exiting ...", flush=True)
            exit(1)

        sleep(5)
    else:
        proc = run(["sudo", "systemctl", "restart", "bunkerweb"], check=False)
        if proc.returncode != 0:
            print("❌ An error occurred when restarting BunkerWeb, exiting ...", flush=True)
            exit(1)

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
                print("❌ BunkerWeb took too long to be ready, exiting ...", flush=True)
                exit(1)
            elif not ready:
                retries += 1
                print("⚠️ Waiting for BunkerWeb to be ready, retrying in 5s ...", flush=True)
                sleep(5)

    print("ℹ️ Starting Firefox again ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print("ℹ️ Navigating to http://www.example.com ...", flush=True)
        driver.get("http://www.example.com")

        cookie = driver.get_cookies()[0]

        if sessions_name == "random":
            if TEST_TYPE == "docker" and first_cookie["name"] != cookie["name"]:
                print(
                    "❌ The cookie name should not have changed after a simple reload, exiting ...",
                    flush=True,
                )
                exit(1)
            elif TEST_TYPE == "linux" and first_cookie["name"] == cookie["name"]:
                print(
                    "❌ The cookie name should have changed after a full reload, exiting ...",
                    flush=True,
                )
                exit(1)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
