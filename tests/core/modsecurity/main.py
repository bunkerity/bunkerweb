# -*- coding: utf-8 -*-
from contextlib import suppress
from os import getenv
from requests import get
from requests.exceptions import RequestException
from time import sleep
from traceback import format_exc

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            status_code = get("http://www.example.com", headers={"Host": "www.example.com"}).status_code

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    use_modsecurity = getenv("USE_MODSECURITY", "yes") == "yes"
    use_modsecurity_crs = getenv("USE_MODSECURITY_CRS", "yes") == "yes"

    print(
        "ℹ️ Sending a requests to http://www.example.com/?id=/etc/passwd ...",
        flush=True,
    )

    status_code = get("http://www.example.com/?id=/etc/passwd", headers={"Host": "www.example.com"}).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    if status_code == 403:
        if not use_modsecurity:
            print(
                "❌ ModSecurity should have been disabled, exiting ...",
                flush=True,
            )
            exit(1)
        elif not use_modsecurity_crs:
            print(
                "❌ ModSecurity CRS should have been disabled, exiting ...",
                flush=True,
            )
            exit(1)
    elif use_modsecurity and use_modsecurity_crs:
        print("❌ ModSecurity is not working as expected, exiting ...", flush=True)
        exit(1)

    print("✅ ModSecurity is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
