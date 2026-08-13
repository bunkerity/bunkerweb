from typing import Literal, Optional

from .action import ActionBase, ActionData


class UrlData(ActionData):
    url: str


class UrlBase(ActionBase, UrlData):
    type: Literal["url"] = "url"


class Url(UrlBase):
    Docker: Optional[UrlData] = None
    Linux: Optional[UrlData] = None
    Autoconf: Optional[UrlData] = None
    Kubernetes: Optional[UrlData] = None
    All_in_one: Optional[UrlData] = None


__all__ = ("Url",)
