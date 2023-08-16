#!/usr/bin/python3

from datetime import datetime
from hashlib import sha512
from inspect import getsourcefile
from io import BufferedReader, BytesIO
from os.path import basename, normpath
from pathlib import Path
from sys import _getframe
from threading import Lock
from traceback import format_exc
from typing import Literal, Optional, Tuple, Union

lock = Lock()

"""
{
    "date": timestamp,
    "checksum": sha512
}
"""


def is_cached_file(
    name: str,
    expire: Union[Literal["hour"], Literal["day"], Literal["week"], Literal["month"]],
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, bool]:
    cache_info = None
    is_cached = False
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    try:
        cache_info = get_cache(
            name,
            api,
            api_token,
            with_info=True,
            with_data=False,
            job_name=job_name,
            service_id=service_id,
        )

        if cache_info:
            current_time = datetime.now().timestamp()
            if current_time < float(cache_info["date"]):
                is_cached = False
            else:
                diff_time = current_time - float(cache_info["date"])
                if expire == "hour":
                    is_cached = diff_time < 3600
                elif expire == "day":
                    is_cached = diff_time < 86400
                elif expire == "week":
                    is_cached = diff_time < 604800
                elif expire == "month":
                    is_cached = diff_time < 2592000
    except:
        is_cached = False

    return cache_info is not None, is_cached


def get_cache(
    name: str,
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
    with_info: bool = False,
    with_data: bool = True,
) -> Optional[dict]:
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    sent, _, status, resp = api.request(
        "GET",
        f"/jobs/{job_name}/cache/{name}",
        data={"service_id": service_id, "with_info": with_info, "with_data": with_data},
        additonal_headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
    )

    if not sent or status != 200:
        return None

    return resp


def cache_file(
    name: str,
    cache_file: Union[bytes, str, Path],
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
    checksum: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    if isinstance(cache_file, bytes):
        content = cache_file
    else:
        if isinstance(cache_file, str):
            cache_file = Path(cache_file)
        content = cache_file.read_bytes()

    try:
        sent, err, status, resp = api.request(
            "PUT",
            f"/jobs/{job_name}/cache/{name}",
            data={"service_id": service_id, "checksum": checksum},
            files={"cache_file": content},
            additonal_headers={"Authorization": f"Bearer {api_token}"}
            if api_token
            else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : {err}"
        elif status not in (200, 201):
            ret = False
            err = (
                f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : status = {status}, resp = {resp}",
            )
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def update_cache_file_info(
    name: str,
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    try:
        sent, err, status, resp = api.request(
            "PUT",
            f"/jobs/{job_name}/cache/{name}",
            data={"service_id": service_id},
            additonal_headers={"Authorization": f"Bearer {api_token}"}
            if api_token
            else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : {err}"
        elif status != 200:
            ret = False
            err = (
                f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name}/ : status = {status}, resp = {resp}",
            )
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def del_cache(
    name: str,
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    try:
        sent, err, status, resp = api.request(
            "DELETE",
            f"/jobs/{job_name}/cache/{name}",
            data={"service_id": service_id},
            additonal_headers={"Authorization": f"Bearer {api_token}"}
            if api_token
            else {},
        )

        if not sent:
            ret = False
            err = f"Can't send API request to {api.endpoint}jobs/cache/{job_name}/{name} : {err}"
        elif status != 200:
            ret = False
            err = (
                f"Error while sending API request to {api.endpoint}jobs/cache/{job_name}/{name} : status = {status}, resp = {resp}",
            )
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def file_hash(file: Union[str, Path]) -> str:
    _sha512 = sha512()
    with open(normpath(file), "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _sha512.update(data)
    return _sha512.hexdigest()


def bytes_hash(bio: Union[bytes, BufferedReader]) -> str:
    if isinstance(bio, bytes):
        bio = BytesIO(bio)
        bio.seek(0, 0)

    _sha512 = sha512()
    while True:
        data = bio.read(1024)
        if not data:
            break
        _sha512.update(data)
    bio.seek(0)
    return _sha512.hexdigest()


def cache_hash(
    name: str,
    api,
    api_token: str = None,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
) -> Optional[str]:
    job_name = job_name or basename(getsourcefile(_getframe(1))).replace(".py", "")

    cache_info = get_cache(
        name,
        api,
        api_token,
        with_info=True,
        with_data=False,
        job_name=job_name,
        service_id=service_id,
    )

    if not cache_info:
        return None

    return cache_info["checksum"]
