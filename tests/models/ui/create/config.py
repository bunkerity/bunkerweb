from typing import Literal

from pydantic import field_validator

from models.ui.create import CreateBase


class CreateConfig(CreateBase):
    item: Literal["config"] = "config"
    service: str = "global"
    config_type: Literal[
        "http",
        "stream",
        "server_http",
        "server_stream",
        "default_server_http",
        "default_server_stream",
        "modsec",
        "modsec_crs",
        "crs_plugins_before",
        "crs_plugins_after",
    ] = "http"
    content: str

    @field_validator("name")
    def check_name(cls, v: str):
        return v.removesuffix(".conf")


__all__ = ("CreateConfig",)
