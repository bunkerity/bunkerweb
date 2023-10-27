# -*- coding: utf-8 -*-
from os import getenv
from requests import get
from requests.exceptions import RequestException
from traceback import format_exc

try:
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
