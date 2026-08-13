from typing import Dict, Literal, Optional

from pydantic import field_validator

from models.ui.update import UpdateBase


class UpdateService(UpdateBase):
    item: Literal["service"] = "service"
    name: str
    mode: Literal["easy", "advanced", "raw"] = "advanced"
    template: Literal["low", "medium", "high"] = "low"
    draft: bool = False
    config: Dict[str, Optional[str]]

    @field_validator("name")
    def check_name(cls, v: str):
        return v.lower()

    @field_validator("config")
    def check_config(cls, v: Dict[str, Optional[str]]):
        return {key.upper(): value for key, value in v.items()}


__all__ = ("UpdateService",)
