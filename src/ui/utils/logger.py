from os.path import join, sep
from sys import path as sys_path
from threading import Lock

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import DATE_FORMAT, LOG_FORMAT, getLogger  # type: ignore

from gunicorn.glogging import SYSLOG_FACILITIES, Logger, logging, parse_syslog_address


class UiLogger(Logger):

    error_log = None
    access_log = None

    error_fmt = LOG_FORMAT
    syslog_fmt = LOG_FORMAT
    datefmt = DATE_FORMAT

    def __init__(self, cfg):
        if not self.error_log:
            self.error_log = getLogger("UI")
        self.error_log.propagate = False
        if not self.access_log:
            self.access_log = getLogger("UI.ACCESS")
        self.access_log.propagate = False
        self.error_handlers = []
        self.access_handlers = []
        self.logfile = None
        self.lock = Lock()
        self.cfg = cfg
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


class TmpUiLogger(UiLogger):
    def __init__(self, cfg):
        self.error_log = getLogger("TMP-UI")
        self.access_log = getLogger("TMP-UI.ACCESS")
        super().__init__(cfg)
