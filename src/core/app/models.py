from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from API import API  # type: ignore


class Instance(BaseModel):
    hostname: str = Field(examples=["bunkerweb-1"])
    port: int = Field(examples=[5000])
    server_name: str = Field(examples=["bwapi"])

    def to_api(self) -> API:
        return API(
            f"http://{self.hostname}:{self.port}",
            self.server_name,
        )


class InstanceWithMethod(Instance):
    method: str = Field(examples=["static"])


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
    last_update: Optional[float] = Field(None, examples=["1609459200.0"])
    checksum: Optional[str] = Field(
        None,
        examples=[
            "b935addf904d374ad57b7985e821d6bab74ee1c18757479b33b855622ab78290ddb00b39be41e60df41bf4502b9c8796e975c2177e8000f068a5a4d6d9acac3d"
        ],
    )
    data: Optional[bytes] = Field(None, examples=[b"BunkerWeb forever"])


class ErrorMessage(BaseModel):
    message: str


class CacheFileModel(BaseModel):
    service_id: Optional[str] = None


class CacheFileDataModel(CacheFileModel):
    with_info: bool = False
    with_data: bool = True


class CacheFileInfoModel(CacheFileModel):
    last_update: Union[datetime, float]
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
