from typing import Literal

from pydantic import field_validator

from models.ui.delete import DeleteBase


class DeleteService(DeleteBase):
    item: Literal["service"] = "service"
    name: str

    @field_validator("name")
    def check_name(cls, v: str):
        return v.lower()


__all__ = ("DeleteService",)
