# -*- coding: utf-8 -*-
from functools import cached_property
from os import getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import path as sys_path
from typing import Literal, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore


class AutoconfConfig(YamlBaseSettings):
    CORE_ADDR: str = "http://127.0.0.1:1337"
    CORE_TOKEN: str = ""
    WAIT_RETRY_INTERVAL: Union[str, int] = 5
    DOCKER_HOST: str = "unix:///var/run/docker.sock"
    LOG_LEVEL: Literal["error", "warn", "info", "debug", "ERROR", "WARN", "INFO", "DEBUG"] = "info"

    KUBERNETES_MODE: Union[Literal["y", "yes", "n", "no"], bool] = "no"
    SWARM_MODE: Union[Literal["y", "yes", "n", "no"], bool] = "no"

    # The reading order is:
    # 1. Environment variables
    # 2. Secrets files
    # 3. YAML file
    # 4. .env file
    # 5. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=normpath(getenv("SETTINGS_YAML_FILE", join(sep, "etc", "bunkerweb", "config.yaml") if Path(sep, "etc", "bunkerweb", "config.yaml").is_file() else join(sep, "etc", "bunkerweb", "config.yml"))),
        env_file=normpath(getenv("SETTINGS_ENV_FILE", join(sep, "etc", "bunkerweb", "autoconf.conf"))),
        secrets_dir=normpath(getenv("SETTINGS_SECRETS_DIR", join(sep, "run", "secrets"))),
        env_file_encoding="utf-8",
        extra="allow",
    )

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.upper() if self.LOG_LEVEL in ("error", "info", "debug") else "WARNING"

    @cached_property
    def kubernetes_mode(self) -> bool:
        return self.KUBERNETES_MODE.lower().startswith("y") if isinstance(self.KUBERNETES_MODE, str) else self.KUBERNETES_MODE

    @cached_property
    def swarm_mode(self) -> bool:
        return self.SWARM_MODE.lower().startswith("y") if isinstance(self.SWARM_MODE, str) else self.SWARM_MODE
