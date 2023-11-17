#!/usr/bin/python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from hashlib import sha512
from inspect import getsourcefile
from io import BytesIO
from os.path import normpath, sep
from pathlib import Path
from re import IGNORECASE, compile as re_compile
from sys import _getframe
from threading import Lock
from time import sleep
from traceback import format_exc
from typing import Literal, Optional, Tuple, Union

from requests import Response

lock = Lock()


minute_rx = r"[1-5]?\d"
day_rx = r"(3[01]|[12][0-9]|[1-9])"
month_rx = r"(1[0-2]|[1-9]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
week_day_rx = r"([0-6]|sun|mon|tue|wed|thu|fri|sat)"
cron_rx = (
    r"^(?P<minute>(?!,)((^|,)(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?))+)\s"
    + r"(?P<hour>(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?)(,(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?))*)\s"
    + r"(?P<day>(\*(/\d+)?|{day_rx}(-{day_rx}|/\d+)?)(,(\*(/\d+)?|{day_rx}(-{day_rx}|/\d+)?))*)\s"
    + r"(?P<month>(\*(/\d+)?|{month_rx}(-{month_rx}|/\d+)?)(,(\*(/\d+)?|{month_rx}(-{month_rx}|/\d+)?))*)\s"
    + r"(?P<week_day>(\*(/\d+)?|{week_day_rx}(-{week_day_rx}|/\d+)?)(,(\*(/\d+)?|{week_day_rx}(-{week_day_rx}|/\d+)?))*)$"
).format(
    minute_rx=minute_rx,
    day_rx=day_rx,
    month_rx=month_rx,
    week_day_rx=week_day_rx,
)
CRON_RX = re_compile(cron_rx, IGNORECASE)


def file_hash(file: Union[str, Path]) -> str:
    _sha512 = sha512()
    with open(normpath(file), "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _sha512.update(data)
    return _sha512.hexdigest()


def bytes_hash(bio: Union[bytes, BytesIO]) -> str:
    if isinstance(bio, bytes):
        bio = BytesIO(bio)  # type: ignore (bio will always be a bytes object in this case)

    assert isinstance(bio, BytesIO)

    _sha512 = sha512()
    while True:
        data = bio.read(1024)
        if not data:
            break
        _sha512.update(data)
    bio.seek(0)
    return _sha512.hexdigest()


# TODO make a class instead of the following functions


def get_cache(
    name: str,
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
    with_info: bool = False,
    with_data: bool = True,
) -> Optional[Union[dict, Response]]:
    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return None
    source_path = Path(source_file)

    cache_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name)
    if cache_path.is_file():
        return (
            {}
            | (
                {
                    "last_update": cache_path.stat().st_mtime,
                    "checksum": file_hash(cache_path),
                }
                if with_info
                else {}
            )
            | ({"data": cache_path.read_bytes()} if with_data else {})
        )

    if not job_name:
        job_name = source_path.name.replace(".py", "")

    sent, _, status, resp = api.request(
        "GET",
        f"/jobs/{job_name}/cache/{name}?method=core",
        data={"service_id": service_id, "with_info": with_info, "with_data": with_data},
        additonal_headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
    )

    if not sent or status not in (200, 503):
        return None
    elif status == 503:
        retry_after = resp.headers.get("Retry-After", 1)
        retry_after = float(retry_after)
        sleep(retry_after)
        return get_cache(
            name,
            api,
            api_token,
            job_name=job_name,
            service_id=service_id,
            with_info=with_info,
            with_data=with_data,
        )

    return resp.json() if resp.headers.get("Content-Type") == "application/json" else resp


def is_cached_file(
    name: str,
    expire: Union[Literal["hour"], Literal["day"], Literal["week"], Literal["month"]],
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, bool]:
    cache_info = None
    is_cached = False

    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return False, False
    source_path = Path(source_file)

    cache_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name)
    if cache_path.is_file():
        cache_info = {"last_update": cache_path.stat().st_mtime}

    try:
        if not cache_info:
            if not job_name:
                job_name = source_path.name.replace(".py", "")

            cache_info = get_cache(
                name,
                api,
                api_token,
                with_info=True,
                with_data=False,
                job_name=job_name,
                service_id=service_id,
            )

        if cache_info and isinstance(cache_info, dict):
            current_time = datetime.now().timestamp()
            if current_time < float(cache_info["last_update"]):
                is_cached = False
            else:
                diff_time = current_time - float(cache_info["last_update"])
                if expire == "hour":
                    is_cached = diff_time < timedelta(hours=1).total_seconds()
                elif expire == "day":
                    is_cached = diff_time < timedelta(days=1).total_seconds()
                elif expire == "week":
                    is_cached = diff_time < timedelta(weeks=1).total_seconds()
                elif expire == "month":
                    is_cached = diff_time < timedelta(days=30).total_seconds()
    except:
        is_cached = False

    return cache_info is not None, is_cached


def cache_file(
    name: str,
    file_cache: Union[bytes, str, Path],
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
    checksum: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"

    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return False, "Can't get source file"
    source_path = Path(source_file)

    if not job_name:
        job_name = source_path.name.replace(".py", "")

    if isinstance(file_cache, bytes):
        content = file_cache
    else:
        if isinstance(file_cache, str):
            file_cache = Path(file_cache)
        assert isinstance(file_cache, Path)
        content = file_cache.read_bytes()

    cache_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(content)

    if not checksum:
        checksum = bytes_hash(content)

    try:
        sent, err, status, resp = api.request(
            "PUT",
            f"/jobs/{job_name}/cache/{name}?method=core",
            data={"service_id": service_id, "checksum": checksum},
            files={"cache_file": content},
            additonal_headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : {err}"
        elif status == 503:
            retry_after = resp.headers.get("Retry-After", 1)
            retry_after = float(retry_after)
            sleep(retry_after)
            return cache_file(
                name,
                file_cache,
                api,
                api_token,
                job_name=job_name,
                service_id=service_id,
                checksum=checksum,
            )
        elif status not in (200, 201):
            ret = False
            err = f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : status = {status}, resp = {resp}"
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def update_cache_file_info(
    name: str,
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"

    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return False, "Can't get source file"
    source_path = Path(source_file)

    cache_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(cache_path.read_bytes())

    if not job_name:
        job_name = source_path.name.replace(".py", "")

    try:
        sent, err, status, resp = api.request(
            "PUT",
            f"/jobs/{job_name}/cache/{name}?method=core",
            data={"service_id": service_id},
            additonal_headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : {err}"
        elif status == 503:
            retry_after = resp.headers.get("Retry-After", 1)
            retry_after = float(retry_after)
            sleep(retry_after)
            return update_cache_file_info(
                name,
                api,
                api_token,
                job_name=job_name,
                service_id=service_id,
            )
        elif status != 200:
            ret = False
            err = f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : status = {status}, resp = {resp}"
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def del_cache(
    name: str,
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"

    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return False, "Can't get source file"
    source_path = Path(source_file)

    Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name).unlink(missing_ok=True)

    if not job_name:
        job_name = source_path.name.replace(".py", "")

    try:
        sent, err, status, resp = api.request(
            "DELETE",
            f"/jobs/{job_name}/cache/{name}?method=core",
            data={"service_id": service_id},
            additonal_headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name} : {err}"
        elif status == 503:
            retry_after = resp.headers.get("Retry-After", 1)
            retry_after = float(retry_after)
            sleep(retry_after)
            return del_cache(
                name,
                api,
                api_token,
                job_name=job_name,
                service_id=service_id,
            )
        elif status != 200:
            ret = False
            err = f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name} : status = {status}, resp = {resp}"
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def cache_hash(
    name: str,
    api,
    api_token: Optional[str] = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Optional[str]:
    source_file = getsourcefile(_getframe(1))
    if source_file is None:
        return None
    source_path = Path(source_file)

    cache_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name, name)
    if cache_path.is_file():
        return file_hash(cache_path)

    if not job_name:
        job_name = source_path.name.replace(".py", "")

    cache_info = get_cache(
        name,
        api,
        api_token,
        with_info=True,
        with_data=False,
        job_name=job_name,
        service_id=service_id,
    )

    if not cache_info or not isinstance(cache_info, dict):
        return None

    return cache_info["checksum"]
