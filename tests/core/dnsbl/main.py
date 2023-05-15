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
            status_code = get(
                "http://www.example.com", headers={"Host": "www.example.com"}, timeout=3
            ).status_code

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400 or status_code == 403

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print(
                "⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True
            )
            sleep(5)

    use_dnsbl = getenv("USE_DNSBL", "yes") == "yes"
    dnsbl_list = getenv("DNSBL_LIST", "bl.blocklist.de problems.dnsbl.sorbs.net")

    print(
        "ℹ️ Sending a request to http://www.example.com ...",
        flush=True,
    )

    status_code = get(
        f"http://www.example.com", headers={"Host": "www.example.com"}
    ).status_code

    if status_code == 403:
        if not use_dnsbl:
            print("❌ The request was rejected, but DNSBL is disabled, exiting ...")
            exit(1)
        elif dnsbl_list == "bl.blocklist.de problems.dnsbl.sorbs.net":
            print(
                '❌ The request was rejected, but DNSBL list is equal to "bl.blocklist.de problems.dnsbl.sorbs.net", exiting ...'
            )
            exit(1)
    elif use_dnsbl and dnsbl_list != "bl.blocklist.de problems.dnsbl.sorbs.net":
        print(
            f'❌ The request was not rejected, but DNSBL list is equal to "{dnsbl_list}", exiting ...'
        )
        exit(1)

    print("✅ DNSBL is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
