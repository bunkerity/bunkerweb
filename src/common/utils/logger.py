from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Logger,
    _levelToName,
    _nameToLevel,
    addLevelName,
    basicConfig,
    getLogger,
    setLoggerClass,
)
from os import getenv
from threading import Lock


class BWLogger(Logger):
    def __init__(self, name, level=INFO):
        self.name = name
        self.db_lock = Lock()
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
        *,
        store_db: bool = False,
        db=None,
    ):
        if store_db is True and db is not None:
            with self.db_lock:
                ret = db.save_log(msg, level, self.name)

                if ret:
                    self.warning("Failed to save log to database")

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
getLogger("sqlalchemy.engine.Engine").setLevel(
    default_level if default_level != INFO else WARNING
)

# Edit the default levels of the logging module
addLevelName(CRITICAL, "🚨")
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")


def setup_logger(title: str, level=INFO) -> Logger:
    """Set up local logger"""
    title = title.upper()
    logger = getLogger(title)
    logger.setLevel(_nameToLevel.get(level, _levelToName.get(level, INFO)))

    return logger
