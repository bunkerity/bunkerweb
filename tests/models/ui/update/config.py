from typing import Literal, Optional

from pydantic import field_validator, model_validator

from models.ui.update import UpdateBase


class UpdateConfig(UpdateBase):
    item: Literal["config"] = "config"
    name: str
    new_name: Optional[str] = None
    service: str = "global"
    new_service: Optional[str] = None
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
    new_config_type: Optional[
        Literal[
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
        ]
    ] = None
    content: str

    @field_validator("name")
    def check_name(cls, v: str):
        return v.removesuffix(".conf")

    @model_validator(mode="after")
    def check_fields(self):
        if self.new_name is None:
            self.new_name = self.name

        if self.new_service is None:
            self.new_service = self.service

        if self.new_config_type is None:
            self.new_config_type = self.config_type

        return self


__all__ = ("UpdateConfig",)
