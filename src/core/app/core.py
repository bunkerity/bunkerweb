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
from os import cpu_count, sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from typing import Union

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("db",), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)

CPU_COUNT = cpu_count() or 1


class CoreConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: str = "1337"
    MAX_WORKERS: str = str(CPU_COUNT - 1 if CPU_COUNT > 1 else 1)
    MAX_THREADS: str = str(int(MAX_WORKERS) * 2 if MAX_WORKERS.isdigit() else 2)
    WAIT_RETRY_INTERVAL: str = "5"
    HEALTHCHECK_INTERVAL: str = "30"
    CHECK_WHITELIST: str = "yes"
    WHITELIST: Union[str, set] = "127.0.0.1"
    CHECK_TOKEN: str = "yes"
    TOKEN: str = "changeme"
    BUNKERWEB_INSTANCES: str = ""

    LOG_LEVEL: str = "info"
    DATABASE_URI: str = "sqlite:////var/lib/bunkerweb/db.sqlite3"
    EXTERNAL_PLUGIN_URLS: str = ""
    AUTOCONF_MODE: str = "no"
    KUBERNETES_MODE: str = "no"
    SWARM_MODE: str = "no"

    # The reading order is:
    # 1. Environment variables
    # 2. YAML file
    # 3. .env file
    # 4. Default values
    model_config = YamlSettingsConfigDict(
        yaml_file=join(sep, "etc", "bunkerweb", "config.yaml"),
        env_file=join(sep, "etc", "bunkerweb", "core.conf"),
        env_file_encoding="utf-8",
        extra="allow",
    )

    @cached_property
    def log_level(self) -> str:
        return self.LOG_LEVEL.upper()

    @cached_property
    def check_whitelist(self) -> bool:
        return self.CHECK_WHITELIST.lower() == "yes"

    @cached_property
    def check_token(self) -> bool:
        return self.CHECK_TOKEN.lower() == "yes"

    @cached_property
    def autoconf_mode(self) -> bool:
        return self.AUTOCONF_MODE.lower() == "yes"

    @cached_property
    def kubernetes_mode(self) -> bool:
        return self.KUBERNETES_MODE.lower() == "yes"

    @cached_property
    def swarm_mode(self) -> bool:
        return self.SWARM_MODE.lower() == "yes"

    @cached_property
    def whitelist(
        self,
    ) -> set[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]]:
        if isinstance(self.WHITELIST, str):
            tmp_whitelist = self.WHITELIST.split(" ")
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
                continue

        return whitelist

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

    if not CORE_CONFIG.LISTEN_PORT.isdigit() or not (
        1 <= int(CORE_CONFIG.LISTEN_PORT) <= 65535
    ):
        _exit(1)
    elif not CORE_CONFIG.MAX_WORKERS.isdigit() or int(CORE_CONFIG.MAX_WORKERS) < 1:
        _exit(2)
    elif not CORE_CONFIG.MAX_THREADS.isdigit() or int(CORE_CONFIG.MAX_THREADS) < 1:
        _exit(3)

    data = {
        "LISTEN_ADDR": CORE_CONFIG.LISTEN_ADDR,
        "LISTEN_PORT": CORE_CONFIG.LISTEN_PORT,
        "MAX_WORKERS": CORE_CONFIG.MAX_WORKERS,
        "MAX_THREADS": CORE_CONFIG.MAX_THREADS,
        "LOG_LEVEL": CORE_CONFIG.LOG_LEVEL,
        "AUTOCONF_MODE": CORE_CONFIG.AUTOCONF_MODE,
        "KUBERNETES_MODE": CORE_CONFIG.KUBERNETES_MODE,
        "SWARM_MODE": CORE_CONFIG.SWARM_MODE,
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

If the API is configured to check the authentication token, the token must be provided in the request header. Each request should include an authentication token in the request header. The token can be set in the configuration file or as an environment variable (`API_TOKEN`).

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

from .dependencies import stop


@asynccontextmanager  # type: ignore
async def lifespan(_):
    yield  # ? lifespan of the application

    stop(0)


app = FastAPI(
    title="BunkerWeb API",
    description=description,
    summary="The API used by BunkerWeb to communicate with the database and the instances",
    version=BUNKERWEB_VERSION,
    contact={
        "name": "BunkerWeb Team",
        "url": "https://bunkerweb.io",
        "email": "contact@bunkerity.com",
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "identifier": "AGPL-3.0",
        "url": "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE.md",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)
