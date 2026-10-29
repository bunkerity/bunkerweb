"""Plain helpers for the UI route tests.

Kept out of ``conftest.py`` on purpose: the suite runs in prepend import mode with no ``__init__.py``, so every
``conftest.py`` is the module ``conftest`` and importing names from it binds to whichever one was loaded last.
"""

from concurrent.futures import Future

import flask_login


class FakeData(dict):
    """UIData without the file: the routes only need a dict that has a ``file_path``."""

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def load_from_file(self):
        pass

    def write_to_file(self):
        pass


class FakeRedis:
    """The slice of redis-py the route code uses: ``scan_iter``, ``get``/``ttl`` through a pipeline, plus plain get/set/delete."""

    def __init__(self, values=None, ttls=None):
        self.values = dict(values or {})
        self.ttls = dict(ttls or {})
        self.deleted = []

    def scan_iter(self, pattern, count=None):
        from fnmatch import fnmatchcase

        return iter([key for key in self.values if fnmatchcase(key.decode() if isinstance(key, bytes) else key, pattern)])

    def get(self, key):
        return self.values.get(key)

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def delete(self, *keys):
        self.deleted.extend(keys)
        return len(keys)

    def pipeline(self, transaction=False):
        redis = self

        class Pipe:
            def __init__(self):
                self.ops = []

            def get(self, key):
                self.ops.append(redis.get(key))

            def ttl(self, key):
                self.ops.append(redis.ttl(key))

            def execute(self):
                return list(self.ops)

        return Pipe()


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            future.set_exception(exc)
        return future


class FakeUser(flask_login.UserMixin):
    def __init__(self, username="alice", admin=True, permissions=("read", "write"), **extra):
        self.username = username
        self.admin = admin
        self.list_permissions = set(permissions)
        self.list_roles = []
        self.totp_secret = None
        self.method = "ui"
        self.theme = "light"
        self.language = "en"
        self.email = None
        self.creation_date = None
        self.last_login_at = None
        self.last_login_ip = None
        self.password = "stored-hash"
        self.good_password = "Correct-Horse1!"
        self.roles = []
        self.list_recovery_codes = []
        for key, value in extra.items():
            setattr(self, key, value)

    def get_id(self):
        return self.username

    def check_password(self, password):
        return password == self.good_password
