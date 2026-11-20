"""The api_app lane: tests that import the API's ``app`` package, in an interpreter of their own.

`tests/unit/ui/conftest.py` says it plainly: *"Only the UI imports ``app`` (API tests recompose
without it), so ``import app`` resolves uniquely to ``src/ui/app``."* The whole unit suite depends on
that. `tests/unit/api/conftest.py` honours it by recomposing ``APIDatabase`` from
``src/api/app/models`` instead of importing the package -- which works only because the API's DB
mixins use **absolute** imports.

That trick does not generalise. ``src/api/app/auth/biscuit.py`` imports ``..config``, ``..utils`` and
``.common`` **relatively**, so it can only be imported as part of its package, with ``src/api`` on
the path as ``app``. In one interpreter with the UI's tests, whichever ``app`` is imported first
wins and the other silently gets the wrong module.

So this lane runs separately, and refuses to run any other way: `tests/unit/conftest.py` ignores
``api_app/`` unless ``BW_API_APP_LANE=1`` is set, which makes accidental collection impossible
rather than merely unlikely.

Its dependencies are pinned separately too (`tests/unit/api_app/requirements.txt`), so a runner that
never invokes this lane never installs them.
"""

import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

_ROOT = Path(__file__).resolve().parents[3]

# `src/api` first: it is what makes `app` the API's package here.
for _p in (_ROOT / "src" / "api", _ROOT / "src" / "common" / "utils", _ROOT / "src" / "common" / "db"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# app.config reads this at import; point it at an empty document rather than the image's copy.
if "SETTINGS_YAML_FILE" not in os.environ:
    _stub = NamedTemporaryFile("w", suffix=".yml", delete=False)  # noqa: SIM115 - must outlive import
    _stub.write("{}\n")
    _stub.close()
    os.environ["SETTINGS_YAML_FILE"] = _stub.name
