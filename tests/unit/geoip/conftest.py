"""Path setup for the GeoIP job-helper tests.

Adds ``src/common/core/geoip/jobs`` to ``sys.path`` so ``geoip_utils`` imports by its bare
module name (the job scripts run with that dir on the path at runtime). ``common_utils``
comes from ``src/common/utils``, already injected by the root conftest.

``geoip_utils`` imports ``maxminddb`` at module load, but only ``validate()`` uses it and
that needs a real ``.mmdb`` fixture we do not ship. A stub keeps the unit venv free of the
dependency; everything under test here (source resolution, unpacking, redaction) is pure.
"""

import sys
from pathlib import Path
from types import ModuleType


def _open_database_stub(*_args, **_kwargs):
    raise NotImplementedError("maxminddb is stubbed in the unit venv; validate() is not covered here")


if "maxminddb" not in sys.modules:
    _stub = ModuleType("maxminddb")
    setattr(_stub, "open_database", _open_database_stub)
    sys.modules["maxminddb"] = _stub

_JOBS = str(Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "geoip" / "jobs")
if _JOBS not in sys.path:
    sys.path.insert(0, _JOBS)
