from typing import Dict, Literal, Optional

from models.ui.step_base import StepBase


class Fetch(StepBase):
    type: Literal["fetch"] = "fetch"
    url: str
    method: Literal["GET", "POST"] = "GET"
    headers: Dict[str, str] = {}
    # Requests sent one after the other from the current page, so the cookies and the origin are the browser's
    count: int = 1
    # Status every response must carry, when set
    status: Optional[int] = None


__all__ = ("Fetch",)
