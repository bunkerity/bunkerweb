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

            ready = status_code < 400 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    inject_body = getenv("INJECT_BODY", "")

    page_text = get("http://www.example.com", headers={"Host": "www.example.com"}).text

    if inject_body not in page_text:
        print("❌ The service is ready but the injected body is not present, exiting ...", flush=True)
        exit(1)

    print(
        "✅ The service is ready and the injected body is present, exiting ...",
        flush=True,
    )
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
