from datetime import datetime, timezone
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Formatter,
    Logger,
    _nameToLevel,
    addLevelName,
    getLogger,
    setLoggerClass,
    StreamHandler,
)
from os import getenv
from typing import Optional, Union

from common_utils import get_timezone


class BwFormatter(Formatter):
    """Overrides logging.Formatter to use an aware datetime object."""

    def converter(self, timestamp):
        """Convert timestamp to an aware datetime object in the desired timezone."""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(get_timezone())

    def formatTime(self, record, datefmt=None):
        """Format the datetime according to the specified format or ISO 8601."""
        dt = self.converter(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        try:
            return dt.isoformat(timespec="milliseconds")
        except TypeError:
            return dt.isoformat()


class BWLogger(Logger):
    """Custom logger class inheriting from the standard Logger."""

    def __init__(self, name, level=INFO):
        super().__init__(name, level)


# Set the custom logger class as the default
setLoggerClass(BWLogger)

# Set the default logging level based on environment variables
default_level = _nameToLevel.get(getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper(), INFO)

# Create a custom formatter instance
formatter = BwFormatter(fmt="%(asctime)s [%(name)s] [%(process)d] [%(levelname)s] - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S %z]")

# Create a console handler and set the custom formatter
handler = StreamHandler()
handler.setFormatter(formatter)

# Get the root logger and add the handler to it
root_logger = getLogger()
root_logger.setLevel(default_level)
root_logger.addHandler(handler)

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
