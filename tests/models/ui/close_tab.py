from typing import Literal, Optional

from models.ui.step_base import StepBase


class Close_Tab(StepBase):
    type: Literal["close_tab"] = "close_tab"
    tab: Optional[int] = None


__all__ = ("Close_Tab",)
