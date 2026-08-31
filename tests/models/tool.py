from json import loads
from logging import warning
from pathlib import Path
from typing import Literal, Optional

from pydantic import field_validator, model_validator

from .action import ActionBase, ActionData, check_embedded_runner_urls


class ToolData(ActionData):
    tool: str
    arguments: Optional[str] = None
    result: Optional[str] = None
    success: bool = True

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if v:
            warning("The URL property is only a dummy value, it won't be used in the tests.")
        return v

    @field_validator("arguments")
    @classmethod
    def check_arguments(cls, v: Optional[str]) -> Optional[str]:
        # `tool` runs on the runner, so a URL embedded in its argv has to resolve there the same
        # way a `url` field does.
        if v:
            check_embedded_runner_urls(v)
        return v

    @model_validator(mode="after")
    def check_fields(self):
        tools = []
        tool_file = Path("tests", "utils", "tools.json")
        if tool_file.exists():
            tools = loads(tool_file.read_text())
        if self.tool not in tools:
            raise ValueError(f"Tool {self.tool} is not found in the tools.json file")

        # `timeout` is ActionData's own field (default 120s, the HTTP timeout elsewhere); for a
        # tool it bounds the process. Cutting a tool short discards whatever it would have printed
        # afterwards, which is only sound for a pure provocation -- one judged by what it provoked
        # in a LATER action rather than by its own output. A tool asserting on `result` must run to
        # completion, else the assertion is checked against a truncated stream and can pass or fail
        # for reasons that have nothing to do with the product. Only an explicitly set timeout is
        # refused; the inherited default is ignored for those, see tool_handler.
        if self.result and "timeout" in self.model_fields_set:
            raise ValueError("timeout cannot be combined with result: a tool asserting on its own output must run to completion")

        return self


class ToolBase(ActionBase, ToolData):
    type: Literal["tool"] = "tool"


class Tool(ToolBase):
    Docker: Optional[ToolData] = None
    Linux: Optional[ToolData] = None
    Autoconf: Optional[ToolData] = None
    Kubernetes: Optional[ToolData] = None
    All_in_one: Optional[ToolData] = None


__all__ = ("Tool",)
