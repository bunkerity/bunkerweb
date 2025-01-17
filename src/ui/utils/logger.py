from logging import getLogger
from os.path import join, sep
from sys import path as sys_path
from threading import Lock

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from gunicorn.glogging import Logger

from logger import DATE_FORMAT, LOG_FORMAT  # type: ignore


class UiLogger(Logger):

    error_log = None
    access_log = None

    error_fmt = LOG_FORMAT
    datefmt = DATE_FORMAT

    def __init__(self, cfg):
        if not self.error_log:
            self.error_log = getLogger("UI")
        self.error_log.propagate = False
        if not self.access_log:
            self.access_log = getLogger("UI.access")
        self.access_log.propagate = False
        self.error_handlers = []
        self.access_handlers = []
        self.logfile = None
        self.lock = Lock()
        self.cfg = cfg
        self.setup(cfg)


class TmpUiLogger(UiLogger):
    def __init__(self, cfg):
        self.error_log = getLogger("TMP-UI")
        self.access_log = getLogger("TMP-UI.access")
        super().__init__(cfg)
