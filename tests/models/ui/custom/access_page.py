from typing import Literal

from models.ui.custom import CustomBase


class Access_Page(CustomBase):
    type: Literal["access_page"] = "access_page"
    by: Literal["xpath"] = "xpath"
    page: str


__all__ = ("Access_Page",)
