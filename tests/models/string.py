from typing import Literal, Optional

from pydantic import model_validator

from .action import ActionBase, ActionData


class StringData(ActionData):
    string: Optional[str] = None  # ? If string is found, then the request must pass
    not_string: Optional[str] = None  # ? If not_string is found, then the request must fail
    # ? Match without regard to case. Scenarios migrated from the legacy example harness
    # ? set this, because that harness casefolded both sides of the comparison.
    ignore_case: bool = False

    @model_validator(mode="after")
    def check_fields(self):
        if not (self.string or self.not_string):
            raise ValueError("Either string or not_string must be set")
        return self


class StringBase(ActionBase, StringData):
    type: Literal["string"] = "string"


class String(StringBase):
    Docker: Optional[StringData] = None
    Linux: Optional[StringData] = None
    Autoconf: Optional[StringData] = None
    Kubernetes: Optional[StringData] = None
    All_in_one: Optional[StringData] = None


__all__ = ("String",)
