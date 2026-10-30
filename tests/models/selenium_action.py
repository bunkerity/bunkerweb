from pydantic import field_validator
from typing import Literal, Optional

from .action import ActionBase, ActionData


class SeleniumActionData(ActionData):
    # Override the default values
    method: Literal["GET"] = "GET"
    auth: None = None
    body: None = None
    body_length: Literal[0] = 0
    follow_redirects: Literal[True] = True
    http2: Literal[False] = False
    raise_for_status: Literal[False] = False

    # New fields
    clear_cookies: bool = True

    @field_validator("headers", check_fields=False)
    @classmethod
    def check_headers(cls, v: str) -> str:
        if v:
            raise ValueError("headers are not allowed as this is a Selenium action")
        return v


class SeleniumActionBase(ActionBase, SeleniumActionData):
    type: str


class SeleniumAction(SeleniumActionBase):
    Docker: Optional[SeleniumActionData] = None
    Linux: Optional[SeleniumActionData] = None
    Autoconf: Optional[SeleniumActionData] = None
    Kubernetes: Optional[SeleniumActionData] = None
    All_in_one: Optional[SeleniumActionData] = None
