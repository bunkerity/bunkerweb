"""Renaming the admin user through ADMIN_USERNAME applies at startup.

The startup hook changed the username it was about to store and then updated the row without naming the old one, so the
database looked for the new name, found nothing, and logged an error: the old credential stayed live. Runs the real
``on_starting`` over a real ``UIDatabase`` with only the filesystem, the network and the plugin reload replaced.
"""

import logging
import runpy
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
from bcrypt import gensalt, hashpw

PASSWORD = "Correct-Horse1!"
CONF = Path(__file__).resolve().parents[3] / "src/ui/utils/gunicorn.conf.py"


@pytest.fixture
def start(ui_db, tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    # app.dependencies would build a real database at import time
    deps = ModuleType("app.dependencies")
    deps.reload_plugins = Mock()
    monkeypatch.setitem(sys.modules, "app.dependencies", deps)
    for name in ("CUSTOM_LOG_LEVEL", "LOG_LEVEL", "CAPTURE_OUTPUT", "LOG_FILE_PATH", "DEBUG", "ADMIN_USERNAME", "ADMIN_PASSWORD", "OVERRIDE_ADMIN_CREDS"):
        monkeypatch.delenv(name, raising=False)

    class Wrapped:
        """The test database, kept open when the hook closes its handle before forking, and already initialized."""

        def close(self):
            pass

        def get_metadata(self):
            return {"is_initialized": True}

        def __getattr__(self, attr):
            return getattr(ui_db, attr)

    Database = lambda *_args, **_kwargs: Wrapped()  # noqa: E731

    def run(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        namespace = runpy.run_path(str(CONF))
        hook = namespace["on_starting"]
        paths = {name: tmp_path / name for name in ("TMP_DIR", "TMP_UI_DIR", "RUN_DIR", "LIB_DIR", "UI_WORKER_TMP_DIR")}
        paths.update(
            ERROR_FILE=paths["TMP_DIR"] / "ui.error",
            UI_DATA_FILE=paths["TMP_DIR"] / "ui_data.json",
            UI_SESSIONS_CACHE=paths["LIB_DIR"] / "sessions",
            TMP_PID_FILE=paths["RUN_DIR"] / "tmp-ui.pid",
            FLASK_SECRET_FILE=paths["LIB_DIR"] / ".flask_secret",
            FLASK_SECRET_HASH_FILE=paths["LIB_DIR"] / ".flask_secret.hash",
            TOTP_ENCRYPTION_KEYS_FILE=paths["LIB_DIR"] / ".totp_keys.json",
            TOTP_ENCRYPTION_HASH_FILE=paths["LIB_DIR"] / ".totp_keys.hash",
            TOTP_SECRETS_FILE=paths["LIB_DIR"] / ".totp_secrets.json",
            TOTP_HASH_FILE=paths["LIB_DIR"] / ".totp_secrets.hash",
            BISCUIT_PUBLIC_KEY_FILE=paths["LIB_DIR"] / "biscuit.pub",
            BISCUIT_PRIVATE_KEY_FILE=paths["LIB_DIR"] / "biscuit.key",
            BISCUIT_PUBLIC_KEY_HASH_FILE=paths["LIB_DIR"] / "biscuit.pub.hash",
            BISCUIT_PRIVATE_KEY_HASH_FILE=paths["LIB_DIR"] / "biscuit.key.hash",
        )
        # run_path returns a copy; the hook keeps the original globals mapping
        hook.__globals__.update(
            paths,
            UIDatabase=Database,
            worker_tmp_dir="/missing-shm",
            handle_docker_secrets=lambda: {},
            get_latest_stable_release=lambda: "unknown",
        )
        with caplog.at_level(logging.INFO):
            hook(None)

    return run


def test_a_rename_through_the_environment_updates_the_stored_user(ui_db, start, caplog):
    assert ui_db.create_ui_user("admin", hashpw(PASSWORD.encode(), gensalt(rounds=4)), [], admin=True, method="manual") == ""

    start(ADMIN_USERNAME="root2")

    assert "Couldn't update the admin user" not in caplog.text
    assert ui_db.get_ui_user(username="admin") is None
    renamed = ui_db.get_ui_user(username="root2")
    assert renamed is not None and renamed.check_password(PASSWORD)
