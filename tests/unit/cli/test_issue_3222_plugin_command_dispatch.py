"""``bwcli plugin <id> <command>`` ran the wrong command when the plugin command shadowed a built-in.

The plugin subparser stored the plugin's command name in the same argparse destination as the
top-level subcommand, so a plugin command called like a built-in (``bans``, ``unban``,
``plugin_list``...) replaced ``plugin`` as the dispatched command and ran the built-in instead.
The test goes through ``main.py`` and asserts which ``CLI`` method ran.

Refs: #3222.
"""

import os
import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/common/cli"))

import CLI as cli_module  # noqa: E402
import logger  # noqa: E402


@pytest.mark.parametrize("plugin_command", ["bans", "ban", "unban", "plugin_list", "plugin", "support"])
def test_plugin_command_named_like_a_builtin_runs_the_plugin_command(monkeypatch, plugin_command):
    instance = Mock()
    instance.custom.return_value = True, "done"
    monkeypatch.setattr(cli_module, "CLI", Mock(return_value=instance))
    monkeypatch.setattr(cli_module, "support_refusal", lambda: None)
    monkeypatch.setattr(logger, "getLogger", lambda _: Mock())
    monkeypatch.setattr(sys, "argv", ["bwcli", "plugin", "someplugin", plugin_command])
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(os, "_exit", sys.exit)

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(ROOT / "src/common/cli/main.py"), run_name="__main__")

    instance.custom.assert_called_once_with("someplugin", plugin_command, debug=False, extra_args=[])
    for builtin in ("bans", "ban", "unban", "plugin_list", "support"):
        getattr(instance, builtin).assert_not_called()
    assert raised.value.code == 0
