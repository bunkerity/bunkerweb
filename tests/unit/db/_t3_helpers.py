"""Helpers for the T3 regression tests: a recording logger and a Database built on a stubbed engine."""

import logging
from unittest.mock import MagicMock, patch

import Database as database_module  # type: ignore
from Database import Database  # type: ignore


class RecordingHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())

    @property
    def text(self):
        return "\n".join(self.messages)


def recording_logger(name="bw-t3-recorder"):
    logger = logging.getLogger(name)
    logger.handlers[:] = []
    handler = RecordingHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger, handler


def build_database(uri, *, engine=None, **kwargs):
    """Construct a ``Database`` for ``uri`` without opening a real connection.

    ``create_engine`` is replaced: its call (uri, kwargs) is returned next to the instance so a test can
    read what the constructor handed to SQLAlchemy. ``engine`` is what ``create_engine`` returns.
    """
    logger, handler = recording_logger()
    engine = engine or MagicMock()
    with patch.object(database_module, "create_engine", return_value=engine) as create_engine:
        db = Database(logger, sqlalchemy_string=uri, exit_on_error=False, **kwargs)
    return db, handler, create_engine
