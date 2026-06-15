"""Path setup for scheduler tests — adds ``src/scheduler`` so ``JobScheduler`` imports.

``JobScheduler`` needs the ``schedule`` package and ``logger`` (the latter already on the
path via the root conftest). We only import ``JobScheduler``; ``main`` is left untouched
(its top-level name would otherwise clash with ``src/api/app/main.py``).
"""

import sys
from pathlib import Path

_SCHED = str(Path(__file__).resolve().parents[3] / "src" / "scheduler")
if _SCHED not in sys.path:
    sys.path.insert(0, _SCHED)
