from logging import Logger
from os import sep
from os.path import join
from sys import path as sys_path
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

"""
APIDatabase: API-specific user accessors respecting API models.

Note: Method signatures keep UI-compatible parameters for callers,
but only API model fields are used/stored.
"""

from Database import Database  # type: ignore

from .api_db_methods.users import APIUsersMethodsMixin
from .api_db_methods.permissions import APIPermissionsMethodsMixin


class APIDatabase(APIUsersMethodsMixin, APIPermissionsMethodsMixin, Database):
    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, external=True, pool=pool, log=log, **kwargs)
