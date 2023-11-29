# -*- coding: utf-8 -*-
from functools import cached_property
from os import cpu_count, getenv, sep
from os.path import join, normpath
from pathlib import Path
from sys import path as sys_path
from typing import List, Literal, Optional, Set, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from pydantic import field_validator
from regex import IGNORECASE, compile as re_compile
from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)

CORE_ADDR_RX = re_compile(r"^(https?://[a-z0-9.-]{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$", IGNORECASE)
IP_RX = re_compile(
    r"^((\b25[0-5]|\b2[0-4]\d|\b[01]?\d\d?)(\.(25[0-5]|2[0-4]\d|[01]?\d\d?)){3}|(([0-9a-f]{1,4}:){7,7}[0-9a-f]{1,4}|([0-9a-f]{1,4}:){1,7}:|([0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}|([0-9a-f]{1,4}:){1,5}(:[0-9a-f]{1,4}){1,2}|([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,3}|([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}|([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}|[0-9a-f]{1,4}:((:[0-9a-f]{1,4}){1,6})|:((:[0-9a-f]{1,4}){1,7}|:)|fe80:(:[0-9a-f]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)\.){3,3}(25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)|([0-9a-f]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)\.){3,3}(25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)))$",  # noqa: E501
    IGNORECASE,
)
NETWORK_RX = re_compile(
    r"^((\b25[0-5]|\b2[0-4]\d|\b[01]?\d\d?)(\.(25[0-5]|2[0-4]\d|[01]?\d\d?)){3})(\/([1-2][0-9]?|3[0-2]?|[04-9]))?|(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]Z{0,4}){0,4}%[0-9a-zA-Z]+|::(ffff(:0{1,4})?:)?((25[0-5]|(2[0-4]|1?\d)?\d)\.){3}(25[0-5]|(2[0-4]|1?\d)?\d)|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1?\d)?\d)\.){3}(25[0-5]|(2[0-4]|1?\d)?\d))(\/(12[0-8]|1[01][0-9]|[0-9][0-9]?))?(?!.*\D\2([^\d\/]|$))$",  # noqa: E501
    IGNORECASE,
)
TOKEN_RX = re_compile(r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]).{8,}$")


class UiConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: Union[str, int] = 7000
    CORE_ADDR: str = "http://127.0.0.1:1337"
    CORE_TOKEN: Optional[str] = None
    MAX_WORKERS: Union[str, int] = max((cpu_count() or 1) - 1, 1)
    MAX_THREADS: Union[str, int] = int(MAX_WORKERS) * 2 if isinstance(MAX_WORKERS, int) or MAX_WORKERS.isdigit() else 2
    EXIT_ON_FAILURE: str = "yes"
    WAIT_RETRY_INTERVAL: Union[str, float] = 5.0
    MAX_WAIT_RETRIES: Union[str, int] = 10
    LOG_LEVEL: Literal["debug", "info", "warning", "error", "critical", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "info"
    REVERSE_PROXY_IPS: Union[str, List[str], Set[str], Tuple[str]] = {
        "192.168.0.0/16",
        "172.16.0.0/12",
        "10.0.0.0/8",
        "127.0.0.0/8",
    }

    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    UI_USE_PROXY_PROTOCOL: Union[Literal["yes", "no"], bool] = "no"

    # The reading order is:
    # 1. Environment variables
    # 2. Secrets files
    # 3. YAML file
    # 4. .env file
    # 5. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=normpath(getenv("SETTINGS_YAML_FILE", join(sep, "etc", "bunkerweb", "config.yaml") if Path(sep, "etc", "bunkerweb", "config.yaml").is_file() else join(sep, "etc", "bunkerweb", "config.yml"))),
        env_file=normpath(getenv("SETTINGS_ENV_FILE", join(sep, "etc", "bunkerweb", "ui.conf"))),
        secrets_dir=normpath(getenv("SETTINGS_SECRETS_DIR", join(sep, "run", "secrets"))),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ? VALIDATION

    @field_validator("LISTEN_ADDR")
    @classmethod
    def check_listen_addr(cls, v: str) -> str:
        if not IP_RX.match(v):
            raise ValueError("Invalid LISTEN_ADDR provided, it must be a valid IPv4 or IPv6 address.")
        return v

    @field_validator("LISTEN_PORT")
    @classmethod
    def check_listen_port(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or not (1 <= int(v) <= 65535)):
            raise ValueError("Invalid LISTEN_PORT provided, it must be a positive integer between 1 and 65535.")
        return v

    @field_validator("CORE_ADDR")
    @classmethod
    def check_core_addr(cls, v: str) -> str:
        if not CORE_ADDR_RX.match(v):
            raise ValueError("Invalid CORE_ADDR provided, it must be a valid URL.")
        return v

    @field_validator("CORE_TOKEN")
    @classmethod
    def check_core_token(cls, v: str) -> str:
        if v and not TOKEN_RX.match(v):
            raise ValueError("Invalid CORE_TOKEN provided, it must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).")
        return v

    @field_validator("MAX_WORKERS")
    @classmethod
    def check_max_workers(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or int(v) < 1):
            raise ValueError("Invalid MAX_WORKERS provided, it must be a positive integer.")
        return v

    @field_validator("MAX_THREADS")
    @classmethod
    def check_max_threads(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or int(v) < 1):
            raise ValueError("Invalid MAX_THREADS provided, it must be a positive integer.")
        return v

    @field_validator("WAIT_RETRY_INTERVAL")
    @classmethod
    def check_wait_retry_interval(cls, v: Union[str, float]) -> Union[str, float]:
        try:
            if not float(v) > 0:
                raise ValueError
        except ValueError:
            raise ValueError("Invalid WAIT_RETRY_INTERVAL provided, it must be a positive float.")
        return v

    @field_validator("MAX_WAIT_RETRIES")
    @classmethod
    def check_max_wait_retries(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or int(v) < 1):
            raise ValueError("Invalid MAX_WAIT_RETRIES provided, it must be a positive integer.")
        return v

    @field_validator("ADMIN_PASSWORD")
    @classmethod
    def check_admin_password(cls, v: str) -> str:
        if v and not TOKEN_RX.match(v):
            raise ValueError("Invalid ADMIN_PASSWORD provided, it must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).")
        return v

    @field_validator("REVERSE_PROXY_IPS")
    @classmethod
    def check_reverse_proxy_ips(cls, v: Union[str, List[str], Set[str], Tuple[str]]) -> Union[str, List[str], Set[str], Tuple[str]]:
        if isinstance(v, str):
            v = {v}

        for ip in v:
            if not ip:
                continue

            if not NETWORK_RX.match(ip) and not IP_RX.match(ip):
                raise ValueError("Invalid REVERSE_PROXY_IPS provided, it must be a valid IPv4 or IPv6 address or network.")
        return v

    # ? PROPERTIES

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.lower()

    @cached_property
    def reverse_proxy_ips(self) -> str:
        if not isinstance(self.REVERSE_PROXY_IPS, str):
            return " ".join(self.REVERSE_PROXY_IPS)
        return self.REVERSE_PROXY_IPS

    @cached_property
    def use_proxy_protocol(self) -> bool:
        return self.UI_USE_PROXY_PROTOCOL == "yes" if isinstance(self.UI_USE_PROXY_PROTOCOL, str) else self.UI_USE_PROXY_PROTOCOL

    @cached_property
    def use_proxy_protocol_str(self) -> str:
        return "yes" if self.use_proxy_protocol else "no"

    @property
    def core_token(self) -> Optional[str]:
        if not self.CORE_TOKEN:
            core_token_path = Path(sep, "var", "cache", "bunkerweb", "core_token")
            if core_token_path.is_file():
                self.CORE_TOKEN = core_token_path.read_text(encoding="utf-8").strip()

        return self.CORE_TOKEN


if __name__ == "__main__":
    from os import environ

    UI_CONFIG = UiConfig("ui", **environ)

    data = {
        "LISTEN_ADDR": UI_CONFIG.LISTEN_ADDR,
        "LISTEN_PORT": UI_CONFIG.LISTEN_PORT,
        "LOG_LEVEL": UI_CONFIG.log_level,
        "REVERSE_PROXY_IPS": UI_CONFIG.reverse_proxy_ips,
        "UI_USE_PROXY_PROTOCOL": UI_CONFIG.use_proxy_protocol_str,
    }

    content = ""
    for k, v in data.items():
        content += f"{k}={v!r}\n"

    with open(join(sep, "etc", "bunkerweb", "ui.env"), "w", encoding="utf-8") as f:
        f.write(content)
