from typing import Literal

from models.ui.custom import CustomBase


class Find(CustomBase):
    type: Literal["find"] = "find"
    findable: bool = True


__all__ = ("Find",)
