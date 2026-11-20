"""Plain helpers for the autoconf tests (never imported from conftest.py: see tests/unit/gen/conftest.py)."""

import logging
from types import SimpleNamespace


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def messages(self, level=None):
        return [r.getMessage() for r in self.records if level is None or r.levelno == level]

    def has(self, text, level=None):
        return any(text in message for message in self.messages(level))


_ATTACHED = []


def attach_log(controller):
    """Capture everything the controller logs; reset_logs() (autouse in conftest) undoes it after the test."""
    capture = LogCapture()
    logger = controller._logger
    _ATTACHED.append((logger, capture, logger.level))
    logger.addHandler(capture)
    logger.setLevel(logging.DEBUG)
    return capture


def reset_logs():
    while _ATTACHED:
        logger, capture, level = _ATTACHED.pop()
        logger.removeHandler(capture)
        logger.setLevel(level)


def ns(**kwargs):
    return SimpleNamespace(**kwargs)
