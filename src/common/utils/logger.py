from logging import (
    CRITICAL, DEBUG, ERROR, INFO, WARNING,
    FileHandler, Formatter, Logger, StreamHandler,
    addLevelName, getLogger, setLoggerClass
)
from os import getenv
from typing import Dict, Optional, Set, Tuple, Union
import threading
import sys

# Constants for log formatting
LOG_FORMAT: str = (
    "%(asctime)s [%(name)s] [%(process)d] "
    "[%(levelname)s] - %(message)s"
)
DATE_FORMAT: str = "[%Y-%m-%d %H:%M:%S %z]"

# Mapping of string level names to numeric values
# This replaces the private _nameToLevel from logging module
LEVEL_MAP: Dict[str, int] = {
    "CRITICAL": CRITICAL,  # 50
    "FATAL": CRITICAL,     # 50 (alias)
    "ERROR": ERROR,        # 40
    "WARN": WARNING,       # 30 (alias)
    "WARNING": WARNING,    # 30
    "INFO": INFO,          # 20
    "DEBUG": DEBUG,        # 10
    "NOTSET": 0           # 0
}

# Thread safety primitives
_logger_lock: threading.Lock = threading.Lock()
_initialized: bool = False
_configured_loggers: Set[str] = set()


class BWLogger(Logger):
    # Custom logger class inheriting from the standard Logger

    def __init__(self, name: str, level: int = INFO) -> None:
        super().__init__(name, level)


# Initialize logging configuration for the entire application
def _initialize_logging() -> None:
    # Initialize logging configuration (thread-safe, runs once)
    global _initialized

    # Use lock to ensure thread-safe initialization
    with _logger_lock:
        # Check if already initialized to avoid duplicate setup
        if _initialized:
            return

        # Set our custom logger class as the default for all new loggers
        setLoggerClass(BWLogger)

        # Configure the root logger with basic settings
        root_logger = getLogger()

        # Only add handler if root logger doesn't have any
        if not root_logger.handlers:
            # Create console handler that outputs to stderr
            handler = StreamHandler(sys.stderr)

            # Apply our custom format to the handler
            handler.setFormatter(
                Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
            )

            # Add handler to root logger
            root_logger.addHandler(handler)

            # Set default log level from environment
            root_logger.setLevel(_get_default_level())

        # Customize log level names with emojis for better visibility
        level_emojis: Dict[int, str] = {
            CRITICAL: "🚨",  # Critical/Fatal errors
            DEBUG: "🐛",     # Debug messages
            ERROR: "❌",     # Error messages
            INFO: "ℹ️ ",     # Informational messages
            WARNING: "⚠️ "   # Warning messages
        }

        # Register each emoji with its corresponding level
        for level, emoji in level_emojis.items():
            addLevelName(level, emoji)

        # Apply special configuration for SQLAlchemy loggers
        _configure_sqlalchemy_loggers()

        # Mark as initialized
        _initialized = True


# Get the default logging level from environment variables
def _get_default_level() -> int:
    # Get the default logging level from environment variables
    # Check CUSTOM_LOG_LEVEL first, then LOG_LEVEL, default to INFO
    level_str: str = getenv(
        "CUSTOM_LOG_LEVEL",
        getenv("LOG_LEVEL", "INFO")
    ).upper()

    # Convert string level to numeric value, default to INFO if unknown
    return LEVEL_MAP.get(level_str, INFO)


# Get the database-specific logging level
def _get_database_level() -> int:
    # Get the database logging level from environment variables
    # DATABASE_LOG_LEVEL defaults to WARNING to reduce noise
    level_str: str = getenv("DATABASE_LOG_LEVEL", "WARNING").upper()

    # Convert to numeric, default to WARNING if unknown
    return LEVEL_MAP.get(level_str, WARNING)


# Configure logging for SQLAlchemy components
def _configure_sqlalchemy_loggers() -> None:
    # Configure SQLAlchemy-specific loggers
    # Get the database log level
    database_level: int = _get_database_level()

    # List of SQLAlchemy logger names to configure
    # These are particularly verbose and need special handling
    sqlalchemy_loggers: Tuple[str, ...] = (
        "sqlalchemy.orm.mapper.Mapper",
        "sqlalchemy.orm.relationships.RelationshipProperty",
        "sqlalchemy.orm.strategies.LazyLoader",
        "sqlalchemy.pool.impl.QueuePool",
        "sqlalchemy.pool.impl.SingletonThreadPool",
        "sqlalchemy.engine.Engine",
    )

    # Apply database log level to each SQLAlchemy logger
    for logger_name in sqlalchemy_loggers:
        logger = getLogger(logger_name)
        logger.setLevel(database_level)


# Main function to create and configure loggers
def setup_logger(
    title: str,
    level: Optional[Union[str, int]] = None
) -> Logger:
    # Set up and return a logger with the specified title and level
    # Ensure global logging is initialized first
    _initialize_logging()

    # Convert title to uppercase for consistency
    title = title.upper()

    # Thread-safe logger configuration
    with _logger_lock:
        # Get existing logger or create new one
        logger: Logger = getLogger(title)

        # Skip configuration if already done for this logger
        if title in _configured_loggers:
            return logger

        # Determine the numeric log level
        if level is None:
            # Use default from environment
            numeric_level: int = _get_default_level()
        elif isinstance(level, str):
            # Convert string level to numeric
            numeric_level = LEVEL_MAP.get(
                level.upper(),
                _get_default_level()
            )
        else:
            # Already numeric
            numeric_level = level

        # Apply the log level to the logger
        logger.setLevel(numeric_level)

        # Check if file logging is enabled via environment variable
        if getenv("SCHEDULER_LOG_TO_FILE", "no").lower() == "yes":
            # Check if logger already has a file handler
            has_file_handler: bool = any(
                isinstance(handler, FileHandler)
                for handler in logger.handlers
            )

            # Only add file handler if not already present
            if not has_file_handler:
                try:
                    # Create file handler for scheduler logs
                    log_file = "/var/log/bunkerweb/scheduler.log"
                    file_handler = FileHandler(log_file)

                    # Apply same formatting as console handler
                    file_handler.setFormatter(
                        Formatter(
                            fmt=LOG_FORMAT,
                            datefmt=DATE_FORMAT
                        )
                    )

                    # Set same level as logger
                    file_handler.setLevel(numeric_level)

                    # Add handler to logger
                    logger.addHandler(file_handler)
                except (IOError, OSError) as e:
                    # If file creation fails, log error to stderr
                    err_msg = f"Failed to create file handler: {e}\n"
                    sys.stderr.write(err_msg)

        # Disable propagation to prevent duplicate logs
        # This ensures logs don't bubble up to parent loggers
        logger.propagate = False

        # Mark this logger as configured to avoid re-configuration
        _configured_loggers.add(title)

    return logger


# Initialize logging when module is imported
# This ensures logging is ready before any logger is created
_initialize_logging()
