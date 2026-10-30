from logging import warning
from typing import Literal, Optional

from pydantic import field_validator

from .action import ActionBase, ActionData


class DatabaseData(ActionData):
    query: str
    result: Optional[str] = (
        None  # ? The expected result to be found in the output of the query (if None, the query will be executed but the result won't be checked)
    )

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if v:
            warning("The URL property is only a dummy value, it won't be used in the tests.")
        return v


class DatabaseBase(ActionBase, DatabaseData):
    type: Literal["database"] = "database"


class Database(DatabaseBase):
    Docker: Optional[DatabaseData] = None
    Linux: Optional[DatabaseData] = None
    Autoconf: Optional[DatabaseData] = None
    Kubernetes: Optional[DatabaseData] = None
    All_in_one: Optional[DatabaseData] = None


__all__ = ("Database",)
