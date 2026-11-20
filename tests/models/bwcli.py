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
    # ? The exit code the command is expected to return. Default 0, so every existing spec keeps
    # ? its meaning: "the command succeeded". A refusal is a documented outcome of some bwcli
    # ? subcommands, and without this the only way to assert one was to let the handler bail on a
    # ? non-zero code, which reports the deliberate refusal as a harness failure.
    # ?
    # ? Expect what BWCLI returns, not what the plugin script returns: the wrapper collapses every
    # ? non-zero code to 1 (src/common/cli/CLI.py:806-812 turns the SystemExit into a failure,
    # ? src/common/cli/main.py:112-113 exits 1). `plugin backup downgrade <newer version>` exits 3
    # ? inside downgrade_execute.py and reaches a spec as 1. Pair the code with `result:` -- alone
    # ? it only says "something failed".
    exit_code: int = 0

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
