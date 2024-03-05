from contextlib import suppress
from os import getenv
from pathlib import Path
from uuid import uuid4
from requests import RequestException, Session, get
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException
from traceback import format_exc
from time import sleep

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"}, verify=False, allow_redirects=True)
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

    Path("error.png").unlink(missing_ok=True)
    firefox_options = Options()
    firefox_options.add_argument("--headless")

    USE_REVERSE_PROXY = getenv("USE_REVERSE_PROXY", "no") == "yes"
    REVERSE_PROXY_INTERCEPT_ERRORS = getenv("REVERSE_PROXY_INTERCEPT_ERRORS", "yes") == "yes"
    REVERSE_PROXY_WS = getenv("REVERSE_PROXY_WS", "no") == "yes"
    REVERSE_PROXY_KEEPALIVE = getenv("REVERSE_PROXY_KEEPALIVE", "no") == "yes"
    REVERSE_PROXY_HEADERS = getenv("REVERSE_PROXY_HEADERS", "")
    REVERSE_PROXY_HEADERS_CLIENT = getenv("REVERSE_PROXY_HEADERS_CLIENT", "")
    REVERSE_PROXY_AUTH_REQUEST = getenv("REVERSE_PROXY_AUTH_REQUEST", "")
    REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL = getenv("REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL", "")

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print("ℹ️ Navigating to http://www.example.com/admin ...", flush=True)
        driver.get("http://www.example.com/admin")
        content = driver.page_source

        if USE_REVERSE_PROXY and "BunkerWeb Forever!" not in content:
            if REVERSE_PROXY_AUTH_REQUEST and REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL:
                if "This is the authentication page" not in content:
                    print(f"❌ The reverse proxy is not redirecting to the authentication page, exiting ...\n{content}", flush=True)
                    exit(1)
                print("✅ The reverse proxy is redirecting to the authentication page", flush=True)
                exit(0)
            print("❌ The reverse proxy is not working properly, exiting ...", flush=True)
            exit(1)
        elif not USE_REVERSE_PROXY and "BunkerWeb Forever!" in content:
            print("❌ The reverse proxy is not disabled, exiting ...", flush=True)
            exit(1)

        print("✅ The reverse proxy is behaving as expected", flush=True)

        if USE_REVERSE_PROXY:
            random_endpoint = f"/{uuid4()}"
            print(f"ℹ️ Navigating to http://www.example.com{random_endpoint} to test the reverse proxy error interception ...", flush=True)
            driver.get(f"http://www.example.com{random_endpoint}")
            content = driver.page_source

            if '{"detail":"Not Found"}' in content and REVERSE_PROXY_INTERCEPT_ERRORS:
                print("❌ The default error page is being displayed, exiting ...", flush=True)
                exit(1)
            elif '{"detail":"Not Found"}' not in content and not REVERSE_PROXY_INTERCEPT_ERRORS:
                print(f"❌ The default error page is not being displayed, exiting ...\n{content}", flush=True)
                exit(1)

            print("✅ The reverse proxy error interception is behaving as expected", flush=True)

            print("ℹ️ Navigating to ws://www.example.com/ws to test the reverse proxy WebSocket ...", flush=True)
            connected = False
            with suppress(WebSocketBadStatusException):
                ws = create_connection("ws://www.example.com/ws")
                ws.send("BunkerWeb Forever!")
                response = ws.recv()
                print(f"ℹ️ Received message from WebSocket: {response}", flush=True)
                ws.close()
                connected = True

            if REVERSE_PROXY_WS and not connected:
                print("❌ The reverse proxy WebSocket is not working properly, exiting ...", flush=True)
                exit(1)
            elif not REVERSE_PROXY_WS and connected:
                print("❌ The reverse proxy WebSocket is not disabled, exiting ...", flush=True)
                exit(1)

            print("✅ The reverse proxy WebSocket is behaving as expected", flush=True)

    if USE_REVERSE_PROXY:
        print("ℹ️ Sending a request to http://www.example.com/headers to test the reverse proxy headers and the keep-alive ...", flush=True)
        with Session() as session:
            resp = session.post("http://www.example.com/headers", headers={"Host": "www.example.com"}, verify=False, allow_redirects=True)

            if resp.status_code == 505:
                print("❌ The HTTP version is not 1.1, exiting ...", flush=True)
                exit(1)
            elif resp.status_code == 426:
                print("❌ The HTTP version is 1.1 but the keep-alive is disabled, exiting ...", flush=True)
                exit(1)
            elif resp.status_code == 400:
                print("❌ Some headers have the wrong value, exiting ...", flush=True)
                exit(1)
            elif resp.status_code == 412:
                print("❌ Some headers are missing, exiting ...", flush=True)
                exit(1)
            elif resp.status_code != 200:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            print("✅ The reverse proxy headers and keep-alive are behaving as expected", flush=True)

            print("ℹ️ Checking the headers received ...", flush=True)
            headers = {header.split(" ")[0].lower(): header.split(" ")[1] for header in REVERSE_PROXY_HEADERS_CLIENT.split(";") if header}
            print(f"ℹ️ Headers to check: {headers}", flush=True)
            print(f"ℹ️ Headers received: {resp.headers}", flush=True)
            found = 0
            for name, value in resp.headers.items():
                name = name.lower()
                if name in headers:
                    found += 1
                    if value != headers[name]:
                        print(f"❌ The header {name} has the wrong value ({value} instead of {headers[name]}), exiting ...", flush=True)
                        exit(1)
            if found != len(headers):
                print("❌ Some headers are missing, exiting ...", flush=True)
                exit(1)

            print("✅ The headers received are behaving as expected", flush=True)

            if REVERSE_PROXY_AUTH_REQUEST:
                print("ℹ️ Checking if the authentication endpoint was accessed ...", flush=True)
                resp = session.get("http://www.example.com/check-auth", headers={"Host": "www.example.com"}, verify=False, allow_redirects=True)

                if resp.status_code != 200:
                    print("❌ An error occurred with the server, exiting ...", flush=True)
                    exit(1)

                data = resp.json()
                if not data["asked_auth"]:
                    print("❌ The authentication endpoint was not accessed, exiting ...", flush=True)
                    exit(1)

                print("✅ The authentication endpoint was accessed", flush=True)

    print("✅ All tests passed", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
