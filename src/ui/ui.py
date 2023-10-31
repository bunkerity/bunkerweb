# -*- coding: utf-8 -*-
from functools import cached_property
from os import cpu_count, getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import path as sys_path
from typing import Literal, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)


class UiConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: Union[str, int] = 7000
    CORE_ADDR: str = "http://127.0.0.1:1337"
    CORE_TOKEN: str = ""
    MAX_WORKERS: Union[str, int] = max((cpu_count() or 1) - 1, 1)
    MAX_THREADS: Union[str, int] = int(MAX_WORKERS) * 2 if isinstance(MAX_WORKERS, int) or MAX_WORKERS.isdigit() else 2
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme"
    WAIT_RETRY_INTERVAL: Union[str, int] = 5
    MAX_WAIT_RETRIES: Union[str, int] = 10
    LOG_LEVEL: Literal["debug", "info", "warning", "error", "critical", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "info"
    REVERSE_PROXY_IPS: Union[str, set] = {
        "192.168.0.0/16",
        "172.16.0.0/12",
        "10.0.0.0/8",
        "127.0.0.0/8",
    }

    # The reading order is:
    # 1. Environment variables
    # 2. Secrets files
    # 3. YAML file
    # 4. .env file
    # 5. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=normpath(getenv("SETTINGS_YAML_FILE", join(sep, "etc", "bunkerweb", "config.yml") if Path(sep, "etc", "bunkerweb", "config.yml").is_file() else join(sep, "etc", "bunkerweb", "config.yaml"))),
        env_file=normpath(getenv("SETTINGS_ENV_FILE", join(sep, "etc", "bunkerweb", "ui.conf"))),
        secrets_dir=normpath(getenv("SETTINGS_SECRETS_DIR", join(sep, "run", "secrets"))),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.lower()

    @cached_property
    def reverse_proxy_ips(self) -> str:
        if isinstance(self.REVERSE_PROXY_IPS, set):
            return " ".join(self.REVERSE_PROXY_IPS)
        return self.REVERSE_PROXY_IPS

    @property
    def core_token(self) -> str:
        if not self.CORE_TOKEN:
            core_token_path = Path(sep, "var", "cache", "bunkerweb", "core_token")
            if core_token_path.is_file():
                self.CORE_TOKEN = core_token_path.read_text(encoding="utf-8").strip()

        return self.CORE_TOKEN


if __name__ == "__main__":
    from os import _exit, environ
    from regex import match as regex_match

    UI_CONFIG = UiConfig("ui", **environ)

    if not regex_match(
        r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]).{8,}$",
        UI_CONFIG.ADMIN_PASSWORD,
    ):
        _exit(2)
    elif not isinstance(UI_CONFIG.LISTEN_PORT, int) and (not UI_CONFIG.LISTEN_PORT.isdigit() or not (1 <= int(UI_CONFIG.LISTEN_PORT) <= 65535)):
        _exit(3)

    data = {"LISTEN_ADDR": UI_CONFIG.LISTEN_ADDR, "LISTEN_PORT": UI_CONFIG.LISTEN_PORT, "LOG_LEVEL": UI_CONFIG.log_level, "REVERSE_PROXY_IPS": UI_CONFIG.reverse_proxy_ips}

    content = ""
    for k, v in data.items():
        content += f"{k}={v!r}\n"

    with open(join(sep, "etc", "bunkerweb", "ui.env"), "w", encoding="utf-8") as f:
        f.write(content)
