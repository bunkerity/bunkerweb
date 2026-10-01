"""QA-UI-6 Q6-H1: a flash written by a background save task is in the language of the request.

Every save queues its work on `CONFIG_TASKS_EXECUTOR` and returns. The task then runs outside the
request, so `translated()` found no app context, returned None, and the English fallback was
flashed in every locale. The executor now carries the request's app and locale into the task.

This runs the real `update_global_config` (refused-only path) through the real executor class from
inside a French request, then reads the flash it queued.
"""

import sys
from json import loads
from pathlib import Path
from unittest.mock import patch

from flask import Flask, session

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import LocaleThreadPoolExecutor, init_i18n  # noqa: E402
from app.models.config import Config  # noqa: E402

from test_global_settings_save_flash_type import MODULE, SETTINGS, _FakeData, _stored_config  # noqa: E402

KEY = "global_settings.flash.global_settings_not_saved_every_changed"


def _catalog_value(language: str, key: str) -> str:
    node = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / f"{language}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


def _app() -> Flask:
    application = Flask("bw_ui_task_locale_test", root_path=str(REPO / "src" / "ui"))
    application.config["SECRET_KEY"] = "test"
    init_i18n(application)
    return application


def _run_refused_only_save(language: str) -> list:
    data = _FakeData(TO_FLASH=[])
    config = Config.__new__(Config)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: _stored_config()
    config.edit_global_conf = lambda variables, **kwargs: ("", 0)

    executor = LocaleThreadPoolExecutor(max_workers=1)
    app = _app()
    try:
        with patch.object(MODULE, "BW_CONFIG", config), patch.object(MODULE, "DATA", data), patch.object(MODULE, "wait_applying", lambda: None):
            with app.test_request_context("/global-settings", method="POST"):
                session["language"] = language
                future = executor.submit(MODULE.update_global_config, {"WORKER_CONNECTIONS": "abc", "SSL_PROTOCOLS": "TLSv1.2 TLSv1.3"}, False, {}, scope=None)
            future.result(timeout=10)  # after the request is gone, as in production
    finally:
        executor.shutdown(wait=True)
    return [entry["content"] for entry in data["TO_FLASH"]]


def test_a_task_queued_from_a_french_request_flashes_in_french():
    flashed = _run_refused_only_save("fr")

    assert _catalog_value("fr", KEY) in flashed, flashed
    assert _catalog_value("en", KEY) not in flashed, flashed


def test_a_task_queued_from_a_german_request_flashes_in_german():
    assert _catalog_value("de", KEY) in _run_refused_only_save("de")


def test_the_real_ui_executor_carries_the_locale():
    """The choke point itself: every route submits to `app.dependencies.CONFIG_TASKS_EXECUTOR`."""
    source = (REPO / "src" / "ui" / "app" / "dependencies.py").read_text(encoding="utf-8")
    assert "CONFIG_TASKS_EXECUTOR = LocaleThreadPoolExecutor(" in source


def test_a_submit_outside_a_request_still_runs():
    executor = LocaleThreadPoolExecutor(max_workers=1)
    try:
        assert executor.submit(lambda value: value * 2, 21).result(timeout=10) == 42
    finally:
        executor.shutdown(wait=True)
