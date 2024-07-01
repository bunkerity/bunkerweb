from contextlib import suppress
from os import getenv, sep
from os.path import join
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

    use_dnsbl = getenv("USE_DNSBL", "yes") == "yes"
    dnsbl_list = getenv("DNSBL_LIST", "")
    TEST_TYPE = getenv("TEST_TYPE", "docker")

    print(
        "ℹ️ Sending a request to http://www.example.com ...",
        flush=True,
    )
    passed = False
    retries = 0

    while not passed and retries < 10:
        status_code = get(
            "http://www.example.com", headers={"Host": "www.example.com"} | ({"X-Forwarded-For": getenv("IP_ADDRESS", "")} if TEST_TYPE == "linux" else {})
        ).status_code

        if status_code == 403:
            if not use_dnsbl:
                print("❌ The request was rejected, but DNSBL is disabled, exiting ...")
                exit(1)
            elif not dnsbl_list:
                print("❌ The request was rejected, but DNSBL list is empty, exiting ...")
                exit(1)
        elif use_dnsbl and dnsbl_list:
            if retries <= 10:
                found = False
                with open(join(sep, "var", "log", "bunkerweb", "error.log"), "r") as f:
                    for line in f.readlines():
                        if "error while doing A DNS query for" in line:
                            print(
                                f"⚠ Found the following error in the logs: {line}, retrying in 5s ...",
                                flush=True,
                            )
                            found = True
                            break

                if found:
                    retries += 1
                    sleep(5)
                    continue

            print(f'❌ The request was not rejected, but DNSBL list is equal to "{dnsbl_list}", exiting ...')
            exit(1)

        passed = True

    print("✅ DNSBL is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
