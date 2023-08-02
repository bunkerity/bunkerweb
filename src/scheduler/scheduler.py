from functools import cached_property
from os import sep
from os.path import join
from sys import path as sys_path

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)


class SchedulerConfig(YamlBaseSettings):
    API_ADDR: str = ""
    API_TOKEN: str = ""
    MQ_URI: str = "filesystem:////var/lib/bunkerweb/mq"
    LOG_LEVEL: str = "info"
    WAIT_RETRY_INTERVAL: str = "5"

    # The reading order is:
    # 1. Environment variables
    # 2. YAML file
    # 3. .env file
    # 4. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=join(sep, "etc", "bunkerweb", "config.yaml"),
        env_file=join(sep, "etc", "bunkerweb", "scheduler.conf"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.upper()
