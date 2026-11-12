"""An admin renamed or rotated through the environment is applied by the API's gunicorn startup hook.

``on_starting`` changed ``API_USER["username"]`` in memory and then called
``update_api_user(new_name, password)`` without the name it had to find the row by, so the lookup
used the new name, answered ``User <new> doesn't exist`` and only logged an error: the old
credential stayed the only one that worked. The real hook runs here against a real database, with
the bootstrap that does not matter to the rename (key files, ACL cache, imports) pointed away.
"""

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from bcrypt import checkpw, gensalt, hashpw

ROOT = Path(__file__).resolve().parents[3]

OLD_PASSWORD = "0ld-P@ssw0rd!"
NEW_PASSWORD = "N3w-P@ssw0rd!"


class _Keys:
    """The key-pair classes of ``biscuit_auth``, which the hook only needs to accept a loaded key."""

    def __init__(self, *args):
        pass


@pytest.fixture
def hook(monkeypatch, tmp_path, api_db):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("app.models.api_database", "app.utils", "app", "app.models", "biscuit_auth"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    logger = MagicMock()
    logger.log_types = {}
    monkeypatch.setitem(sys.modules, "logger", logger)
    for name in ("API_USERNAME", "API_PASSWORD", "OVERRIDE_API_CREDS", "DEBUG", "API_ACL_BOOTSTRAP_FILE"):
        monkeypatch.delenv(name, raising=False)

    namespace = runpy.run_path(str(ROOT / "src" / "api" / "utils" / "gunicorn.conf.py"))
    scope = namespace["on_starting"].__globals__

    for name in ("TMP_DIR", "TMP_UI_DIR", "RUN_DIR", "LIB_DIR", "API_WORKER_TMP_DIR"):
        scope[name] = tmp_path / name
    scope["worker_tmp_dir"] = (tmp_path / "API_WORKER_TMP_DIR").as_posix()
    scope["SHM_TMP_DIR"] = tmp_path / "shm"
    scope["API_ACL_FILE"] = tmp_path / "api_acl.json"
    scope["BISCUIT_PUBLIC_KEY_FILE"] = tmp_path / "public"
    scope["BISCUIT_PRIVATE_KEY_FILE"] = tmp_path / "private"
    scope["BISCUIT_PUBLIC_KEY_HASH_FILE"] = tmp_path / "public.hash"
    scope["BISCUIT_PRIVATE_KEY_HASH_FILE"] = tmp_path / "private.hash"
    scope["PublicKey"] = scope["PrivateKey"] = _Keys
    scope["handle_docker_secrets"] = lambda: {}
    scope["APIDatabase"] = lambda *args, **kwargs: api_db
    scope["gen_password_hash"] = lambda password: hashpw(password.encode("utf-8"), gensalt(4))
    scope["check_password"] = lambda password, hashed: checkpw(password.encode("utf-8"), hashed)
    scope["password_exceeds_bcrypt_limit"] = lambda password: False
    scope["USER_PASSWORD_RX"] = MagicMock(match=lambda password: True)

    monkeypatch.setattr(api_db, "get_metadata", lambda: {"is_initialized": True})  # the hook waits for the scheduler to initialise it
    assert api_db.create_api_user("admin", hashpw(OLD_PASSWORD.encode("utf-8"), gensalt(4)), admin=True) == ""
    return namespace["on_starting"], api_db


def _logins(db, username, password):
    user = db.get_api_user(username=username, as_dict=True)
    return bool(user) and checkpw(password.encode("utf-8"), user["password"])


def test_a_renamed_admin_replaces_the_old_one(hook, monkeypatch):
    on_starting, db = hook
    monkeypatch.setenv("API_USERNAME", "root")

    on_starting(MagicMock())

    assert db.get_api_user(username="admin") is None, "the old name must stop being a user"
    assert _logins(db, "root", OLD_PASSWORD), "the renamed user keeps its password"
    assert db.get_api_user(username="root", as_dict=True)["admin"] is True


def test_a_renamed_admin_with_a_new_password_only_accepts_the_new_pair(hook, monkeypatch):
    on_starting, db = hook
    monkeypatch.setenv("API_USERNAME", "root")
    monkeypatch.setenv("API_PASSWORD", NEW_PASSWORD)

    on_starting(MagicMock())

    assert not _logins(db, "admin", OLD_PASSWORD)
    assert not _logins(db, "root", OLD_PASSWORD)
    assert _logins(db, "root", NEW_PASSWORD)


def test_a_password_rotation_without_a_rename_still_applies(hook, monkeypatch):
    on_starting, db = hook
    monkeypatch.setenv("API_PASSWORD", NEW_PASSWORD)

    on_starting(MagicMock())

    assert _logins(db, "admin", NEW_PASSWORD)
    assert not _logins(db, "admin", OLD_PASSWORD)
