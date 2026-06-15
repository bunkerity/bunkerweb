#!/usr/bin/env python3
"""Domain mixin modules composing the APIDatabase class.

Each module holds one domain of APIDatabase methods (users, permissions) as a
mixin class; api_database.py assembles them on top of the shared Database core.

This package mirrors api_database.py's sys.path bootstrap so that `model`,
`Database`, the bundled dependencies and the shared utils resolve no matter how
this package was reached. The package __init__ runs before its submodules, so
the bootstrap is in place by the time the mixin modules execute their imports.
"""

from os import sep
from os.path import join
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)
