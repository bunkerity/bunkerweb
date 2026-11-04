from typing import Literal, Optional

from pydantic import model_validator

from models.ui.custom import CustomBase


class Save_Data(CustomBase):
    type: Literal["save_data"] = "save_data"
    key: str
    attribute: Optional[str] = None
    text: bool = False

    @model_validator(mode="after")
    def check_fields(self):
        if not self.text and not self.attribute:
            raise ValueError("text or attribute must be set")

        return self


__all__ = ("Save_Data",)
