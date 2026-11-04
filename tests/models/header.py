from pydantic import field_validator
from re import match
from typing import Dict, Literal, Optional

from .action import ActionBase, ActionData


class HeaderData(ActionData):
    response_headers: Dict[str, Optional[str]]  # ? If the value is None, then the header must not be present

    @field_validator("response_headers")
    @classmethod
    def check_response_headers(cls, v: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
        for header, value in v.items():
            if not match(r"^[\w-]+$", header):
                raise ValueError("header_name must be a valid HTTP header")
            if value is not None:
                match(value, "")
        return v


class HeaderBase(ActionBase, HeaderData):
    type: Literal["header"] = "header"


class Header(HeaderBase):
    Docker: Optional[HeaderData] = None
    Linux: Optional[HeaderData] = None
    Autoconf: Optional[HeaderData] = None
    Kubernetes: Optional[HeaderData] = None
    All_in_one: Optional[HeaderData] = None


__all__ = ("Header",)
