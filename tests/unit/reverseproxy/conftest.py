"""Path setup for the reverse proxy job-helper tests.

Adds ``src/common/core/reverseproxy/jobs`` to ``sys.path`` so ``reverseproxy_pem`` imports by
its bare module name, exactly as the job scripts do at runtime. ``logger`` comes from
``src/common/utils``, already injected by the root conftest.
"""

import sys
from pathlib import Path

_JOBS = str(Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "reverseproxy" / "jobs")
if _JOBS not in sys.path:
    sys.path.insert(0, _JOBS)
