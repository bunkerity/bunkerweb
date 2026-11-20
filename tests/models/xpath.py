from lxml.etree import XPath
from pydantic import field_validator
from typing import Literal, Optional

from .selenium_action import SeleniumActionBase, SeleniumActionData


class XpathData(SeleniumActionData):
    xpath: str
    current_url_contains: Optional[str] = None

    @field_validator("xpath")
    @classmethod
    def check_xpath(cls, v: str) -> str:
        XPath(v)
        return v


class XpathBase(SeleniumActionBase, XpathData):
    type: Literal["xpath"] = "xpath"


class Xpath(XpathBase):
    Docker: Optional[XpathData] = None
    Linux: Optional[XpathData] = None
    Autoconf: Optional[XpathData] = None
    Kubernetes: Optional[XpathData] = None
    All_in_one: Optional[XpathData] = None


__all__ = ("Xpath",)
