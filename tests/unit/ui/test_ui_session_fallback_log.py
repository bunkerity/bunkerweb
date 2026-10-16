"""The "Redis unavailable" warning is for a Redis that fails, not for `UI_USE_REDIS=no`.

`src/ui/main.py` picks the session backend at boot. When there is no Redis client it logs a WARNING
that Redis is configured but unavailable, because that worker is now pinned to file sessions. An
operator who set `UI_USE_REDIS=no` chose the filesystem on purpose: the warning is wrong for them
(and so is the `USE_REDIS` lookup that feeds it), so that case logs one INFO line instead.

The statement is lifted out of `main.py` by AST and run here, since importing `main` boots the UI.
"""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MAIN = Path(__file__).resolve().parents[3] / "src/ui/main.py"


def _run_backend_choice(use_redis_setting):
    """Run the `if redis_client: ... else: ...` that sets SESSION_TYPE, with no Redis client."""
    tree = ast.parse(MAIN.read_text())
    # The names main.py takes from common_utils come from its own import lines, so a missing import fails here too.
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "common_utils"]
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Name)
        and n.test.id == "redis_client"
        and any("Using FileSystemCache" in ast.unparse(s) for s in n.orelse)
    )
    logger = Mock()
    bw_config = Mock()
    bw_config.get_config.return_value = {"USE_REDIS": use_redis_setting}
    app = SimpleNamespace(config={})
    namespace = dict(app=app, redis_client=None, LOGGER=logger, BW_CONFIG=bw_config, getenv=os.getenv)
    exec(compile(ast.Module(body=[*imports, node], type_ignores=[]), str(MAIN), "exec"), namespace)
    return logger, bw_config, app


@pytest.mark.parametrize("value", ["no", "NO", "false", "0"])
def test_opt_out_logs_no_warning_and_one_info_line(monkeypatch, value):
    monkeypatch.setenv("UI_USE_REDIS", value)

    logger, bw_config, app = _run_backend_choice("yes")

    logger.warning.assert_not_called()
    logger.info.assert_called_once()
    assert "filesystem" in logger.info.call_args.args[0]
    assert app.config["SESSION_TYPE"] == "cachelib"
    bw_config.get_config.assert_not_called()


@pytest.mark.parametrize("value", [None, "yes", "true"])
def test_a_redis_that_is_configured_but_down_still_warns(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("UI_USE_REDIS", raising=False)
    else:
        monkeypatch.setenv("UI_USE_REDIS", value)

    logger, _, app = _run_backend_choice("yes")

    logger.warning.assert_called_once()
    assert "unavailable" in logger.warning.call_args.args[0]
    logger.info.assert_not_called()
    assert app.config["SESSION_TYPE"] == "cachelib"


def test_redis_not_configured_logs_neither(monkeypatch):
    monkeypatch.delenv("UI_USE_REDIS", raising=False)

    logger, *_ = _run_backend_choice("no")

    logger.warning.assert_not_called()
    logger.info.assert_not_called()
