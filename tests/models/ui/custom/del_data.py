from typing import Literal, Optional

from models.ui.custom import CustomBase


class Del_Data(CustomBase):
    type: Literal["del_data"] = "del_data"
    selector: Optional[str] = None
    key: str


__all__ = ("Del_Data",)
