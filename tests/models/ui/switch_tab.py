from typing import Literal

from models.ui.step_base import StepBase


class Switch_Tab(StepBase):
    type: Literal["switch_tab"] = "switch_tab"
    tab: int


__all__ = ("Switch_Tab",)
