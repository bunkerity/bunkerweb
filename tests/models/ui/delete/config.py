from typing import Literal

from pydantic import field_validator

from models.ui.delete import DeleteBase


class DeleteConfig(DeleteBase):
    item: Literal["config"] = "config"
    name: str

    @field_validator("name")
    def check_name(cls, v: str):
        return v.removesuffix(".conf")


__all__ = ("DeleteConfig",)
