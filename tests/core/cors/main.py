from contextlib import suppress
from os import getenv
from requests import RequestException, get, head, options
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import JavascriptException
from traceback import format_exc
from time import sleep


try:
    ssl = getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes"

    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get(
                f"http{'s' if ssl else ''}://www.example.com/ready",
                headers={"Host": "www.example.com"},
                verify=False,
            )
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

    use_cors = getenv("USE_CORS", "no") == "yes"
    cors_allow_origin = getenv("CORS_ALLOW_ORIGIN", "*").replace("\\", "").replace("^", "").replace("$", "")
    cors_expose_headers = getenv("CORS_EXPOSE_HEADERS", "Content-Length,Content-Range")
    cors_max_age = getenv("CORS_MAX_AGE", "86400")
    cors_allow_credentials = "true" if getenv("CORS_ALLOW_CREDENTIALS", "no") == "yes" else "false"
    cors_allow_methods = getenv("CORS_ALLOW_METHODS", "GET, POST, OPTIONS")
    cors_allow_headers = getenv(
        "CORS_ALLOW_HEADERS",
        "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range",
    )

    print(
        f"ℹ️ Sending a HEAD request to http{'s' if ssl else ''}://www.example.com ...",
        flush=True,
    )

    response = head(
        f"http{'s' if ssl else ''}://www.example.com",
        headers={
            "Host": "www.example.com",
            "Origin": f"http{'s' if ssl else ''}://app1.example.com",
        },
        verify=False,
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

    for header, value in (
        ("Access-Control-Allow-Origin", cors_allow_origin),
        ("Access-Control-Expose-Headers", cors_expose_headers),
    ):
        if use_cors:
            if value != response.headers.get(header):
                print(
                    f"❌ The {header} header is set to \"{response.headers.get(header, 'header missing')}\", it should be \"{value}\" ...\nheaders: {response.headers}",
                    flush=True,
                )
                exit(1)
            print(
                f'✅ The {header} header is set to "{value}" ...',
                flush=True,
            )
        else:
            if header in response.headers:
                print(
                    f'❌ The {header} header is present in the response headers while the setting USE_CORS is set to "no", it should not be ...\nheaders: {response.headers}',
                )
                exit(1)
            print(
                f"✅ The {header} header is not present in the response headers as expected ...",
                flush=True,
            )

    sleep(1)

    print(
        f"ℹ️ Sending a preflight request to http{'s' if ssl else ''}://www.example.com/options ...",
        flush=True,
    )

    response = options(
        f"http{'s' if ssl else ''}://www.example.com/options",
        headers={
            "Host": "www.example.com",
            "Origin": f"http{'s' if ssl else ''}://app1.example.com",
        },
        verify=False,
    )
    if response.status_code != 404:
        response.raise_for_status()

    if use_cors:
        if cors_allow_credentials == "false" and "Access-Control-Allow-Credentials" in response.headers:
            print(
                f'❌ The Access-Control-Allow-Credentials header is present in the response headers while the setting CORS_ALLOW_CREDENTIALS is set to "no", it should not be ...\nheaders: {response.headers}',
            )
            exit(1)
        elif cors_allow_credentials == "true" and "Access-Control-Allow-Credentials" not in response.headers:
            print(
                f'❌ The Access-Control-Allow-Credentials header is not present in the response headers while the setting CORS_ALLOW_CREDENTIALS is set to "yes", it should be ...\nheaders: {response.headers}',
            )
            exit(1)
        print(
            f"✅ The Access-Control-Allow-Credentials header is{' not' if cors_allow_credentials == 'false' else ''} present as expected ...",
            flush=True,
        )

    for header, value in (
        ("Access-Control-Allow-Credentials", cors_allow_credentials),
        ("Access-Control-Max-Age", cors_max_age),
        ("Access-Control-Allow-Methods", cors_allow_methods),
        ("Access-Control-Allow-Headers", cors_allow_headers),
    ):
        if use_cors:
            if header == "Access-Control-Allow-Credentials" and cors_allow_credentials == "false":
                continue

            if value != response.headers.get(header):
                print(
                    f"❌ The {header} header is set to \"{response.headers.get(header, 'header missing')}\", it should be \"{value}\" ...\nheaders: {response.headers}",
                    flush=True,
                )
                exit(1)
            print(
                f'✅ The {header} header is set to "{value}" ...',
                flush=True,
            )
        else:
            if header in response.headers:
                print(
                    f'❌ The {header} header is present in the response headers while the setting USE_CORS is set to "no", it should not be ...\nheaders: {response.headers}',
                )
                exit(1)
            print(
                f"✅ The {header} header is not present in the response headers as expected ...",
                flush=True,
            )

    if any(
        [
            cors_expose_headers != "Content-Length,Content-Range",
            cors_max_age != "86400",
            cors_allow_credentials == "true",
            cors_allow_methods != "GET, POST, OPTIONS",
            cors_allow_headers != "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range",
        ]
    ):
        exit(0)

    sleep(0.5)

    firefox_options = Options()
    firefox_options.add_argument("--headless")

    print("ℹ️ Starting Firefox ...", flush=True)
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()

        print("ℹ️ Navigating to http://app1.example.com ...", flush=True)
        driver.get(f"http{'s' if ssl else ''}://app1.example.com")

        sleep(1.5)

        print(
            f"ℹ️ Sending a javascript request to http{'s' if ssl else ''}://www.example.com ...",
            flush=True,
        )
        error = False

        try:
            driver.execute_script(
                f"""
                   var xhttp = new XMLHttpRequest();
                   xhttp.open("GET", "http{'s' if ssl else ''}://www.example.com", false);
                   xhttp.setRequestHeader("Host", "www.example.com");
                   xhttp.send();
                """
            )
        except JavascriptException as e:
            if not f"{e}".startswith("Message: NetworkError"):
                print(f"❌ {e}", flush=True)
            error = True

        if not use_cors and not error:
            print("❌ CORS is enabled, it shouldn't be, exiting ...", flush=True)
            exit(1)
        elif use_cors and error:
            print("❌ CORS are not working as expected, exiting ...", flush=True)
            exit(1)

    print("✅ CORS are working as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
