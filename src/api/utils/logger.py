from contextlib import suppress
from logging import Formatter, getLogger
from os.path import join, sep
from sys import path as sys_path
from threading import Lock

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from gunicorn.glogging import Logger

from logger import DATE_FORMAT, LOG_FORMAT, setup_logger  # type: ignore


class APILogger(Logger):

    error_log = None
    access_log = None

    error_fmt = LOG_FORMAT
    datefmt = DATE_FORMAT

    def __init__(self, cfg):
        if not self.error_log:
            # Use common utils setup to fetch level from CUSTOM_LOG_LEVEL/LOG_LEVEL
            self.error_log = setup_logger("API")  # type: ignore
        self.error_log.propagate = False
        if not self.access_log:
            self.access_log = setup_logger("API.access")  # type: ignore
        self.access_log.propagate = False
        self.error_handlers = []
        self.access_handlers = []
        self.logfile = None
        self.lock = Lock()
        self.cfg = cfg
        self.setup(cfg)

    def setup(self, cfg):  # type: ignore[override]
        # Let Gunicorn configure its handlers first
        super().setup(cfg)

        # Align uvicorn loggers with our format/handlers so all logs are consistent
        with suppress(Exception):
            uvicorn_error = getLogger("uvicorn.error")
            uvicorn_access = getLogger("uvicorn.access")

            def _sync_handlers(target, source):
                # Replace target handlers with ours, enforcing formatter
                target.handlers = []
                for h in source.handlers:
                    if h.formatter is None or getattr(h.formatter, "_fmt", None) != LOG_FORMAT:
                        h.setFormatter(Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))  # type: ignore
                    target.addHandler(h)
                target.setLevel(source.level)
                target.propagate = False

            _sync_handlers(uvicorn_error, self.error_log)
            _sync_handlers(uvicorn_access, self.access_log)

            # Rename loggers by filtering records' name to match API naming
            class _RenameFilter:
                def __init__(self, new_name: str):
                    self._new_name = new_name

                def filter(self, record):  # type: ignore[override]
                    record.name = self._new_name
                    return True

            uvicorn_error.addFilter(_RenameFilter("API"))
            uvicorn_access.addFilter(_RenameFilter("API.access"))

            # Ensure uvicorn logger families use the same level
            for lname, src in (
                ("uvicorn", self.error_log),
                ("uvicorn.server", self.error_log),
            ):
                with suppress(Exception):
                    getLogger(lname).setLevel(src.level)  # type: ignore
