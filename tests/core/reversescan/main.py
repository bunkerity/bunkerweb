# -*- coding: utf-8 -*-
from re import search
from time import sleep
from fastapi import FastAPI
from os import getenv
from requests import get
from multiprocessing import Process
from traceback import format_exc
from uvicorn import run


fastapi_proc = None
if getenv("TEST_TYPE", "docker") == "docker":
    app = FastAPI()
    fastapi_proc = Process(target=run, args=(app,), kwargs=dict(host="0.0.0.0", port=80))
    fastapi_proc.start()

    sleep(1)

try:
    use_reverse_scan = getenv("USE_REVERSE_SCAN", "yes") == "yes"
    reverse_scan_ports = getenv("REVERSE_SCAN_PORTS", "80")

    print("ℹ️ Trying to access http://www.example.com ...", flush=True)
    status_code = get("http://www.example.com", headers={"Host": "www.example.com"}).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    if status_code == 403:
        pass
    elif use_reverse_scan and search(r"\b80\b", reverse_scan_ports):
        print(
            "❌ Request didn't return 403, but reverse scan is enabled and port 80 is in the reverse scan ports list, exiting ...",
            flush=True,
        )
        exit(1)

    print("✅ Reverse scan is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
finally:
    if fastapi_proc:
        fastapi_proc.terminate()
