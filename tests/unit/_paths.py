"""Single source of truth for the ``src`` directories the unit tests import from.

``src/common/db/`` is NOT a Python package — its modules use bare imports such as
``from model import ...`` and ``from db_methods.common import ...`` — so it must sit
directly on ``sys.path`` (and ahead of the empty ``src/deps/python`` so it can never
shadow the venv-installed sqlalchemy/pymysql). ``conftest.py`` calls :func:`inject`
before anything imports ``Database``/``model``.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMON_DB = REPO_ROOT / "src" / "common" / "db"
COMMON_UTILS = REPO_ROOT / "src" / "common" / "utils"
COMMON_API = REPO_ROOT / "src" / "common" / "api"
API_APP = REPO_ROOT / "src" / "api"  # exposes top-level ``app`` (api) — see conftest note
UI_APP = REPO_ROOT / "src" / "ui"  # exposes top-level ``app`` (ui) — mutually exclusive with API_APP

# Everything the common Database layer (Database, model, db_methods) needs to import.
DB_LAYER_PATHS = [COMMON_DB, COMMON_UTILS, COMMON_API]


def inject(paths) -> None:
    """Prepend ``paths`` to ``sys.path`` (idempotent), preserving their given order
    so the first entry ends up first on the path."""
    for raw in reversed([str(p) for p in paths]):
        if raw in sys.path:
            sys.path.remove(raw)
        sys.path.insert(0, raw)
