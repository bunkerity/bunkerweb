from contextlib import suppress
from datetime import datetime
from hashlib import sha512
from json import dumps, loads
from pathlib import Path
from shutil import copy
from traceback import format_exc


"""
{
    "date": timestamp,
    "checksum": sha512
}
"""


def is_cached_file(file, expire):
    is_cached = False
    try:
        if not Path(f"{file}.md").is_file():
            return False

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


def file_hash(file):
    _sha512 = sha512()
    with open(file, "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            _sha512.update(data)
    return _sha512.hexdigest()


def cache_hash(cache):
    with suppress(BaseException):
        return loads(Path(f"{cache}.md").read_text())["checksum"]
    return None


def cache_file(file, cache, _hash):
    ret, err = True, "success"
    try:
        copy(file, cache)
        Path(file).unlink()
        md = {"date": datetime.timestamp(datetime.now()), "checksum": _hash}
        Path(cache).write_text(dumps(md))
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err
