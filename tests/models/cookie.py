from pydantic import field_validator, model_validator
from re import match
from typing import Literal, Optional

from .selenium_action import SeleniumActionBase, SeleniumActionData


class CookieData(SeleniumActionData):
    cookie_name: str
    cookie_rx: Optional[str] = None  # ? If cookie_rx is None, then the cookie must not be present
    cookie_secure_flag: bool = False
    cookie_http_only_flag: bool = False
    cookie_same_site_flag: Optional[Literal["Strict", "Lax"]] = None

    @model_validator(mode="after")
    def check_fields(self):
        if self.url.startswith("http://") and self.cookie_secure_flag:
            raise ValueError("cookie_secure_flag must be False if the URL is not HTTPS")
        return self

    @field_validator("cookie_name")
    @classmethod
    def check_cookie_name(cls, v: str) -> str:
        if not match(r"^[\w+]+$", v):
            raise ValueError("cookie_name must be a valid HTTP cookie")
        return v

    @field_validator("cookie_rx")
    @classmethod
    def check_cookie_rx(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            match(v, "")
        return v


class CookieBase(SeleniumActionBase, CookieData):
    type: Literal["cookie"] = "cookie"


class Cookie(CookieBase):
    Docker: Optional[CookieData] = None
    Linux: Optional[CookieData] = None
    Autoconf: Optional[CookieData] = None
    Kubernetes: Optional[CookieData] = None
    All_in_one: Optional[CookieData] = None


__all__ = ("Cookie",)
