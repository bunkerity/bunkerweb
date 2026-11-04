from typing import Literal

from models.ui.custom import CustomBase


class Send_Keys(CustomBase):
    type: Literal["send_keys"] = "send_keys"
    value: str
    clear: bool = False


__all__ = ("Send_Keys",)
