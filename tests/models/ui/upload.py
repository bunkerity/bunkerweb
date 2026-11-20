from typing import Literal

from models.ui.step_base import StepBase


class Upload(StepBase):
    type: Literal["upload"] = "upload"
    by: Literal["id", "xpath", "name", "css selector"] = "xpath"
    selector: str
    # File, or directory zipped on the fly, relative to the repository root
    path: str


__all__ = ("Upload",)
