# -*- coding: utf-8 -*-
from os import sep
from os.path import join
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from uvicorn.workers import UvicornWorker


class BwUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "loop": "auto",
        "http": "auto",
        "proxy_headers": True,
        "server_header": False,
        "date_header": False,
    }
