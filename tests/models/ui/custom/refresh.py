from typing import Literal, Optional

from models.ui.custom import CustomBase


class Refresh(CustomBase):
    type: Literal["refresh"] = "refresh"
    selector: Optional[str] = None


__all__ = ("Refresh",)
