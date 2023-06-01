#!/usr/bin/python3

from contextlib import suppress
from datetime import datetime
from hashlib import sha512
from inspect import getsourcefile
from io import BufferedReader
from json import dumps, loads
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
    file: Union[str, Path],
    expire: Union[Literal["hour"], Literal["day"], Literal["week"], Literal["month"]],
    db=None,
) -> bool:
    is_cached = False
    cached_file = None
    try:
        file = normpath(file)
        file_path = Path(f"{file}.md")
        if not file_path.is_file():
            if not db:
                return False
            cached_file = db.get_job_cache_file(
                basename(getsourcefile(_getframe(1))).replace(".py", ""),
                basename(file),
                with_info=True,
            )

            if not cached_file:
                return False
            cached_time = cached_file.last_update.timestamp()
        else:
            cached_time = loads(file_path.read_text())["date"]

        current_time = datetime.now().timestamp()
        if current_time < cached_time:
            is_cached = False
        else:
            diff_time = current_time - cached_time
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

    if is_cached and cached_file:
        Path(file).write_bytes(cached_file.data)

    return is_cached and cached_file


def get_file_in_db(file: Union[str, Path], db) -> Optional[bytes]:
    cached_file = db.get_job_cache_file(
        basename(getsourcefile(_getframe(1))).replace(".py", ""), normpath(file)
    )
    if not cached_file:
        return None
    return cached_file.data


def set_file_in_db(
    name: str,
    content: bytes,
    db,
    *,
    job_name: Optional[str] = None,
    service_id: Optional[str] = None,
    checksum: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"
    try:
        with lock:
            err = db.update_job_cache(
                service_id,
                name,
                content,
                job_name=job_name
                or basename(getsourcefile(_getframe(1))).replace(".py", ""),
                checksum=checksum,
            )

            if err:
                ret = False
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err


def del_file_in_db(name: str, db) -> Tuple[bool, str]:
    ret, err = True, "success"
    try:
        db.delete_job_cache(
            name, job_name=basename(getsourcefile(_getframe(1))).replace(".py", "")
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


def bytes_hash(bio: BufferedReader) -> str:
    _sha512 = sha512()
    while True:
        data = bio.read(1024)
        if not data:
            break
        _sha512.update(data)
    bio.seek(0)
    return _sha512.hexdigest()


def cache_hash(cache: Union[str, Path], db=None) -> Optional[str]:
    with suppress(BaseException):
        return loads(Path(normpath(f"{cache}.md")).read_text(encoding="utf-8")).get(
            "checksum", None
        )
    if db:
        cached_file = db.get_job_cache_file(
            basename(getsourcefile(_getframe(1))).replace(".py", ""),
            basename(normpath(cache)),
            with_info=True,
            with_data=False,
        )

        if cached_file:
            return cached_file.checksum
    return None


def cache_file(
    file: Union[str, Path],
    cache: Union[str, Path],
    _hash: Optional[str],
    db=None,
    *,
    delete_file: bool = True,
    service_id: Optional[str] = None,
) -> Tuple[bool, str]:
    ret, err = True, "success"
    try:
        if not isinstance(file, Path):
            file = Path(normpath(file))
        if not isinstance(cache, Path):
            cache = Path(normpath(cache))

        content = file.read_bytes()
        cache.write_bytes(content)

        if delete_file:
            file.unlink()

        if not _hash:
            _hash = file_hash(str(cache))

        if db:
            return set_file_in_db(
                basename(str(cache)),
                content,
                db,
                job_name=basename(getsourcefile(_getframe(1))).replace(".py", ""),
                service_id=service_id,
                checksum=_hash,
            )
        else:
            Path(f"{cache}.md").write_text(
                dumps(dict(date=datetime.now().timestamp(), checksum=_hash)),
                encoding="utf-8",
            )
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err
