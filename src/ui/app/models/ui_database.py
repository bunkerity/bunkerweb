from logging import Logger
from os import sep
from os.path import join
from sys import path as sys_path
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore

from app.models.ui_db_methods.users import UIUsersMethodsMixin
from app.models.ui_db_methods.rbac import UIRBACMethodsMixin
from app.models.ui_db_methods.preferences import UIPreferencesMethodsMixin


class UIDatabase(UIUsersMethodsMixin, UIRBACMethodsMixin, UIPreferencesMethodsMixin, Database):
    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, external=True, pool=pool, log=log, **kwargs)
