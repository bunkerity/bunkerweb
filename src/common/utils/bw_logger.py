import os
import sys
import threading
from logging import (
    CRITICAL, DEBUG, ERROR, INFO, WARNING,
    FileHandler, Formatter, Logger, StreamHandler,
    addLevelName, getLogger, setLoggerClass
)
from os import getenv
from typing import Any, Dict, Optional, Set, Tuple, Union, cast


# --- Cross-Platform and Performance Utilities ---

def _get_username() -> str:
    # Provides a cross-platform way to get the current user's name.
    try:
        # Unix-like systems (Linux, macOS)
        import pwd
        return pwd.getpwuid(os.geteuid()).pw_name
    except (ImportError, KeyError):
        # environments where the UID is not in the password database
        return getenv('USERNAME') or 'unknown_user'


# --- Custom Log Level: EXCEPTION ---
# EXCEPTION is a custom log level (45), between ERROR (40) and
# CRITICAL (50). It gives special visibility to handled exceptions. To use
# it, call logger.exception() from within an 'except' block.
EXCEPTION_LEVEL = 45

# --- Constants for log formatting ---
LOG_FORMAT: str = (
    "%(asctime)s [%(name)s] [%(process)d] "
    "[%(levelname)s] - %(message)s"
)
DATE_FORMAT: str = "[%Y-%m-%d %H:%M:%S %z]"

# --- Mapping of string level names to numeric values ---
LEVEL_MAP: Dict[str, int] = {
    "CRITICAL": CRITICAL,
    "FATAL": CRITICAL,
    "EXCEPTION": EXCEPTION_LEVEL,
    "ERROR": ERROR,
    "WARN": WARNING,
    "WARNING": WARNING,
    "INFO": INFO,
    "DEBUG": DEBUG,
    "NOTSET": 0
}

# --- Thread safety and configuration tracking ---
_logger_lock: threading.Lock = threading.Lock()
_initialized: bool = False
_configured_loggers: Set[str] = set()


# Custom logger class inheriting from the standard Logger.
class BWLog(Logger):
    def __init__(self, name: str, level: int = INFO) -> None:
        super().__init__(name, level)

    # Overrides the default exception method. We ignore the 'override'
    # type error because we are intentionally simplifying the signature
    # for our specific use case.
    def exception(  # type: ignore[override]
        self, msg: str, *args: Any, **kwargs: Any
    ) -> None:
        kwargs['exc_info'] = True
        if self.isEnabledFor(EXCEPTION_LEVEL):
            self._log(EXCEPTION_LEVEL, msg, args, **kwargs)


# Initializes logging configuration for the entire application.
def _initialize_logging() -> None:
    global _initialized
    with _logger_lock:
        if _initialized:
            return

        setLoggerClass(BWLog)
        addLevelName(EXCEPTION_LEVEL, "EXCEPTION")

        # Configure a handler for the root logger.
        # This ensures that any library logs (like SQLAlchemy) that propagate
        # to the root will be displayed on the console.
        root_logger = getLogger()
        if not root_logger.handlers:
            root_handler = StreamHandler(sys.stderr)
            formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
            root_handler.setFormatter(formatter)
            root_logger.addHandler(root_handler)
            root_logger.setLevel(_get_default_level())

        level_emojis: Dict[int, str] = {
            CRITICAL: "🚨",
            EXCEPTION_LEVEL: "⚡",
            ERROR: "❌",
            INFO: "ℹ️ ",
            WARNING: "⚠️ ",
            DEBUG: "🐛"
        }
        for level, emoji in level_emojis.items():
            addLevelName(level, emoji)

        _configure_sqlalchemy_loggers()
        _initialized = True


# Gets the default logging level from environment variables.
def _get_default_level() -> int:
    level_str = getenv("CUSTOM_LOG_LEVEL") or getenv("LOG_LEVEL") or "INFO"
    return LEVEL_MAP.get(level_str.upper(), INFO)


# Gets the database-specific logging level from environment variables.
def _get_database_level() -> int:
    level_str = getenv("DATABASE_LOG_LEVEL", "WARNING").upper()
    return LEVEL_MAP.get(level_str, WARNING)


# Sets the log level for verbose SQLAlchemy loggers.
def _configure_sqlalchemy_loggers() -> None:
    database_level: int = _get_database_level()
    sqlalchemy_loggers: Tuple[str, ...] = (
        "sqlalchemy.orm.mapper.Mapper",
        "sqlalchemy.orm.relationships.RelationshipProperty",
        "sqlalchemy.orm.strategies.LazyLoader",
        "sqlalchemy.pool.impl.QueuePool",
        "sqlalchemy.pool.impl.SingletonThreadPool",
        "sqlalchemy.engine.Engine",
    )
    for logger_name in sqlalchemy_loggers:
        getLogger(logger_name).setLevel(database_level)


# Main function to get a configured logger instance.
def setup_logger(
    title: str,
    level: Optional[Union[str, int]] = None,
    log_file_path: Optional[str] = None
) -> BWLog:
    _initialize_logging()

    # Use the title directly as the logger name, preserving case.
    logger_name = title

    with _logger_lock:
        if len(_configured_loggers) > 1000:
            _configured_loggers.clear()

        logger = cast(BWLog, getLogger(logger_name))
        if logger_name in _configured_loggers:
            return logger

        if level is None:
            numeric_level = _get_default_level()
        elif isinstance(level, str):
            numeric_level = LEVEL_MAP.get(level.upper(), _get_default_level())
        else:
            numeric_level = level

        logger.setLevel(numeric_level)
        # Isolate this logger to prevent messages from being passed to parent
        # loggers. This is the most robust way to prevent duplicate logs,
        # as this logger has its own dedicated console handler.
        logger.propagate = False

        if not any(isinstance(h, StreamHandler) for h in logger.handlers):
            console_handler = StreamHandler(sys.stderr)
            formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(numeric_level)
            logger.addHandler(console_handler)

        if log_file_path:
            abs_log_path = os.path.abspath(log_file_path)
            if not any(isinstance(h, FileHandler) and
                       os.path.abspath(h.baseFilename) == abs_log_path
                       for h in logger.handlers):
                try:
                    parent_dir = os.path.dirname(abs_log_path)
                    os.makedirs(parent_dir, exist_ok=True)

                    file_handler = FileHandler(abs_log_path)
                    formatter = Formatter(
                        fmt=LOG_FORMAT, datefmt=DATE_FORMAT
                    )
                    file_handler.setFormatter(formatter)
                    file_handler.setLevel(numeric_level)
                    logger.addHandler(file_handler)
                except OSError as e:
                    user_name = _get_username()
                    err_msg = (
                        f"[LOGGER SETUP ERROR] Failed to create log "
                        f"directory/file for path: {abs_log_path}\n"
                        f"User '{user_name}' may not have permissions. "
                        f"Error: {e}\n"
                    )
                    sys.stderr.write(err_msg)

        _configured_loggers.add(logger_name)
        return logger


# --- Run the global initialization when this module is first imported ---
_initialize_logging()
