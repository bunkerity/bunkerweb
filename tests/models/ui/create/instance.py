from typing import Literal

from models.ui.create import CreateBase


class CreateInstance(CreateBase):
    item: Literal["instance"] = "instance"
    hostname: str
    name: str = "My Bunker"


__all__ = ("CreateInstance",)
