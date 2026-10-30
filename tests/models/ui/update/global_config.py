from typing import Dict, Literal, Optional

from pydantic import field_validator

from models.ui.update import UpdateBase


class UpdateGlobal_Config(UpdateBase):
    item: Literal["global_config"] = "global_config"
    # "compose" and "raw" are the two panes the settings page still has; easy and advanced
    # went away with the settings monolith (per-plugin editing moved to its own pages).
    mode: Literal["compose", "raw"] = "raw"
    config: Dict[str, Optional[str]]

    @field_validator("config")
    def check_config(cls, v: Dict[str, Optional[str]]):
        return {key.upper(): value for key, value in v.items()}


__all__ = ("UpdateGlobal_Config",)
