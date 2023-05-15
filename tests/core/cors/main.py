from contextlib import suppress
from os import getenv
from requests import RequestException, get, head, options
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import JavascriptException
from traceback import format_exc
from time import sleep


try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            status_code = get(
                "https://www.example.com",
                headers={"Host": "www.example.com"},
                verify=False,
            ).status_code

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print(
                "⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True
            )
            sleep(5)

    firefox_options = Options()
    firefox_options.add_argument("--headless")

    use_cors = getenv("USE_CORS", "no")
    cors_allow_origin = getenv("CORS_ALLOW_ORIGIN", "*")
    cors_expose_headers = getenv("CORS_EXPOSE_HEADERS", "Content-Length,Content-Range")
    cors_max_age = getenv("CORS_MAX_AGE", "86400")
    cors_allow_credentials = getenv("CORS_ALLOW_CREDENTIALS", "no") == "yes"
    cors_allow_methods = getenv("CORS_ALLOW_METHODS", "GET, POST, OPTIONS")
    cors_allow_headers = getenv(
        "CORS_ALLOW_HEADERS",
        "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range",
    )

    if any(
        [
            cors_allow_origin != "*",
            cors_expose_headers != "Content-Length,Content-Range",
        ]
    ):
        print(
            "ℹ️ Sending a HEAD request to https://www.example.com ...",
            flush=True,
        )

        response = head(
            "https://www.example.com", headers={"Host": "www.example.com"}, verify=False
        )
        response.raise_for_status()

        if any(
            header in response.headers
            for header in (
                "Access-Control-Max-Age",
                "Access-Control-Allow-Credentials",
                "Access-Control-Allow-Methods",
                "Access-Control-Allow-Headers",
            )
        ):
            print(
                f"❌ One of the preflight request headers is present in the response headers, it should not be ...\nheaders: {response.headers}",
            )
            exit(1)
        elif cors_allow_origin != response.headers.get("Access-Control-Allow-Origin"):
            print(
                f"❌ The Access-Control-Allow-Origin header is set to {response.headers.get('Access-Control-Allow-Origin', 'missing')}, it should be {cors_allow_origin} ...\nheaders: {response.headers}",
                flush=True,
            )
            exit(1)
        elif cors_allow_origin != "*":
            print(
                f"✅ The Access-Control-Allow-Origin header is set to {cors_allow_origin} ...",
                flush=True,
            )
        elif cors_expose_headers != response.headers.get(
            "Access-Control-Expose-Headers"
        ):
            print(
                f"❌ The Access-Control-Expose-Headers header is set to {response.headers.get('Access-Control-Expose-Headers', 'missing')}, it should be {cors_expose_headers} ...\nheaders: {response.headers}",
                flush=True,
            )
            exit(1)
        elif cors_expose_headers != "Content-Length,Content-Range":
            print(
                f"✅ The Access-Control-Expose-Headers header is set to {cors_expose_headers} ...",
                flush=True,
            )

        exit(0)
    elif any(
        [
            cors_max_age != "86400",
            cors_allow_credentials,
            cors_allow_methods != "GET, POST, OPTIONS",
            cors_allow_headers
            != "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range",
        ]
    ):
        print(
            "ℹ️ Sending a preflight request to https://www.example.com ...",
            flush=True,
        )

        response = options(
            "https://www.example.com", headers={"Host": "www.example.com"}, verify=False
        )
        response.raise_for_status()

        if (
            not cors_allow_credentials
            and "Access-Control-Allow-Credentials" in response.headers
        ):
            print(
                f"❌ The Access-Control-Allow-Credentials header is present in the response headers while the setting CORS_ALLOW_CREDENTIALS is set to {cors_allow_credentials}, it should not be ...\nheaders: {response.headers}",
            )
            exit(1)
        elif cors_max_age != response.headers.get("Access-Control-Max-Age"):
            print(
                f"❌ The Access-Control-Max-Age header is set to {response.headers.get('Access-Control-Max-Age', 'missing')}, it should be {cors_max_age} ...\nheaders: {response.headers}",
                flush=True,
            )
            exit(1)
        elif cors_max_age != "86400":
            print(
                f"✅ The Access-Control-Max-Age header is set to {cors_max_age} ...",
                flush=True,
            )
        elif (
            cors_allow_credentials
            and "Access-Control-Allow-Credentials" not in response.headers
        ):
            print(
                f"❌ The Access-Control-Allow-Credentials header is not present in the response headers while the setting CORS_ALLOW_CREDENTIALS is set to {cors_allow_credentials}, it should be ...\nheaders: {response.headers}",
            )
            exit(1)
        elif cors_allow_methods != response.headers.get("Access-Control-Allow-Methods"):
            print(
                f"❌ The Access-Control-Allow-Methods header is set to {response.headers.get('Access-Control-Allow-Methods', 'missing')}, it should be {cors_allow_methods} ...\nheaders: {response.headers}",
            )
            exit(1)
        elif cors_allow_methods != "GET, POST, OPTIONS":
            print(
                f"✅ The Access-Control-Allow-Methods is set to {cors_allow_methods} ...",
                flush=True,
            )
        elif cors_allow_headers != response.headers.get("Access-Control-Allow-Headers"):
            print(
                f"❌ The Access-Control-Allow-Headers header is set to {response.headers.get('Access-Control-Allow-Headers', 'missing')}, it should be {cors_allow_headers} ...\nheaders: {response.headers}",
                flush=True,
            )
            exit(1)
        elif (
            cors_allow_headers
            != "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"
        ):
            print(
                f"✅ The Access-Control-Allow-Headers header is set to {cors_allow_headers} ...",
                flush=True,
            )
        else:
            print(
                f"✅ The Access-Control-Allow-Credentials header is present and set to {cors_allow_credentials} ...",
                flush=True,
            )

        exit(0)

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print(
            "ℹ️ Sending a javascript request to https://www.example.com ...",
            flush=True,
        )
        error = False

        try:
            driver.execute_script(
                """var xhttp = new XMLHttpRequest();
xhttp.open("GET", "https://www.example.com", false);
xhttp.setRequestHeader("Host", "www.example.com");
xhttp.send();"""
            )
        except JavascriptException as e:
            if not f"{e}".startswith("Message: NetworkError"):
                print(f"❌ {e}", flush=True)
            error = True

        if use_cors == "no" and not error:
            print("❌ CORS is enabled, it shouldn't be, exiting ...", flush=True)
            exit(1)
        elif use_cors == "yes" and error:
            print("❌ CORS are not working as expected, exiting ...", flush=True)
            exit(1)

    print("✅ CORS are working as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
