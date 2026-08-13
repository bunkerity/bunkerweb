from typing import Dict, Literal, Optional

from pydantic import field_validator

from models.ui.read import ReadBase


class ReadGlobal_Config(ReadBase):
    item: Literal["global_config"] = "global_config"
    mode: Literal["advanced", "raw"] = "advanced"
    config: Dict[str, Optional[str]]

    @field_validator("config")
    def check_item(cls, v: Dict[str, Optional[str]]):
        return {key.upper(): value for key, value in v.items()}


__all__ = ("ReadGlobal_Config",)
