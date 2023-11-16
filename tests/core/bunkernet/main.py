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

    use_bunkernet = getenv("USE_BUNKERNET", "yes") == "yes"
    bunkernet_server = getenv("BUNKERNET_SERVER")

    if not bunkernet_server:
        print("❌ BunkerNet server not specified, exiting ...", flush=True)
        exit(1)

    instance_id = get(f"{bunkernet_server}/instance_id").json()["data"]

    if use_bunkernet and not instance_id:
        print("❌ BunkerNet plugin did not register, exiting ...", flush=True)
        exit(1)
    elif not use_bunkernet and instance_id:
        print("❌ BunkerNet plugin registered but it shouldn't, exiting ...", flush=True)
        exit(1)
    elif not use_bunkernet and not instance_id:
        print("✅ BunkerNet plugin is disabled and not registered ...", flush=True)
        exit(0)

    print("ℹ️ Sending a request to http://www.example.com/?id=/etc/passwd ...", flush=True)

    status_code = get("http://www.example.com/?id=/etc/passwd", headers={"Host": "www.example.com", "X-Forwarded-For": "1.0.0.3"}).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    if status_code != 403:
        print("❌ The request was not blocked, exiting ...", flush=True)
        exit(1)

    sleep(2)

    report_num = get(f"{bunkernet_server}/report_num").json()["data"]

    if report_num < 1:
        print("❌ The report was not sent, exiting ...", flush=True)
        exit(1)

    print("✅ BunkerNet is working as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
