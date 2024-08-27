from datetime import datetime
from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bcrypt import checkpw
from flask_login import AnonymousUserMixin, UserMixin
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import TEXT, Boolean, DateTime, Column, Identity, Integer, String, ForeignKey, UnicodeText

from model import METHODS_ENUM  # type: ignore

Base = declarative_base()


class AnonymousUser(AnonymousUserMixin):
    username = "Anonymous"
    email = None
    password = ""
    method = "manual"
    admin = False
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


class Users(Base, UserMixin):
    __tablename__ = "bw_ui_users"

    username = Column(String(256), primary_key=True)
    email = Column(String(256), unique=True, nullable=True)
    password = Column(String(60), nullable=False)
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    admin = Column(Boolean, nullable=False, default=False)

    # 2FA
    totp_secret = Column(String(256), nullable=True)

    creation_date = Column(DateTime(timezone=True), nullable=False)
    update_date = Column(DateTime(timezone=True), nullable=False)

    roles = relationship("RolesUsers", back_populates="user", cascade="all")
    recovery_codes = relationship("UserRecoveryCodes", back_populates="user", cascade="all")
    sessions = relationship("UserSessions", back_populates="user", cascade="all")
    list_roles: list[str] = []
    list_permissions: list[str] = []
    list_recovery_codes: list[str] = []

    def get_id(self):
        return self.username

    def check_password(self, password: str) -> bool:
        return checkpw(password.encode("utf-8"), self.password.encode("utf-8"))


class Roles(Base):
    __tablename__ = "bw_ui_roles"

    name = Column(String(64), primary_key=True)
    description = Column(String(256), nullable=False)
    update_datetime = Column(DateTime(timezone=True), nullable=False)

    users = relationship("RolesUsers", back_populates="role", cascade="all")
    permissions = relationship("RolesPermissions", back_populates="role", cascade="all")


class RolesUsers(Base):
    __tablename__ = "bw_ui_roles_users"

    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), primary_key=True)
    role_name = Column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True)

    user = relationship("Users", back_populates="roles")
    role = relationship("Roles", back_populates="users")


class UserRecoveryCodes(Base):
    __tablename__ = "bw_ui_user_recovery_codes"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    code = Column(UnicodeText, nullable=False)

    user = relationship("Users", back_populates="recovery_codes")


class RolesPermissions(Base):
    __tablename__ = "bw_ui_roles_permissions"

    role_name = Column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True)
    permission_name = Column(String(64), ForeignKey("bw_ui_permissions.name", onupdate="cascade", ondelete="cascade"), primary_key=True)

    role = relationship("Roles", back_populates="permissions")
    permission = relationship("Permissions", back_populates="roles")


class Permissions(Base):
    __tablename__ = "bw_ui_permissions"

    name = Column(String(64), primary_key=True)

    roles = relationship("RolesPermissions", back_populates="permission", cascade="all")


class UserSessions(Base):
    __tablename__ = "bw_ui_user_sessions"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    ip = Column(String(39), nullable=False)
    user_agent = Column(TEXT, nullable=False)
    creation_date = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False)

    user = relationship("Users", back_populates="sessions")
