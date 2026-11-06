from pydantic import field_validator, model_validator
from typing import Literal, Optional, Set

from .action import ActionBase, ActionData


class StatusData(ActionData):
    status: Optional[int] = None
    expect_error: Set[Literal["connection_refused", "connection_closed", "tls_verify"]] = set()

    @model_validator(mode="after")
    def check_expectation(self):
        if (self.status is None) == (not self.expect_error):
            raise ValueError("Set either status or a nonempty expect_error, not both")
        return self

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
