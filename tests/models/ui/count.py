from typing import Literal, Optional

from models.ui.step_base import StepBase


class Count(StepBase):
    type: Literal["count"] = "count"
    by: Literal["id", "xpath", "name", "css selector"] = "xpath"
    selector: str
    # Save the number of matching elements under this key ...
    key: Optional[str] = None
    # ... or require more matches than the number saved under this key, refreshing the page until it holds
    greater_than: Optional[str] = None
    timeout: float = 180.0


__all__ = ("Count",)
