from os import getenv
from requests import get
from requests.exceptions import RequestException
from traceback import format_exc

try:

    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):      
            resp = get(
                f"http://www.example.com/ready",
                headers={"Host": "www.example.com"},
                verify=False,
                allow_redirects=True
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

    use_custom_ssl = getenv("USE_CUSTOM_SSL", "no") == "yes"

    print(
        "ℹ️ Sending a request to http://www.example.com ...",
        flush=True,
    )

    try:
        get("http://www.example.com", headers={"Host": "www.example.com"})
    except RequestException:
        if not use_custom_ssl:
            print(
                "❌ The request failed even though the Custom Cert isn't activated, exiting ...",
                flush=True,
            )
            exit(1)

    if not use_custom_ssl:
        print("✅ The Custom Cert isn't activated, as expected ...", flush=True)
        exit(0)

    print(
        "ℹ️ Sending a request to https://www.example.com ...",
        flush=True,
    )

    try:
        get("https://www.example.com", headers={"Host": "www.example.com"}, verify=False)
    except RequestException:
        print(
            "❌ The request failed even though the Custom Cert is activated, exiting ...",
            flush=True,
        )
        exit(1)

    print("✅ The Custom Cert is activated, as expected ...", flush=True)
except SystemExit as e:
    exit(e.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
