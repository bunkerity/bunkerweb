#!/usr/bin/python3

from os import getegid, geteuid, stat
from stat import (
    S_IRGRP,
    S_IROTH,
    S_IRUSR,
    S_IWGRP,
    S_IWOTH,
    S_IWUSR,
    S_IXGRP,
    S_IXOTH,
    S_IXUSR,
)
from typing import List


def has_permissions(path: str, need_permissions: List[str]) -> bool:
    uid = geteuid()
    gid = getegid()
    statinfo = stat(path)
    permissions = {"R": False, "W": False, "X": False}
    if statinfo.st_uid == uid:
        if statinfo.st_mode & S_IRUSR:
            permissions["R"] = True
        if statinfo.st_mode & S_IWUSR:
            permissions["W"] = True
        if statinfo.st_mode & S_IXUSR:
            permissions["X"] = True
    if statinfo.st_uid == gid:
        if statinfo.st_mode & S_IRGRP:
            permissions["R"] = True
        if statinfo.st_mode & S_IWGRP:
            permissions["W"] = True
        if statinfo.st_mode & S_IXGRP:
            permissions["X"] = True
    if statinfo.st_mode & S_IROTH:
        permissions["R"] = True
    if statinfo.st_mode & S_IWOTH:
        permissions["W"] = True
    if statinfo.st_mode & S_IXOTH:
        permissions["X"] = True
    for need_permission in need_permissions:
        if not permissions[need_permission]:
            return False
    return True
