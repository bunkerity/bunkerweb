#!/usr/bin/env python3
"""Domain mixin modules composing the BunkerWeb Database class.

Each module holds one domain of Database methods (config, plugins, jobs,
instances, templates, ...) as a mixin class; Database.py assembles them.
Shared infrastructure (retry decorator, lock, engine event hooks, pool
defaults) lives in db_methods.common.
"""

from os import sep
from os.path import dirname, join as os_join
from sys import path as sys_path

# Mirror Database.py's bootstrap so `model`, the bundled dependencies and the
# shared utils resolve no matter how this package was reached.
for _path in (
    dirname(dirname(__file__)),
    os_join(sep, "usr", "share", "bunkerweb", "deps", "python"),
    os_join(sep, "usr", "share", "bunkerweb", "utils"),
):
    if _path not in sys_path:
        sys_path.append(_path)
