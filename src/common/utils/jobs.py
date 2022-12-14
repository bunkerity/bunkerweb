from contextlib import suppress
from datetime import datetime
from hashlib import sha512
from json import dumps, loads
from os import path, remove
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
        if not path.isfile(file):
            return False
        if not path.isfile(f"{file}.md"):
            return False
        with open(f"{file}.md", "r") as f:
            cached_time = loads(f.read())["date"]
        current_time = datetime.timestamp(datetime.now())
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
        with open(f"{cache}.md", "r") as f:
            return loads(f.read())["checksum"]
    return None


def cache_file(file, cache, _hash):
    ret, err = True, "success"
    try:
        copy(file, cache)
        remove(file)
        with open(f"{cache}.md", "w") as f:
            md = {"date": datetime.timestamp(datetime.now()), "checksum": _hash}
            f.write(dumps(md))
    except:
        return False, f"exception :\n{format_exc()}"
    return ret, err
