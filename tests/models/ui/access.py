from typing import Literal, Optional

from pydantic import model_validator

from models.ui.step_base import StepBase


class Access(StepBase):
    type: Literal["access"] = "access"
    page: Optional[
        Literal[
            "about",
            "bans",
            "cache",
            "configs",
            "global-config",
            "global-settings",
            "home",
            "instances",
            "jobs",
            "logs",
            "plugins",
            "pro",
            "profile",
            "reports",
            "services",
            "support",
            "templates",
        ]
    ] = None
    url: Optional[str] = None
    new_tab: bool = False

    @model_validator(mode="after")
    def check_fields(self):
        if not self.page and not self.url:
            raise ValueError("page or url must be set")

        return self


__all__ = ("Access",)
