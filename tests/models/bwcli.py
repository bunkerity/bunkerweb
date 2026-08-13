from logging import warning
from typing import Literal, Optional

from pydantic import field_validator

from .action import ActionBase, ActionData


class BwcliData(ActionData):
    command: str
    result: str  # ? The expected result to be found in the output of the command

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if v:
            warning("The URL property is only a dummy value, it won't be used in the tests.")
        return v


class BwcliBase(ActionBase, BwcliData):
    type: Literal["bwcli"] = "bwcli"


class Bwcli(BwcliBase):
    Docker: Optional[BwcliData] = None
    Linux: Optional[BwcliData] = None
    Autoconf: Optional[BwcliData] = None
    Kubernetes: Optional[BwcliData] = None
    All_in_one: Optional[BwcliData] = None


__all__ = ("Bwcli",)
