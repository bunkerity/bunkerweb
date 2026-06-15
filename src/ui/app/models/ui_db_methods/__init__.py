#!/usr/bin/env python3
"""UI-specific domain mixin modules composing the UIDatabase class.

Each module holds one domain of UI-only Database methods (users, RBAC,
column preferences) as a mixin class; ui_database.py assembles them ahead of
the shared :class:`Database` so the UI overrides win in the MRO.

The mixins reuse the shared ``DatabaseMixinBase`` annotations from
``db_methods.common`` (TYPE_CHECKING-only declarations of ``_db_session``,
``readonly``, ``logger`` ...) and depend on the bundled SQLAlchemy/bcrypt
dependencies plus the ``model`` module — all resolved through the same
sys.path bootstrap ui_database.py uses, replicated below defensively so these
modules import no matter how the package was reached.
"""

from os import sep
from os.path import join as os_join
from sys import path as sys_path

# Mirror ui_database.py's bootstrap so `model`, the bundled dependencies, the
# shared utils and the base `db_methods` package resolve no matter how this
# package was reached.
for _path in [os_join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if _path not in sys_path:
        sys_path.append(_path)
