#!/usr/bin/python3
# -*- coding: utf-8 -*-

from copy import deepcopy
from datetime import date
from functools import cached_property
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from logging import Logger
from os import cpu_count, getenv, sep
from os.path import join, normpath
from pathlib import Path
from pydantic import field_validator
from regex import IGNORECASE, compile as re_compile
from secrets import choice as secrets_choice
from string import ascii_letters, digits, punctuation
from sys import path as sys_path
from typing import Dict, List, Literal, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("db",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)

BUNKERWEB_STATIC_INSTANCES_RX = re_compile(r"(?P<hostname>(?<![:@])\b[^:@\s]+\b)(:(?P<port>\d+))?(@(?P<server_name>(?=[^\s]{1,255})[^\s]+))?")
EXTERNAL_PLUGIN_URLS_RX = re_compile(r"^( *((https?://|file:///)[-\w@:%.+~#=]+[-\w()!@:%+.~?&/=$#]*)(?!.*\2(?!.)) *)*$")
IP_RX = re_compile(
    r"^((\b25[0-5]|\b2[0-4]\d|\b[01]?\d\d?)(\.(25[0-5]|2[0-4]\d|[01]?\d\d?)){3}|(([0-9a-f]{1,4}:){7,7}[0-9a-f]{1,4}|([0-9a-f]{1,4}:){1,7}:|([0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}|([0-9a-f]{1,4}:){1,5}(:[0-9a-f]{1,4}){1,2}|([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,3}|([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}|([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}|[0-9a-f]{1,4}:((:[0-9a-f]{1,4}){1,6})|:((:[0-9a-f]{1,4}){1,7}|:)|fe80:(:[0-9a-f]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)\.){3,3}(25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)|([0-9a-f]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)\.){3,3}(25[0-5]|(2[0-4]|1{0,1}\d){0,1}\d)))$",  # noqa: E501
    IGNORECASE,
)
TOKEN_RX = re_compile(r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]).{8,}$")


class CoreConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: Union[str, int] = 1337
    MAX_WORKERS: Union[str, int] = max((cpu_count() or 1) - 1, 1)
    MAX_THREADS: Union[str, int] = int(MAX_WORKERS) * 2 if isinstance(MAX_WORKERS, int) or MAX_WORKERS.isdigit() else 2
    WAIT_RETRY_INTERVAL: Union[str, float] = 5.0
    HEALTHCHECK_INTERVAL: Union[str, int] = 30
    CHECK_WHITELIST: Union[Literal["yes", "no"], bool] = "yes"
    WHITELIST: Union[str, set[str]] = {"127.0.0.1"}
    CHECK_TOKEN: Union[Literal["yes", "no"], bool] = "yes"
    CORE_TOKEN: str = ""
    BUNKERWEB_INSTANCES: Union[str, set[str]] = set()

    LOG_LEVEL: Literal["emerg", "alert", "crit", "error", "warn", "warning", "notice", "info", "debug", "EMERG", "ALERT", "CRIT", "ERROR", "WARN", "WARNING", "NOTICE", "INFO", "DEBUG"] = "notice"
    DATABASE_URI: str = "sqlite:////var/lib/bunkerweb/db.sqlite3"
    USE_REDIS: Union[Literal["yes", "no"], bool] = "no"
    REDIS_HOST: str = ""
    REDIS_PORT: Union[str, int] = 6379
    REDIS_DATABASE: Union[str, int] = 0
    REDIS_SSL: Union[str, bool] = False
    REDIS_TIMEOUT: Union[str, float] = 1000.0

    EXTERNAL_PLUGIN_URLS: Union[str, set] = ""
    AUTOCONF_MODE: Union[Literal["yes", "no"], bool] = "no"
    KUBERNETES_MODE: Union[Literal["yes", "no"], bool] = "no"
    SWARM_MODE: Union[Literal["yes", "no"], bool] = "no"

    # The reading order is:
    # 1. Environment variables
    # 2. Secrets files
    # 3. YAML file
    # 4. .env file
    # 5. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=normpath(getenv("SETTINGS_YAML_FILE", join(sep, "etc", "bunkerweb", "config.yaml") if Path(sep, "etc", "bunkerweb", "config.yaml").is_file() else join(sep, "etc", "bunkerweb", "config.yml"))),
        env_file=normpath(getenv("SETTINGS_ENV_FILE", join(sep, "etc", "bunkerweb", "core.conf"))),
        secrets_dir=normpath(getenv("SETTINGS_SECRETS_DIR", join(sep, "run", "secrets"))),
        env_file_encoding="utf-8",
        extra="allow",
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

    @field_validator("HEALTHCHECK_INTERVAL")
    @classmethod
    def check_healthcheck_interval(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or int(v) < 1):
            raise ValueError("Invalid HEALTHCHECK_INTERVAL provided, it must be a positive integer.")
        return v

    @field_validator("CORE_TOKEN")
    @classmethod
    def check_core_token(cls, v: str) -> str:
        if cls.check_token and v and not TOKEN_RX.match(v):
            raise ValueError("Invalid token provided, it must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).")
        return v

    @field_validator("REDIS_PORT")
    @classmethod
    def check_redis_port(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or not (1 <= int(v) <= 65535)):
            raise ValueError("Invalid REDIS_PORT provided, it must be a positive integer between 1 and 65535.")
        return v

    @field_validator("REDIS_DATABASE")
    @classmethod
    def check_redis_database(cls, v: Union[str, int]) -> Union[str, int]:
        if not isinstance(v, int) and (not v.isdigit() or not (0 <= int(v) <= 15)):
            raise ValueError("Invalid REDIS_DATABASE provided, it must be a positive integer between 0 and 15.")
        return v

    @field_validator("REDIS_TIMEOUT")
    @classmethod
    def check_redis_timeout(cls, v: Union[str, float]) -> Union[str, float]:
        try:
            if not float(v) > 0:
                raise ValueError
        except ValueError:
            raise ValueError("Invalid REDIS_TIMEOUT provided, it must be a positive float.")
        return v

    # ? PROPERTIES

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.upper() if self.LOG_LEVEL in ("error", "ERROR", "info", "INFO", "debug", "DEBUG") else ("WARNING" if self.LOG_LEVEL in ("warn", "WARN", "warning", "WARNING") else "INFO")

    @cached_property
    def logger(self) -> Logger:
        return setup_logger("core", self.log_level)

    @cached_property
    def log_level_setting(self) -> str:
        return self.LOG_LEVEL.lower()

    @cached_property
    def check_whitelist(self) -> bool:
        return self.CHECK_WHITELIST == "yes" if isinstance(self.CHECK_WHITELIST, str) else self.CHECK_WHITELIST

    @cached_property
    def check_token(self) -> bool:
        return self.CHECK_TOKEN == "yes" if isinstance(self.CHECK_TOKEN, str) else self.CHECK_TOKEN

    @cached_property
    def use_redis(self) -> bool:
        return self.USE_REDIS == "yes" if isinstance(self.USE_REDIS, str) else self.USE_REDIS

    @cached_property
    def redis_ssl(self) -> bool:
        return self.REDIS_SSL == "yes" if isinstance(self.REDIS_SSL, str) else self.REDIS_SSL

    @cached_property
    def autoconf_mode(self) -> bool:
        return self.AUTOCONF_MODE == "yes" if isinstance(self.AUTOCONF_MODE, str) else self.AUTOCONF_MODE

    @cached_property
    def kubernetes_mode(self) -> bool:
        return self.KUBERNETES_MODE == "yes" if isinstance(self.KUBERNETES_MODE, str) else self.KUBERNETES_MODE

    @cached_property
    def swarm_mode(self) -> bool:
        return self.SWARM_MODE == "yes" if isinstance(self.SWARM_MODE, str) else self.SWARM_MODE

    @cached_property
    def whitelist(
        self,
    ) -> set[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]]:
        if isinstance(self.WHITELIST, str):
            tmp_whitelist = self.WHITELIST.split()
        else:
            tmp_whitelist = self.WHITELIST

        whitelist = set()

        for ip in tmp_whitelist:
            if not ip:
                continue

            try:
                if "/" in ip:
                    whitelist.add(ip_network(ip))
                else:
                    whitelist.add(ip_address(ip))
            except ValueError:
                self.logger.warning(f"Invalid whitelisted IP address/network: {ip}")

        return whitelist

    @cached_property
    def bunkerweb_instances(
        self,
    ) -> List[str]:
        if isinstance(self.BUNKERWEB_INSTANCES, str):
            tmp_bunkerweb_instances = self.BUNKERWEB_INSTANCES.split(" ")
        else:
            tmp_bunkerweb_instances = self.BUNKERWEB_INSTANCES

        bunkerweb_instances = []
        hostnames = set()

        for bw_instance in tmp_bunkerweb_instances:
            if not bw_instance:
                continue

            match = BUNKERWEB_STATIC_INSTANCES_RX.search(bw_instance)
            if match:
                if match.group("hostname") in hostnames:
                    self.logger.warning(f"Duplicate BunkerWeb instance hostname {match.group('hostname')}, skipping it")

                hostnames.add(match.group("hostname"))
                bunkerweb_instances.append(
                    {
                        "hostname": match.group("hostname"),
                        "port": match.group("port") or 5000,
                        "server_name": match.group("server_name") or "bwapi",
                    }
                )
            else:
                self.logger.warning(f"Invalid BunkerWeb instance {bw_instance}, it should match the following regex: <hostname>(:<port>)(@<server_name>) ({self.bunkerweb_static_instance_rx.pattern}), skipping it")

        return bunkerweb_instances

    @cached_property
    def external_plugin_urls(self) -> set[str]:
        if isinstance(self.EXTERNAL_PLUGIN_URLS, str):
            tmp_external_plugin_urls = set(self.EXTERNAL_PLUGIN_URLS.split())
        else:
            tmp_external_plugin_urls = self.EXTERNAL_PLUGIN_URLS

        external_plugin_urls = set()

        for url in tmp_external_plugin_urls:
            if not url:
                continue

            if EXTERNAL_PLUGIN_URLS_RX.match(url):
                external_plugin_urls.add(url)
            else:
                self.logger.warning(f"Invalid external plugin URL {url}, skipping it")

        return external_plugin_urls

    @cached_property
    def external_plugin_urls_str(self) -> str:
        return " ".join(self.external_plugin_urls)

    @cached_property
    def core_token(self) -> str:
        if not self.CORE_TOKEN:
            core_token_path = Path(sep, "var", "cache", "bunkerweb", "core_token")
            if core_token_path.is_file():
                self.CORE_TOKEN = core_token_path.read_text(encoding="utf-8").strip()
            else:
                self.logger.warning(
                    """
##############################################################################################################
#                                                                                                            #
# WARNING: No authentication token provided, generating a random one. Please save it for future use. #
#                                                                                                            #
##############################################################################################################"""
                )
                self.CORE_TOKEN = self.generate_token()
                self.logger.warning(f"Generated authentication token: {self.CORE_TOKEN}")
                core_token_path.write_text(self.CORE_TOKEN, encoding="utf-8")
                self.logger.warning(f"Authentication token saved to {core_token_path}")

        return self.CORE_TOKEN

    @cached_property
    def settings(self) -> Dict[str, str]:
        instances_config = self.model_dump(
            exclude=(
                "CORE",
                "core",
                "GLOBAL",
                "global",
                "UI",
                "ui",
                "AUTOCONF",
                "autoconf",
                "LISTEN_ADDR",
                "LISTEN_PORT",
                "MAX_WORKERS",
                "MAX_THREADS",
                "WAIT_RETRY_INTERVAL",
                "HEALTHCHECK_INTERVAL",
                "CORE_TOKEN",
                "core_token",
                "BUNKERWEB_INSTANCES",
                "bunkerweb_instances",
                "external_plugin_urls",
                "external_plugin_urls_str",
                "log_level",
                "log_level_setting",
                "check_whitelist",
                "CHECK_WHITELIST",
                "check_token",
                "CHECK_TOKEN",
                "kubernetes_mode",
                "swarm_mode",
                "autoconf_mode",
                "whitelist",
                "WHITELIST",
                "integration",
            )
        )

        for config, value in deepcopy(instances_config).items():
            if isinstance(value, list):
                for i, setting in enumerate(value, start=1):
                    instances_config[f"{config}_{i}"] = setting
                del instances_config[config]
            elif isinstance(value, bool):
                instances_config[config] = "yes" if value else "no"
            elif isinstance(value, (float, int, date)):
                instances_config[config] = str(value)
            elif not isinstance(value, str):
                del instances_config[config]

        instances_config.update(
            {
                "MULTISITE": "yes" if any((self.kubernetes_mode, self.swarm_mode, self.autoconf_mode)) else instances_config.get("MULTISITE", "no"),
                "LOG_LEVEL": self.log_level_setting,
                "EXTERNAL_PLUGIN_URLS": self.external_plugin_urls_str,
                "AUTOCONF_MODE": "yes" if self.autoconf_mode else "no",
                "KUBERNETES_MODE": "yes" if self.kubernetes_mode else "no",
                "SWARM_MODE": "yes" if self.swarm_mode else "no",
            }
        )
        return instances_config

    @cached_property
    def integration(self) -> str:
        if self.kubernetes_mode:
            return "Kubernetes"
        elif self.swarm_mode:
            return "Swarm"
        elif self.autoconf_mode:
            return "Autoconf"

        return self.get_instance()

    # ? METHODS

    @staticmethod
    def get_instance() -> str:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "Docker"

        return "Linux"

    @staticmethod
    def generate_token() -> str:
        """Generate a random 16 characters token with at least one uppercase letter, one lowercase letter, one digit, and one punctuation character."""
        token = ""
        while not all((any(c in token for c in ascii_letters), any(c in token for c in digits), any(c in token for c in punctuation))):
            token = "".join(secrets_choice(ascii_letters + digits + punctuation) for _ in range(16))

        return token


if __name__ == "__main__":
    from os import _exit, environ

    CORE_CONFIG = CoreConfig("core", **environ)

    data = {
        "LISTEN_ADDR": CORE_CONFIG.LISTEN_ADDR,
        "LISTEN_PORT": CORE_CONFIG.LISTEN_PORT,
        "MAX_WORKERS": CORE_CONFIG.MAX_WORKERS,
        "MAX_THREADS": CORE_CONFIG.MAX_THREADS,
        "LOG_LEVEL": CORE_CONFIG.log_level,
        "AUTOCONF_MODE": "yes" if CORE_CONFIG.autoconf_mode else "no",
        "KUBERNETES_MODE": "yes" if CORE_CONFIG.kubernetes_mode else "no",
        "SWARM_MODE": "yes" if CORE_CONFIG.swarm_mode else "no",
    }

    content = ""
    for k, v in data.items():
        content += f"{k}={v!r}\n"

    Path(sep, "tmp", "core.tmp.env").write_text(content, encoding="utf-8")

    _exit(0)


BUNKERWEB_VERSION = Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()

description = """# BunkerWeb Internal API Documentation

The BunkerWeb Internal API is designed to manage BunkerWeb's instances, communicate with a Database, and interact with various BunkerWeb services, including the scheduler, autoconf, and Web UI. This API provides the necessary endpoints for performing operations related to instance management, database communication, and service interaction.

## Configuration

The API can be configured using environment variables or a configuration file (YAML and a dotenv file). The configuration files are located at `/etc/bunkerweb/config.yml` and `/etc/bunkerweb/core.conf` by default. The environment variables has precedence over the configuration file. You can also use Docker secrets to configure the API (see the [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/) documentation for more information).

### API configuration

The API can be configured using the following settings:

| Name | Description | Default value |
| --- | --- | --- |
| `LISTEN_ADDR` | The address to listen on | `0.0.0.0` |
| `LISTEN_PORT` | The port to listen on | `1337` |
| `MAX_WORKERS` | The maximum number of workers | `cpu_count() - 1` |
| `MAX_THREADS` | The maximum number of threads | `MAX_WORKERS * 2` |
| `WAIT_RETRY_INTERVAL` | The interval between retries when waiting for a service to be up | `5` |
| `HEALTHCHECK_INTERVAL` | The interval between healthchecks | `30` |
| `CHECK_WHITELIST` | Activate the whitelist | `yes` |
| `WHITELIST` | The whitelist | `127.0.0.1` |
| `CHECK_TOKEN` | Activate the authentication token | `yes` |
| `CORE_TOKEN` | The accepted authentication token | `<random>` |
| `BUNKERWEB_INSTANCES` | The static BunkerWeb instances | `[]` |
| `LOG_LEVEL` | The log level | `notice` |
| `DATABASE_URI` | The database URI | `sqlite:////var/lib/bunkerweb/db.sqlite3` |
| `USE_REDIS` | Activate Redis | `no` |
| `REDIS_HOST` | The Redis host | `""` |
| `REDIS_PORT` | The Redis port | `6379` |
| `REDIS_DATABASE` | The Redis database | `0` |
| `REDIS_SSL` | Activate SSL for Redis | `no` |
| `REDIS_TIMEOUT` | The Redis timeout in milliseconds | `1000.0` |
| `EXTERNAL_PLUGIN_URLS` | The external plugin URLs to download | `""` |
| `AUTOCONF_MODE` | Activate the autoconf mode | `no` |
| `KUBERNETES_MODE` | Activate the Kubernetes mode | `no` |
| `SWARM_MODE` | Activate the Swarm mode | `no` |

### Instance configuration

The instance can be configured using BunkerWeb's settings (see the [BunkerWeb settings documentation](https://docs.bunkerweb.io/latest/settings/) for more information).

**These settings can be added to the configuration file or as environment variables.**

## Authentication

If the API is configured to check the authentication token, the token must be provided in the request header. Each request should include an authentication token in the request header. The token can be set in the configuration file or as an environment variable (`CORE_TOKEN`).

Example:

```
Authorization: Bearer YOUR_AUTH_TOKEN
```

**If no token is provided, the API will generate a token, print it to the logs, and save it to `/var/cache/bunkerweb/core_token`.**

## Whitelist

If the API is configured to check the whitelist, the IP address of the client must be in the whitelist. The whitelist can be set in the configuration file or as an environment variable (`API_WHITELIST`). The whitelist can contain IP addresses and/or IP networks.

## Instance management

The BunkerWeb instances have to be declared in the configuration file or as environment variables (`BUNKERWEB_INSTANCES`). The instances can be static or dynamic. The static instances are declared in the configuration file or as environment variables (`BUNKERWEB_INSTANCES`). The dynamic instances are automatically discovered using Redis.

### Static instances

The static instances are declared in the configuration file or as environment variables (`BUNKERWEB_INSTANCES`). The static instances are defined as follows:

    <hostname>[:<port>][@<server_name>]

- `hostname`: The hostname of the instance

- `port`: The port of the instance (default: `5000`)

- `server_name`: The server name of the instance (default: `bwapi`)

Example:

```yaml
# Configuration file
BUNKERWEB_INSTANCES: "bw1.example.com bw2.example.com:5000 bw3.example.com:5000@bwapi"
```

```bash
# Environment variables
BUNKERWEB_INSTANCES="bw1.example.com bw2.example.com:5000 bw3.example.com:5000@bwapi"
```

### Dynamic instances

The dynamic instances are automatically discovered using Redis. **Remember to activate Redis in the configuration file or as environment variables (`USE_REDIS`)**."""  # noqa: E501

tags_metadata = [
    {"name": "misc", "description": "Miscellaneous operations"},
    {"name": "instances", "description": "Operations related to instance management"},
    {"name": "plugins", "description": "Operations related to plugin management"},
    {"name": "config", "description": "Operations related to configuration management"},
    {"name": "custom_configs", "description": "Operations related to custom configuration management"},
    {"name": "jobs", "description": "Operations related to job management"},
    {"name": "actions", "description": "Operations related to action management"},
]
