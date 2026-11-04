"""Real Configurator validation for the lane-T5 regression tests.

A module of its own rather than ``conftest``: ``from conftest import …`` binds to whichever conftest
module pytest loaded last (see ``_listen_helpers.py``). ``tests/unit/gen`` is on ``sys.path`` through
its conftest, so this name is unambiguous.
"""

import logging
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"


def configured(**variables):
    """The config the generator keeps for ``variables``: a value the validation refuses is dropped, so its default shows."""
    from Configurator import Configurator  # type: ignore  (src/common/gen is on the path through the gen conftest)

    with tempfile.TemporaryDirectory() as root:
        plugins = Path(root, "plugins")
        pro_plugins = Path(root, "pro-plugins")
        plugins.mkdir()
        pro_plugins.mkdir()
        return Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("t5-configurator")).get_config(None)
