from contextlib import asynccontextmanager
from datetime import datetime
from functools import cached_property
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from os import sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from typing import Dict, List, Literal, Optional, Union

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("db",), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI
from pydantic import BaseModel, Field

from yaml_base_settings import YamlBaseSettings, YamlSettingsConfigDict  # type: ignore (present in /usr/share/bunkerweb/utils/)


class ApiConfig(YamlBaseSettings):
    LISTEN_ADDR: str = "0.0.0.0"
    LISTEN_PORT: str = "1337"
    WAIT_RETRY_INTERVAL: str = "5"
    CHECK_WHITELIST: str = "yes"
    WHITELIST: str = "127.0.0.1"
    CHECK_TOKEN: str = "yes"
    TOKEN: str = "changeme"
    MQ_URI: str = "filesystem:////var/lib/bunkerweb/mq"
    BUNKERWEB_INSTANCES: str = ""

    LOG_LEVEL: str = "info"
    DATABASE_URI: str = "sqlite:////var/lib/bunkerweb/db.sqlite3"
    EXTERNAL_PLUGIN_URLS: str = ""
    KUBERNETES_MODE: str = "no"
    SWARM_MODE: str = "no"
    AUTOCONF_MODE: str = "no"

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
    def kubernetes_mode(self) -> bool:
        return self.KUBERNETES_MODE.lower() == "yes"

    @cached_property
    def swarm_mode(self) -> bool:
        return self.SWARM_MODE.lower() == "yes"

    @cached_property
    def autoconf_mode(self) -> bool:
        return self.AUTOCONF_MODE.lower() == "yes"

    @cached_property
    def whitelist(
        self,
    ) -> List[Union[IPv4Address, IPv6Address, IPv4Network, IPv6Network]]:
        tmp_whitelist = self.WHITELIST.split(" ")
        whitelist = []

        for ip in tmp_whitelist:
            if not ip:
                continue

            try:
                if "/" in ip:
                    whitelist.append(ip_network(ip))
                else:
                    whitelist.append(ip_address(ip))
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
    from json import dumps
    from os import _exit, environ

    API_CONFIG = ApiConfig("core", **environ)

    if (
        not API_CONFIG.LISTEN_PORT.isdigit()
        or int(API_CONFIG.LISTEN_PORT) < 1
        or int(API_CONFIG.LISTEN_PORT) > 65535
    ):
        _exit(1)

    data = {
        "listen_addr": API_CONFIG.LISTEN_ADDR,
        "listen_port": API_CONFIG.LISTEN_PORT,
        "log_level": API_CONFIG.LOG_LEVEL,
        "kubernetes_mode": API_CONFIG.kubernetes_mode,
        "swarm_mode": API_CONFIG.swarm_mode,
        "autoconf_mode": API_CONFIG.autoconf_mode,
    }

    print(dumps(data), flush=True)
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

from .dependencies import HEALTHY_PATH


@asynccontextmanager  # type: ignore
async def lifespan(_):
    yield  # ? lifespan of the application

    if HEALTHY_PATH.exists():
        HEALTHY_PATH.unlink(missing_ok=True)


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


class Instance(BaseModel):
    hostname: str = Field(examples=["bunkerweb-1"])
    port: int = Field(examples=[5000])
    server_name: str = Field(examples=["bwapi"])


class Plugin(BaseModel):
    id: str = Field(examples=["blacklist"])
    stream: str = Field(examples=["partial"])
    name: str = Field(examples=["Blacklist"])
    description: str = Field(
        examples=[
            "Deny access based on internal and external IP/network/rDNS/ASN blacklists."
        ]
    )
    version: str = Field(examples=["1.0"])
    external: bool = Field(examples=[False])
    method: str = Field(examples=["core"])
    page: bool = Field(examples=[False])
    settings: Dict[
        str,
        Dict[
            Union[
                Literal[
                    "context",
                    "default",
                    "help",
                    "id",
                    "label",
                    "regex",
                    "type",
                ],
                Literal[
                    "context",
                    "default",
                    "help",
                    "id",
                    "label",
                    "regex",
                    "type",
                    "select",
                    "multiple",
                ],
                Literal[
                    "context",
                    "default",
                    "help",
                    "id",
                    "label",
                    "regex",
                    "type",
                    "multiple",
                ],
                Literal[
                    "context",
                    "default",
                    "help",
                    "id",
                    "label",
                    "regex",
                    "type",
                    "select",
                ],
            ],
            Union[str, List[str]],
        ],
    ] = Field(
        examples=[
            {
                "USE_BLACKLIST": {
                    "context": "multisite",
                    "default": "yes",
                    "help": "Activate blacklist feature.",
                    "id": "use-blacklist",
                    "label": "Activate blacklisting",
                    "regex": "^(yes|no)$",
                    "type": "check",
                }
            }
        ]
    )
    jobs: List[
        Dict[Literal["name", "file", "every", "reload"], Union[str, bool]]
    ] = Field(
        None,
        examples=[
            [
                {
                    "name": "blacklist-download",
                    "file": "blacklist-download.py",
                    "every": "hour",
                    "reload": True,
                }
            ]
        ],
    )


class AddedPlugin(Plugin):
    data: bytes = Field(examples=[b"BunkerWeb forever"])
    checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
    )
    template_file: bytes = Field(None, examples=[b"BunkerWeb forever"])
    actions_file: bytes = Field(None, examples=[b"BunkerWeb forever"])
    template_checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
    )
    actions_checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
    )


class Job(BaseModel):
    every: str = Field(examples=["hour"])
    reload: bool = Field(examples=[True])
    history: List[Dict[str, Union[str, bool]]] = Field(
        examples=[
            [
                {
                    "start_date": "2021-01-01T00:00:00.000Z",
                    "end_date": "2021-01-01T00:00:00.000Z",
                    "success": True,
                }
            ]
        ]
    )
    cache: List[Dict[str, Optional[str]]] = Field(
        examples=[
            [
                {
                    "service_id": None,
                    "file_name": "ASN.txt",
                    "last_update": "2021-01-01T00:00:00.000Z",
                    "checksum": "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d",
                }
            ]
        ]
    )


class Job_cache(BaseModel):
    last_update: str = Field(None, examples=["1609459200.0"])
    checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
    )
    data: bytes = Field(None, examples=[b"BunkerWeb forever"])


class ErrorMessage(BaseModel):
    message: str


class CacheFileModel(BaseModel):
    service_id: Optional[str] = None


class CacheFileDataModel(CacheFileModel):
    with_info: bool = False
    with_data: bool = True


class CacheFileInfoModel(CacheFileModel):
    last_update: datetime
    checksum: Optional[str] = None


class CustomConfigModel(CacheFileModel):
    type: str = Field(examples=["server_http"])


class CustomConfigNameModel(CustomConfigModel):
    name: str = Field(examples=["my_custom_config"])


class CustomConfigDataModel(CustomConfigNameModel):
    data: bytes = Field(examples=[b"BunkerWeb forever"])
    checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA256 checksum of the data",
    )
