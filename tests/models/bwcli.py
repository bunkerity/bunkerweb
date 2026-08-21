from logging import warning
from typing import Literal, Optional

from pydantic import field_validator, model_validator

from .action import ActionBase, ActionData


class BwcliData(ActionData):
    command: str
    result: Optional[str] = None  # ? The expected result to be found in the output of the command
    # ? The result that must NOT be in the output. Mirrors `string` / `not_string` on the http
    # ? actions, and exists for the same reason: asserting that a command reported success proves
    # ? only that it printed a message. `unban` saying "has been unbanned" is not evidence the row
    # ? is gone -- that needs a follow-up `bans` whose output no longer carries the address.
    not_result: Optional[str] = None

    @model_validator(mode="after")
    def check_result_fields(self):
        if not (self.result or self.not_result):
            raise ValueError("Either result or not_result must be set")
        return self

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
