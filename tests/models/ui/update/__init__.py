from importlib import import_module
from os.path import dirname
from typing import Literal

from pydantic import field_validator

from ..utils import get_python_files
from .. import CrudBase


class UpdateBase(CrudBase):
    type: Literal["update"] = "update"
    item: str

    @field_validator("item")
    def check_item(cls, v):
        valid_items = get_python_files(dirname(__file__))
        if v not in valid_items:
            raise ValueError(f"Invalid item: {v}. Must be one of {valid_items}")
        return v


for item in get_python_files(dirname(__file__)):
    import_module(f".{item}", package=__package__)
