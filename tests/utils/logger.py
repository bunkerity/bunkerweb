from logging import DEBUG, ERROR, INFO, WARNING, _nameToLevel, addLevelName, basicConfig, getLogger
from os import getenv

basicConfig(
    format="%(asctime)s [%(name)s] [%(levelname)s] - %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S %z]",
    level=DEBUG if getenv("DEBUG", False) else INFO,
)

kubernetes_default_level = _nameToLevel.get(getenv("KUBERNETES_LOG_LEVEL", "WARNING").upper(), WARNING)
getLogger("kubernetes.client.rest").setLevel(kubernetes_default_level)

# Edit the default levels of the logging module
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")
