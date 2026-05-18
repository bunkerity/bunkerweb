from contextlib import suppress
from logging import getLogger, Formatter
from logging.handlers import SysLogHandler
from os import getenv
from os.path import join, sep
from sys import path as sys_path
from threading import Lock

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from gunicorn.glogging import SYSLOG_FACILITIES, Logger, logging, parse_syslog_address

from logger import DATE_FORMAT, LOG_FORMAT  # type: ignore

# Syslog tag to use for API logs - must match gunicorn.conf.py syslog_prefix
SYSLOG_TAG = getenv("LOG_SYSLOG_TAG", "bw-api")


class APILogger(Logger):

    error_log = None
    access_log = None

    error_fmt = LOG_FORMAT
    syslog_fmt = LOG_FORMAT
    datefmt = DATE_FORMAT

    def __init__(self, cfg):
        if not self.error_log:
            self.error_log = getLogger("API")
        self.error_log.propagate = False
        if not self.access_log:
            self.access_log = getLogger("API.ACCESS")
        self.access_log.propagate = False
        self.error_handlers = []
        self.access_handlers = []
        self.logfile = None
        self.lock = Lock()
        self.cfg = cfg
        self._uvicorn_synced = False  # ensure we don't re-sync multiple times
        self.setup(cfg)

    def _set_syslog_handler(self, log, cfg, fmt, name):
        # setup format
        prefix = cfg.syslog_prefix or cfg.proc_name.replace(":", ".")

        if name == "access":
            prefix = "%s-%s" % (prefix, name)

        # set format
        fmt = logging.Formatter(r"%s: %s" % (prefix, fmt))

        # syslog facility
        try:
            facility = SYSLOG_FACILITIES[cfg.syslog_facility.lower()]
        except KeyError:
            raise RuntimeError("unknown facility name")

        # parse syslog address
        socktype, addr = parse_syslog_address(cfg.syslog_addr)

        # finally setup the syslog handler
        h = logging.handlers.SysLogHandler(address=addr, facility=facility, socktype=socktype)

        h.setFormatter(fmt)
        h._gunicorn = True
        log.addHandler(h)

    def setup(self, cfg):  # type: ignore[override]
        # Let Gunicorn configure its handlers first
        super().setup(cfg)

        if self._uvicorn_synced:
            return

        # Align uvicorn loggers with our format/handlers so all logs are consistent
        with suppress(Exception):
            uvicorn_error = getLogger("uvicorn.error")
            uvicorn_access = getLogger("uvicorn.access")

            def _sync_handlers(target, source, is_access=False):
                # Replace target handlers with ours, enforcing formatter and syslog ident
                target.handlers = []
                for h in source.handlers:
                    if h.formatter is None or getattr(h.formatter, "_fmt", None) != LOG_FORMAT:
                        h.setFormatter(Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))  # type: ignore
                    # Ensure syslog handlers have the correct ident/tag
                    if isinstance(h, SysLogHandler):
                        tag = f"{SYSLOG_TAG}-access" if is_access else SYSLOG_TAG
                        h.ident = f"{tag}: "
                    target.addHandler(h)
                target.setLevel(source.level)
                target.propagate = False

            _sync_handlers(uvicorn_error, self.error_log, is_access=False)
            _sync_handlers(uvicorn_access, self.access_log, is_access=True)

            # Rename loggers by filtering records' name to match API naming
            class _RenameFilter:
                def __init__(self, new_name: str):
                    self._new_name = new_name

                def filter(self, record):  # type: ignore[override]
                    record.name = self._new_name
                    return True

            uvicorn_error.addFilter(_RenameFilter("API"))
            uvicorn_access.addFilter(_RenameFilter("API.ACCESS"))

            self._uvicorn_synced = True
