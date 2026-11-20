from typing import Literal, Optional

from models.ui.step_base import StepBase


class Database(StepBase):
    type: Literal["database"] = "database"
    # Run against the stack's own database (the action's `database` key picks the engine)
    query: str
    # Must appear in the query output, when set
    result: Optional[str] = None


__all__ = ("Database",)
