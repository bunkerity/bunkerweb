"""Path setup for Let's Encrypt provider-translation tests.

Adds ``src/common/core/letsencrypt/jobs`` to ``sys.path`` so ``letsencrypt_providers`` and
``letsencrypt_utils`` import by their bare module names (the job scripts run with that dir on
the path at runtime). ``common_utils`` and ``letsencrypt_consistency`` come from
``src/common/utils``, already injected by the root conftest. certbot itself is not imported at
module load, so these tests need no certbot in the unit venv.
"""

import sys
from pathlib import Path

_JOBS = str(Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "jobs")
if _JOBS not in sys.path:
    sys.path.insert(0, _JOBS)
