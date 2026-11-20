from typing import Literal

from models.ui.delete import DeleteBase


class DeleteInstance(DeleteBase):
    item: Literal["instance"] = "instance"
    hostname: str


__all__ = ("DeleteInstance",)
