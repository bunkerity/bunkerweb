"""certbot-auth.py / certbot-cleanup.py log the instance API reply without raising.

The hooks are scripts (hyphenated names, work at import time), so each test runs one with
``runpy`` against stubbed ``Database``/``logger``/``API`` modules and reads the logger calls.
"""

from pathlib import Path
from runpy import run_path
from sys import modules
from types import ModuleType
from unittest.mock import MagicMock

import pytest

_JOBS = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "jobs"
HOOKS = ("certbot-auth.py", "certbot-cleanup.py")


def _run_hook(name, monkeypatch, request_result):
    logger = MagicMock()
    api = MagicMock()
    api.endpoint = "http://bw:5000"
    api.request.return_value = request_result

    for mod_name, attr, value in (
        ("Database", "Database", MagicMock(return_value=MagicMock(get_instances=MagicMock(return_value=[{"hostname": "bw"}])))),
        ("logger", "getLogger", MagicMock(return_value=logger)),
        ("API", "API", MagicMock(from_instance=MagicMock(return_value=api))),
    ):
        stub = ModuleType(mod_name)
        setattr(stub, attr, value)
        monkeypatch.setitem(modules, mod_name, stub)

    with pytest.raises(SystemExit) as exc:
        run_path(str(_JOBS / name), run_name="__main__")
    return exc.value.code, logger


@pytest.mark.parametrize("hook", HOOKS)
@pytest.mark.parametrize(
    "body, expected",
    [
        ("<html>502 Bad Gateway</html>", "HTTP 502, body = '<html>502 Bad Gateway</html>'"),
        ("", "HTTP 502, body = ''"),
        (None, "HTTP 502, body = 'None'"),
        ({"status": "ko"}, "HTTP 502, status = ko, msg = None"),
        ({"status": "ko", "msg": "boom"}, "HTTP 502, status = ko, msg = boom"),
    ],
)
def test_error_reply_is_logged_not_raised(hook, body, expected, monkeypatch):
    code, logger = _run_hook(hook, monkeypatch, (True, None, 502, body))

    assert code == 1
    messages = [c.args[0] for c in logger.error.call_args_list]
    assert any(expected in m for m in messages), messages
    assert not any("Exception while running" in m for m in messages), messages


@pytest.mark.parametrize("hook", HOOKS)
def test_success_exits_zero(hook, monkeypatch):
    code, logger = _run_hook(hook, monkeypatch, (True, None, 200, {"status": "success"}))

    assert code == 0
    logger.error.assert_not_called()
