from contextlib import suppress
from os import getenv
from requests import RequestException, get, head
from traceback import format_exc
from time import sleep


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

    use_gzip = getenv("USE_GZIP", "no") == "yes"

    print(
        "ℹ️ Sending a HEAD request to http://www.example.com ...",
        flush=True,
    )

    response = head(
        "http://www.example.com",
        headers={"Host": "www.example.com", "Accept-Encoding": "gzip"},
    )
    response.raise_for_status()

    if not use_gzip and response.headers.get("Content-Encoding", "").lower() == "gzip":
        print(f"❌ Content-Encoding header is present even if Gzip is deactivated, exiting ...\nheaders: {response.headers}")
        exit(1)
    elif use_gzip and response.headers.get("Content-Encoding", "").lower() != "gzip":
        print(f"❌ Content-Encoding header is not present or with the wrong value even if Gzip is activated, exiting ...\nheaders: {response.headers}")
        exit(1)

    print("✅ Gzip is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
