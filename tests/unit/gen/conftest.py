"""Path setup for config-generation tests.

Adds ``src/common/gen`` so ``Configurator`` imports. ``common_utils`` (its only
non-stdlib dependency) is already on the path via the root conftest. We deliberately
do NOT rely on ``import utils`` here — ``src/common/gen/utils.py`` and
``src/api/app/utils.py`` would both be top-level ``utils`` in a combined run, so the
``has_permissions`` test loads that module by file path instead.
"""

import sys
from pathlib import Path

_GEN = str(Path(__file__).resolve().parents[3] / "src" / "common" / "gen")
if _GEN not in sys.path:
    sys.path.insert(0, _GEN)
