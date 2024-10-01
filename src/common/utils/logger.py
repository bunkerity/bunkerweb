from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, _nameToLevel, addLevelName, basicConfig, getLogger, setLoggerClass
from os import getenv
from typing import Optional, Union


class BWLogger(Logger):
    """Custom logger class inheriting from the standard Logger."""

    def __init__(self, name, level=INFO):
        super().__init__(name, level)


# Set the custom logger class as the default
setLoggerClass(BWLogger)

# Set the default logging level based on environment variables
default_level = _nameToLevel.get(getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")).upper(), INFO)

basicConfig(
    format="%(asctime)s [%(name)s] [%(process)d] [%(levelname)s] - %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S %z]",
    level=default_level,
)

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

    if getenv("SCHEDULER_LOG_TO_FILE", "no") == "yes":
        file_handler = FileHandler("/var/log/bunkerweb/scheduler.log")
        file_handler.setFormatter(Formatter("%(asctime)s [%(name)s] [%(process)d] [%(levelname)s] - %(message)s"))
        logger.addHandler(file_handler)

    return logger
