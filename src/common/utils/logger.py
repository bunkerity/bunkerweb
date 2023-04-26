from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Logger,
    _nameToLevel,
    addLevelName,
    basicConfig,
    getLogger,
    setLoggerClass,
)
from os import getenv
from typing import Optional, Union


class BWLogger(Logger):
    def __init__(self, name, level=INFO):
        self.name = name
        return super(BWLogger, self).__init__(name, level)

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ):
        return super(BWLogger, self)._log(
            level, msg, args, exc_info, extra, stack_info, stacklevel
        )


setLoggerClass(BWLogger)

default_level = _nameToLevel.get(getenv("LOG_LEVEL", "INFO").upper(), INFO)
basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    level=default_level,
)

getLogger("sqlalchemy.orm.mapper.Mapper").setLevel(
    default_level if default_level != INFO else WARNING
)
getLogger("sqlalchemy.orm.relationships.RelationshipProperty").setLevel(
    default_level if default_level != INFO else WARNING
)
getLogger("sqlalchemy.orm.strategies.LazyLoader").setLevel(
    default_level if default_level != INFO else WARNING
)
getLogger("sqlalchemy.pool.impl.QueuePool").setLevel(
    default_level if default_level != INFO else WARNING
)
getLogger("sqlalchemy.pool.impl.NullPool").setLevel(
    default_level if default_level != INFO else WARNING
)
getLogger("sqlalchemy.engine.Engine").setLevel(
    default_level if default_level != INFO else WARNING
)

# Edit the default levels of the logging module
addLevelName(CRITICAL, "🚨")
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")


def setup_logger(title: str, level: Optional[Union[str, int]] = None) -> Logger:
    """Set up local logger"""
    title = title.upper()
    logger = getLogger(title)
    level = level or default_level

    if isinstance(level, str):
        logger.setLevel(_nameToLevel.get(level.upper(), default_level))
    else:
        logger.setLevel(level)

    return logger
