from contextlib import asynccontextmanager
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
from re import compile as re_compile
from sys import path as sys_path
from typing import Dict, List, Literal, Union

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("db",), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI

from logger import setup_logger  # type: ignore
from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)

CPU_COUNT = cpu_count() or 1
BUNKERWEB_STATIC_INSTANCES_RX = re_compile(r"([^ :]{1,255})(:(\d+))?(:(\w+))?")
EXTERNAL_PLUGIN_URLS_RX = re_compile(
    r"^( *((https?://|file:///)[-\w@:%.+~#=]+[-\w()!@:%+.~?&/=$#]*)(?!.*\2(?!.)) *)*$"
)


class CoreConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: Union[str, int] = 1337
    MAX_WORKERS: Union[str, int] = CPU_COUNT - 1 if CPU_COUNT > 1 else 1
    MAX_THREADS: Union[str, int] = (
        int(MAX_WORKERS) * 2
        if isinstance(MAX_WORKERS, int) or MAX_WORKERS.isdigit()
        else 2
    )
    WAIT_RETRY_INTERVAL: Union[str, int] = 5
    HEALTHCHECK_INTERVAL: Union[str, int] = 30
    CHECK_WHITELIST: Union[str, bool] = "yes"
    WHITELIST: Union[str, set] = "127.0.0.1"
    CHECK_TOKEN: Union[str, bool] = "yes"
    CORE_TOKEN: str = "changeme"
    BUNKERWEB_INSTANCES: Union[str, List[str]] = []

    LOG_LEVEL: Literal[
        "emerg",
        "alert",
        "crit",
        "error",
        "warn",
        "notice",
        "info",
        "debug",
        "EMERG",
        "ALERT",
        "CRIT",
        "ERROR",
        "WARN",
        "NOTICE",
        "INFO",
        "DEBUG",
    ] = "notice"
    DATABASE_URI: str = "sqlite:////var/lib/bunkerweb/db.sqlite3"
    EXTERNAL_PLUGIN_URLS: Union[str, set] = ""
    AUTOCONF_MODE: Union[Literal["y", "yes", "n", "no"], bool] = "no"
    KUBERNETES_MODE: Union[Literal["y", "yes", "n", "no"], bool] = "no"
    SWARM_MODE: Union[Literal["y", "yes", "n", "no"], bool] = "no"

    # The reading order is:
    # 1. Environment variables
    # 2. Secrets files
    # 3. YAML file
    # 4. .env file
    # 5. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=normpath(
            getenv("SETTINGS_YAML_FILE", join(sep, "etc", "bunkerweb", "config.yaml"))
        ),
        env_file=normpath(
            getenv("SETTINGS_ENV_FILE", join(sep, "etc", "bunkerweb", "core.conf"))
        ),
        secrets_dir=normpath(
            getenv("SETTINGS_SECRETS_DIR", join(sep, "run", "secrets"))
        ),
        env_file_encoding="utf-8",
        extra="allow",
    )

    @cached_property
    def logger(self) -> Logger:
        return setup_logger("core", self.log_level)

    @cached_property
    def log_level(self) -> str:
        return (
            self.LOG_LEVEL.upper()
            if self.LOG_LEVEL in ("error", "info", "debug")
            else ("WARNING" if self.LOG_LEVEL == "warn" else "INFO")
        )

    @cached_property
    def log_level_settings(self) -> str:
        return self.LOG_LEVEL.lower()

    @cached_property
    def check_whitelist(self) -> bool:
        return (
            self.CHECK_WHITELIST.lower().startswith("y")
            if isinstance(self.CHECK_WHITELIST, str)
            else self.CHECK_WHITELIST
        )

    @cached_property
    def check_token(self) -> bool:
        return (
            self.CHECK_TOKEN.lower().startswith("y")
            if isinstance(self.CHECK_TOKEN, str)
            else self.CHECK_TOKEN
        )

    @cached_property
    def autoconf_mode(self) -> bool:
        return (
            self.AUTOCONF_MODE.lower().startswith("y")
            if isinstance(self.AUTOCONF_MODE, str)
            else self.AUTOCONF_MODE
        )

    @cached_property
    def kubernetes_mode(self) -> bool:
        return (
            self.KUBERNETES_MODE.lower().startswith("y")
            if isinstance(self.KUBERNETES_MODE, str)
            else self.KUBERNETES_MODE
        )

    @cached_property
    def swarm_mode(self) -> bool:
        return (
            self.SWARM_MODE.lower().startswith("y")
            if isinstance(self.SWARM_MODE, str)
            else self.SWARM_MODE
        )

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
            tmp_bunkerweb_instances = self.BUNKERWEB_INSTANCES.split()
        else:
            tmp_bunkerweb_instances = self.BUNKERWEB_INSTANCES

        bunkerweb_instances = []
        hostnames = set()

        for bw_instance in tmp_bunkerweb_instances:
            if not bw_instance:
                continue

            match = BUNKERWEB_STATIC_INSTANCES_RX.search(bw_instance)
            if match:
                groups = match.groups()

                if groups[0] in hostnames:
                    self.logger.warning(
                        f"Duplicate BunkerWeb instance hostname {groups[0]}, skipping it"
                    )

                hostnames.add(groups[0])
                bunkerweb_instances.append(
                    {
                        "hostname": groups[0],
                        "port": groups[2] or 5000,
                        "server_name": groups[-1] or "bwapi",
                    }
                )
            else:
                self.logger.warning(
                    f"Invalid BunkerWeb instance {bw_instance}, it should match the following regex: {self.bunkerweb_static_instance_rx.pattern}, skipping it"
                )

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
    def settings(self) -> Dict[str, str]:
        instances_config = self.model_dump(
            exclude=(
                "CORE",
                "GLOBAL",
                "LISTEN_ADDR",
                "LISTEN_PORT",
                "MAX_WORKERS",
                "MAX_THREADS",
                "WAIT_RETRY_INTERVAL",
                "HEALTHCHECK_INTERVAL",
                "CORE_TOKEN",
                "BUNKERWEB_INSTANCES",
                "bunkerweb_instances",
                "external_plugin_urls",
                "log_level",
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

        instances_config.update(
            {
                "MULTISITE": "yes"
                if self.kubernetes_mode or self.swarm_mode or self.autoconf_mode
                else instances_config.get("MULTISITE", "no"),
                "LOG_LEVEL": self.log_level_settings,
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

        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(
            encoding="utf-8"
        ):
            return "Docker"

        return "Linux"


if __name__ == "__main__":
    from os import _exit, environ

    CORE_CONFIG = CoreConfig("core", **environ)

    if not isinstance(CORE_CONFIG.LISTEN_PORT, int) and (
        not CORE_CONFIG.LISTEN_PORT.isdigit()
        or not (1 <= int(CORE_CONFIG.LISTEN_PORT) <= 65535)
    ):
        _exit(2)
    elif not isinstance(CORE_CONFIG.MAX_WORKERS, int) and (
        not CORE_CONFIG.MAX_WORKERS.isdigit() or int(CORE_CONFIG.MAX_WORKERS) < 1
    ):
        _exit(3)
    elif not isinstance(CORE_CONFIG.MAX_THREADS, int) and (
        not CORE_CONFIG.MAX_THREADS.isdigit() or int(CORE_CONFIG.MAX_THREADS) < 1
    ):
        _exit(4)

    data = {
        "LISTEN_ADDR": CORE_CONFIG.LISTEN_ADDR,
        "LISTEN_PORT": CORE_CONFIG.LISTEN_PORT,
        "MAX_WORKERS": CORE_CONFIG.MAX_WORKERS,
        "MAX_THREADS": CORE_CONFIG.MAX_THREADS,
        "LOG_LEVEL": CORE_CONFIG.LOG_LEVEL,
        "AUTOCONF_MODE": "yes" if CORE_CONFIG.autoconf_mode else "no",
        "KUBERNETES_MODE": "yes" if CORE_CONFIG.kubernetes_mode else "no",
        "SWARM_MODE": "yes" if CORE_CONFIG.swarm_mode else "no",
    }

    content = ""
    for k, v in data.items():
        content += f"{k}={v!r}\n"

    with open("/tmp/core.tmp.env", "w", encoding="utf-8") as f:
        f.write(content)

    _exit(0)


BUNKERWEB_VERSION = (
    Path(sep, "usr", "share", "bunkerweb", "VERSION")
    .read_text(encoding="utf-8")
    .strip()
)

description = """# BunkerWeb Internal API Documentation

The BunkerWeb Internal API is designed to manage BunkerWeb's instances, communicate with a Database, and interact with various BunkerWeb services, including the scheduler, autoconf, and Web UI. This API provides the necessary endpoints for performing operations related to instance management, database communication, and service interaction.

## Authentication

If the API is configured to check the authentication token, the token must be provided in the request header. Each request should include an authentication token in the request header. The token can be set in the configuration file or as an environment variable (`CORE_TOKEN`).

Example:

```
Authorization: Bearer YOUR_AUTH_TOKEN
```

## Whitelist

If the API is configured to check the whitelist, the IP address of the client must be in the whitelist. The whitelist can be set in the configuration file or as an environment variable (`API_WHITELIST`). The whitelist can contain IP addresses and/or IP networks.
"""

tags_metadata = [  # TODO: Add more tags and better descriptions: https://fastapi.tiangolo.com/tutorial/metadata/?h=swagger#metadata-for-tags
    {
        "name": "misc",
        "description": "Miscellaneous operations",
    },
    {
        "name": "instances",
        "description": "Operations related to instance management",
    },
    {
        "name": "plugins",
        "description": "Operations related to plugin management",
    },
    {
        "name": "config",
        "description": "Operations related to configuration management",
    },
    {
        "name": "custom_configs",
        "description": "Operations related to custom configuration management",
    },
    {
        "name": "jobs",
        "description": "Operations related to job management",
    },
]
