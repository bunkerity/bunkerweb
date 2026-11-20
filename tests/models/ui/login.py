from typing import Literal

from models.ui.step_base import StepBase


class Login(StepBase):
    type: Literal["login"] = "login"
    next_page: str = "home"
    username: str
    password: str
    remember: bool = False
    totp_secret: str = ""
    totp_code: str = ""
    login_success: bool = True
    totp_success: bool = True


__all__ = ("Login",)
