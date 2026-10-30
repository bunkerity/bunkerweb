from importlib import import_module
from os.path import dirname
from typing import Literal

from pydantic import field_validator

from ..utils import get_python_files
from .. import StepBase


class CustomBase(StepBase):
    type: str
    by: Literal["id", "xpath", "link text", "partial link text", "name", "tag name", "class name", "css selector", "js"] = "xpath"
    selector: str

    @field_validator("type")
    def check_type(cls, v):
        valid_types = get_python_files(dirname(__file__))
        if v not in valid_types:
            raise ValueError(f"Invalid type: {v}. Must be one of {valid_types}")
        return v


for item in get_python_files(dirname(__file__)):
    import_module(f".{item}", package=__package__)
