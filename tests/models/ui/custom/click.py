from typing import Literal

from models.ui.custom import CustomBase


class Click(CustomBase):
    type: Literal["click"] = "click"


__all__ = ("Click",)
