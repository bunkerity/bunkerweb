from pydantic import field_validator
from typing import Literal, Optional

from .action import ActionBase, ActionData


class StatusData(ActionData):
    status: Optional[int] = None  # ? If status is None, then the request must fail

    @field_validator("status")
    @classmethod
    def check_status(cls, v: int) -> int:
        if v is not None and (v < 100 or v > 599):
            raise ValueError("Status code must be between 100 and 599")
        return v


class StatusBase(ActionBase, StatusData):
    type: Literal["status"] = "status"


class Status(StatusBase):
    Docker: Optional[StatusData] = None
    Linux: Optional[StatusData] = None
    Autoconf: Optional[StatusData] = None
    Kubernetes: Optional[StatusData] = None
    All_in_one: Optional[StatusData] = None


__all__ = ("Status",)
