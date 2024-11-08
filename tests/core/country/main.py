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
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"})
            status_code = resp.status_code
            text = resp.text

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400 or status_code == 403 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    country = getenv("COUNTRY")
    blacklist_country = getenv("BLACKLIST_COUNTRY", "")
    whitelist_country = getenv("WHITELIST_COUNTRY", "")

    print(
        "ℹ️ Sending a request to http://www.example.com ...",
        flush=True,
    )

    status_code = get(
        "http://www.example.com",
        headers={"Host": "www.example.com"}
        | ({"X-Forwarded-For": "213.186.33.5" if country == "FR" else "8.0.0.3"} if getenv("TEST_TYPE", "docker") == "linux" else {}),
    ).status_code

    if status_code == 403:
        if not blacklist_country and not whitelist_country:
            print(
                "❌ Got rejected even though there are no country blacklisted or whitelisted, exiting ...",
                flush=True,
            )
            exit(1)
        elif country == whitelist_country:
            print(
                f"❌ Got rejected even if the current country ({country}) is whitelisted, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Got rejected, as expected ...")
    else:
        if country == blacklist_country:
            print(
                f"❌ Didn't get rejected even if the current country ({country}) is blacklisted, exiting ...",
                flush=True,
            )
            exit(1)

        print("✅ Didn't get rejected, as expected ...")
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
