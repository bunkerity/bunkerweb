from typing import List, Literal, Optional

from pydantic import field_validator

from .action import ActionBase, ActionData


class ScriptData(ActionData):
    # ? argv, run from the deployed example's directory. Use this when the check needs
    # ? more than one request: protocol-level probes, multi-step flows, anything an
    # ? assertion type would only express awkwardly.
    script: List[str] = []
    result: Optional[str] = None  # ? If set, must appear in the script's output
    success: bool = True  # ? Whether the script is expected to exit 0

    @field_validator("script")
    @classmethod
    def check_script(cls, v: List[str]) -> List[str]:
        if not v or not all(isinstance(part, str) and part for part in v):
            raise ValueError("script must be a non-empty list of non-empty strings")
        return v


class ScriptBase(ActionBase, ScriptData):
    type: Literal["script"] = "script"


class Script(ScriptBase):
    Docker: Optional[ScriptData] = None
    Linux: Optional[ScriptData] = None
    Autoconf: Optional[ScriptData] = None
    Kubernetes: Optional[ScriptData] = None
    All_in_one: Optional[ScriptData] = None


__all__ = ("Script",)
