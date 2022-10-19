import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    level=logging.INFO,
)

# Edit the default levels of the logging module
logging.addLevelName(logging.CRITICAL, "🚨")
logging.addLevelName(logging.DEBUG, "🐛")
logging.addLevelName(logging.ERROR, "❌")
logging.addLevelName(logging.INFO, "ℹ️ ")
logging.addLevelName(logging.WARNING, "⚠️ ")


def setup_logger(title: str, level=logging.INFO) -> logging.Logger:
    """Set up local logger"""
    title = title.upper()
    logger = logging.getLogger(title)

    if level not in (
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ):
        level = logging.INFO

    logger.setLevel(level)

    return logger
