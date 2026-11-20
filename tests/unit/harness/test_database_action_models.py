"""UI database steps must not replace the core database action exported to the runners."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_core_and_ui_database_actions_keep_their_own_models():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.util
import logging
import sys
from types import SimpleNamespace

sys.path.insert(0, "tests")
# XPath validation is unrelated and lxml is not installed in the unit-test environment.
sys.modules["models.xpath"] = SimpleNamespace(Xpath=object)
import models
from models.database import Database as CoreDatabase
from models.ui.database import Database as UiDatabase

spec = importlib.util.spec_from_file_location("action_parser", "tests/utils/action.py")
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)

assert models.Database is CoreDatabase
assert models.ui.Database is UiDatabase
action = parser.parse_action(logging.getLogger(__name__), ["Docker"], "Docker", "sqlite",
                             {"type": "database", "query": "SELECT 1", "result": "1"})
assert isinstance(action, CoreDatabase)
assert "Docker" in action.integrations
assert action.database == "sqlite"
assert action.query == "SELECT 1" and action.result == "1"
step = models.ui.Database(query="SELECT 2", result="2")
assert isinstance(step, UiDatabase)
assert step.query == "SELECT 2" and step.result == "2"
""",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
