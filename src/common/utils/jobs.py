from contextlib import suppress
from datetime import datetime
from hashlib import sha512
from inspect import getsourcefile
from json import dumps, loads
from pathlib import Path
from sys import _getframe
from threading import Lock
from traceback import format_exc
from typing import Optional, Tuple

lock = Lock()

"""
{
    "date": timestamp,
    "checksum": sha512
}
"""


def is_cached_file(file: str, expire: str, db=None) -> bool:
    is_cached = False
    try:
        if not Path(f"{file}.md").is_file():
            if not db:
                return False
            cached_file = db.get_job_cache_file(
                getsourcefile(_getframe(1)).replace(".py", "").split("/")[-1],
                file.split("/")[-1],
                with_data=False,
            )

            if not cached_file:
                return False
            cached_time = cached_file.last_update
        else:
            cached_time = loads(Path(f"{file}.md").read_text())["date"]

        current_time = datetime.now().timestamp()
        if current_time < cached_time:
            return False
        diff_time = current_time - cached_time
        if expire == "hour":
            is_cached = diff_time < 3600
        elif expire == "day":
            is_cached = diff_time < 86400
        elif expire == "month":
            is_cached = diff_time < 2592000
    except:
        is_cached = False
    return is_cached


def file_hash(file: str) -> str:
    _sha512 = sha512()
    with open(file, "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _sha512.update(data)
    return _sha512.hexdigest()


def cache_hash(cache: str, db=None) -> Optional[str]:
    with suppress(BaseException):
        return loads(Path(f"{cache}.md").read_text()).get("checksum", None)
    if db:
        cached_file = db.get_job_cache_file(
            getsourcefile(_getframe(1)).replace(".py", "").split("/")[-1],
            cache.split("/")[-1],
            with_data=False,
        )

        if cached_file:
            return cached_file.checksum
    return None


def cache_file(
    file: str, cache: str, _hash: str, db=None, *, service_id: Optional[str] = None
) -> Tuple[bool, str]:
    ret, err = True, "success"
    try:
        content = Path(file).read_bytes()
        Path(cache).write_bytes(content)
        Path(file).unlink()
        md = {"date": datetime.now().timestamp(), "checksum": _hash}
        Path(f"{cache}.md").write_text(dumps(md))

        if db:
            with lock:
                err = db.update_job_cache(
                    getsourcefile(_getframe(1)).replace(".py", "").split("/")[-1],
                    service_id,
                    cache.split("/")[-1],
                    content,
                    checksum=_hash,
                )

                if err:
                    ret = False
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err
