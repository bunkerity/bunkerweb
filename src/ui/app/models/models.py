from datetime import datetime
from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bcrypt import checkpw
from flask_login import AnonymousUserMixin, UserMixin

from model import Users  # type: ignore


class AnonymousUser(AnonymousUserMixin):
    username = "Anonymous"
    email = None
    password = ""
    method = "manual"
    admin = False
    theme = "light"
    language = "en"
    totp_secret = None
    creation_date = datetime.now().astimezone()
    update_date = datetime.now().astimezone()
    list_roles = []
    list_permissions = []
    list_recovery_codes = []

    def get_id(self):
        return self.username

    def check_password(self, password: str) -> bool:
        return False


class UiUsers(Users, UserMixin):
    def get_id(self):
        return self.username

    def check_password(self, password: str) -> bool:
        # bcrypt 5.x raises ValueError on >72 bytes; hashing truncates to 72 (see
        # app/utils.py:_bcrypt_secret), so truncate here too to keep verification symmetric.
        return checkpw(password.encode("utf-8")[:72], self.password.encode("utf-8"))
