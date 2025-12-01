from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    Logger,
    StreamHandler,
    _nameToLevel,
    addLevelName,
    basicConfig,
    getLogger,
    setLoggerClass,
)
from logging.handlers import SysLogHandler
from os import getenv, sep
from os.path import join
from re import match
from socket import SOCK_DGRAM, SOCK_STREAM
from typing import Optional, Union

LOG_FORMAT = "%(asctime)s [%(name)s] [%(process)d] [%(levelname)s] - %(message)s"
DATE_FORMAT = "[%Y-%m-%d %H:%M:%S %z]"

# Regex patterns for validation
FILE_PATH_PATTERN = r"^(/[\w\-./]+|[A-Za-z]:\\[\w\-./\\]+)$"
SYSLOG_ADDRESS_PATTERN = r"^((udp|tcp)://)?(/[\w\-./]+|[\w\-.]+(:\d{1,5})?)$"


class BWLogger(Logger):
    """Custom logger class inheriting from the standard Logger."""

    def __init__(self, name, level=INFO):
        super().__init__(name, level)


# Set the custom logger class as the default
setLoggerClass(BWLogger)

# Set the default logging level based on environment variables
default_level = _nameToLevel.get(getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper(), INFO)

env_log_types = getenv("LOG_TYPES", "stderr").split(" ")
log_types = {}
warnings = []

if "file" in env_log_types:
    log_file_path = getenv(
        "LOG_FILE_PATH", join(sep, "var", "log", "bunkerweb", "scheduler.log") if getenv("SCHEDULER_LOG_TO_FILE", "no") == "yes" else ""
    ).strip()
    if match(FILE_PATH_PATTERN, log_file_path):
        log_types["file"] = {
            "handler": FileHandler(log_file_path),
            "file_path": log_file_path,
        }
    else:
        warnings.append(f"The log file path '{log_file_path}' is invalid. Logs will not be written to file.")

if "syslog" in env_log_types:
    syslog_address = getenv("LOG_SYSLOG_ADDRESS", "").strip()
    if match(SYSLOG_ADDRESS_PATTERN, syslog_address):
        # Parse protocol prefix if present
        socktype = None
        address = syslog_address
        if syslog_address.startswith("udp://"):
            socktype = SOCK_DGRAM
            address = syslog_address[6:]  # Remove "udp://"
        elif syslog_address.startswith("tcp://"):
            socktype = SOCK_STREAM
            address = syslog_address[6:]  # Remove "tcp://"

        # Check if it's a network address (host:port) or socket path
        if ":" in address and not address.startswith("/"):
            host, port = address.rsplit(":", 1)
            log_types["syslog"] = {
                "handler": SysLogHandler(address=(host, int(port)), socktype=socktype),
                "address": (host, int(port)),
                "socktype": socktype,
            }
        else:
            # If no port is given and it's a hostname (not a socket path), default to UDP port 514
            if not address.startswith("/"):
                host = address
                default_port = 514
                if socktype is None:
                    socktype = SOCK_DGRAM  # Default to UDP
                log_types["syslog"] = {
                    "handler": SysLogHandler(address=(host, default_port), socktype=socktype),
                    "address": (host, default_port),
                    "socktype": socktype,
                }
            else:
                log_types["syslog"] = {
                    "handler": SysLogHandler(address=address, socktype=socktype),
                    "address": address,
                    "socktype": socktype,
                }

        # Set syslog ident for service differentiation
        syslog_ident = getenv("LOG_SYSLOG_TAG", "app")
        log_types["syslog"]["ident"] = f"{syslog_ident}: "
        log_types["syslog"]["handler"].ident = f"{syslog_ident}: "
    else:
        warnings.append(f"The syslog address '{syslog_address}' is invalid. Logs will not be sent to syslog.")

if not log_types or "stderr" in env_log_types:
    if not log_types and "stderr" not in env_log_types:
        warnings.append("No valid log types configured. Defaulting to stderr.")
    log_types["stderr"] = {"handler": StreamHandler()}

basicConfig(format=LOG_FORMAT, datefmt=DATE_FORMAT, level=default_level, handlers=[handler["handler"] for handler in log_types.values()], force=True)

# Set the default logging level for specific SQLAlchemy components
database_default_level = _nameToLevel.get(getenv("DATABASE_LOG_LEVEL", "WARNING").upper(), WARNING)
sqlalchemy_loggers = (
    "sqlalchemy.orm.mapper.Mapper",
    "sqlalchemy.orm.relationships.RelationshipProperty",
    "sqlalchemy.orm.strategies.LazyLoader",
    "sqlalchemy.pool.impl.QueuePool",
    "sqlalchemy.pool.impl.SingletonThreadPool",
    "sqlalchemy.engine.Engine",
)
for logger_name in sqlalchemy_loggers:
    getLogger(logger_name).setLevel(database_default_level)

# Customize log level names with emojis
addLevelName(CRITICAL, "🚨")
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")


def setup_logger(title: str, level: Optional[Union[str, int]] = None) -> Logger:
    """Set up and return a logger with the specified title and level."""
    title = title.upper()
    logger = getLogger(title)
    level = level or default_level

    if isinstance(level, str):
        level = _nameToLevel.get(level.upper(), default_level)
    logger.setLevel(level)

    return logger


if warnings:
    logger = getLogger("LOGGER_SETUP")
    for warn in warnings:
        logger.warning(warn)
