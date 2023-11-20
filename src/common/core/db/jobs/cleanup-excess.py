#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("api",),
        ("utils",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger  # type: ignore

LOGGER = setup_logger("CLEANUP-EXCESS", getenv("LOG_LEVEL", "INFO"))
CORE_API = API(getenv("API_ADDR", ""), "job-cleanup-excess")
CORE_TOKEN = getenv("CORE_TOKEN", None)
status = 0


def send_request(url: str, data: dict, retries: int = 0) -> int:
    sent, err, status, resp = CORE_API.request(
        "POST",
        url,
        data=data,
        additonal_headers={"Authorization": f"Bearer {CORE_TOKEN}"} if CORE_TOKEN else {},
    )

    if not sent:
        LOGGER.error(f"Can't send API request to {CORE_API.endpoint}actions/cleanup : {err}")
        return 2
    elif status == 503:
        if retries >= 3:
            LOGGER.error(f"Can't send API request to {CORE_API.endpoint}actions/cleanup : {err}")
            return 2
        retry_after = resp.headers.get("Retry-After", 1)
        retry_after = float(retry_after)
        sleep(retry_after)
        return send_request(url, data, retries + 1)
    elif status != 200:
        LOGGER.error(f"Error while sending API request to {CORE_API.endpoint}actions/cleanup : status = {status}, resp = {resp}")
        return 2

    return 0


try:
    status = send_request("/db/jobs/cleanup?method=core", {"limit": getenv("DATABASE_MAX_JOBS_RUNS", "1000")})
    other_status = send_request("/db/actions/cleanup?method=core", {"limit": getenv("DATABASE_MAX_ACTIONS", "10000")})
    status = status or other_status
except:
    status = 2
    LOGGER.error(f"Exception while running cleanup-excess.py :\n{format_exc()}")

sys_exit(status)
