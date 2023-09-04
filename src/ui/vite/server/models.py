#!/usr/bin/python3

from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator



class Instance(BaseModel):
    hostname: str = Field(examples=["bunkerweb-1"], description="The server hostname")
    port: int = Field(examples=[5000], description="The server port")
    server_name: str = Field(
        examples=["bwapi"],
        description="The instance's server name to be used in the API",
    )


class ResponseModel(BaseModel):
    type: str = Field(examples=["success"], description="success or error communicating with core API")
    status: str | int = Field(examples=[200], description="Status return by core API or fallback")
    message: str = Field(
        examples=["Get global config succeed"],
        description="Feedback message to display on UI",
    )
    data: str = Field(
        examples=[""],
        description="Any stringify data that will be used on UI",
    )




class InstanceWithMethod(Instance):
    method: str = Field(examples=["static"], description="The method used by the API")


class InstanceWithInfo(InstanceWithMethod):
    status: str = Field(examples=["up"], description="The instance status")


class Plugin(BaseModel):
    id: str = Field(examples=["blacklist"], description="The plugin id")
    stream: str = Field(examples=["partial"], description="The plugin stream")
    name: str = Field(examples=["Blacklist"], description="The plugin name")
    description: str = Field(
        examples=[
            "Deny access based on internal and external IP/network/rDNS/ASN blacklists."
        ],
        description="The plugin description",
    )
    version: str = Field(examples=["1.0"], description="The plugin version")
    external: bool = Field(examples=[False], description="If the plugin is external")
    method: str = Field(
        examples=["core"], description="Which service created the plugin"
    )
    page: bool = Field(examples=[False], description="If the plugin has a page")
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
        ],
        description="The plugin settings",
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
        description="The jobs that the plugin has",
    )


class AddedPlugin(Plugin):
    data: bytes = Field(examples=[b"BunkerWeb forever"], description="The plugin data")
    checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the plugin file",
    )
    template_file: bytes = Field(
        None, examples=[b"BunkerWeb forever"], description="The template file data"
    )
    actions_file: bytes = Field(
        None, examples=[b"BunkerWeb forever"], description="The actions file data"
    )
    template_checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the template file",
    )
    actions_checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the actions file",
    )


class Job(BaseModel):
    every: str = Field(
        examples=["hour"],
        description="The job execution frequency, can be: hour, day, week, month or a cron expression",
    )
    reload: bool = Field(
        examples=[True],
        description="Data about if the job should reload BunkerWeb after execution",
    )
    history: List[Dict[str, Union[str, bool]]] = Field(
        examples=[
            [
                {
                    "start_date": "2021-01-01T00:00:00.000Z",
                    "end_date": "2021-01-01T00:00:00.000Z",
                    "success": True,
                }
            ]
        ],
        description="The last 10 job executions information",
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
        ],
        description="The cache files, if any, that the job has",
    )


class Job_cache(BaseModel):
    last_update: Optional[float] = Field(None, examples=["1609459200.0"])
    checksum: Optional[str] = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the cache file",
    )
    data: Optional[bytes] = Field(
        None, examples=[b"BunkerWeb forever"], description="The cache file data"
    )


class ErrorMessage(BaseModel):
    message: str


class CacheFileModel(BaseModel):
    service_id: Optional[str] = Field(
        None,
        examples=["www.example.com"],
        description="The service that the cache file belongs to",
    )


class CacheFileDataModel(CacheFileModel):
    with_info: bool = Field(
        False,
        examples=[True],
        description="Will return the cache file info, being: last_update and checksum",
    )
    with_data: bool = Field(
        True,
        examples=[False],
        description="Will return the cache file data",
    )


class CacheFileInfoModel(CacheFileModel):
    last_update: Union[datetime, float] = Field(
        examples=["1609459200.0"], description="The last update date"
    )
    checksum: Optional[str] = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the cache file",
    )


class CustomConfigModel(CacheFileModel):
    type: str = Field(examples=["server_http"], description="The config type")


class CustomConfigNameModel(CustomConfigModel):
    name: str = Field(examples=["my_custom_config"], description="The config name")


class CustomConfigDataModel(CustomConfigNameModel):
    data: bytes = Field(
        examples=[b"BunkerWeb forever"],
        description="The custom config content in bytes",
    )
    checksum: str = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
        description="SHA512 checksum of the custom config file",
    )
