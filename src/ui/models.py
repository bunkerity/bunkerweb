from datetime import datetime, timezone
from functools import partial
from os.path import join, sep
from sys import path as sys_path
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bcrypt import checkpw
from flask_login import AnonymousUserMixin, UserMixin
from pyotp.totp import TOTP
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Boolean, DateTime, Column, Integer, String, ForeignKey, func


from model import METHODS_ENUM  # type: ignore

Base = declarative_base()


class AnonymousUser(AnonymousUserMixin):
    username = "Anonymous"
    email = None
    password = ""
    method = "manual"
    admin = False
    last_login_at = None
    last_login_ip = None
    login_count = 0
    totp_secret = None
    creation_date = datetime.now(timezone.utc)
    update_date = datetime.now(timezone.utc)

    def check_password(self, password: str) -> bool:
        return False

    def check_otp(self, otp: str, *, secret: Optional[str] = None) -> bool:
        if not secret:
            raise ValueError("Secret is required for anonymous user")
        return TOTP(secret).verify(otp, valid_window=3)


class Users(Base, UserMixin):
    __tablename__ = "bw_ui_users"

    username = Column(String(256), primary_key=True)
    email = Column(String(256), unique=True, nullable=True)
    password = Column(String(60), nullable=False)
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    admin = Column(Boolean, nullable=False, default=False)

    # Trackable
    last_login_at = Column(DateTime(), nullable=True)
    last_login_ip = Column(String(39), nullable=True)
    login_count = Column(Integer, default=0, nullable=False)

    # 2FA
    totp_secret = Column(String(32), nullable=True)
    totp_refreshed = Column(Boolean, nullable=False, default=False)

    creation_date = Column(DateTime(), nullable=False, server_default=func.now())
    update_date = Column(DateTime(), nullable=False, server_default=func.now(), onupdate=partial(datetime.now, timezone.utc))

    roles = relationship("RolesUsers", back_populates="user", cascade="all")
    recovery_codes = relationship("UserRecoveryCodes", back_populates="user", cascade="all")
    list_roles: list[str] = []
    list_permissions: list[str] = []
    list_recovery_codes: list[str] = []

    def get_id(self):
        return self.username

    def check_password(self, password: str) -> bool:
        return checkpw(password.encode("utf-8"), self.password.encode("utf-8"))

    def check_otp(self, otp: str, *, secret: Optional[str] = None) -> bool:
        if secret:
            return TOTP(secret).verify(otp, valid_window=3)
        return TOTP(self.totp_secret).verify(otp, valid_window=3)


class Roles(Base):
    __tablename__ = "bw_ui_roles"

    name = Column(String(64), primary_key=True)
    description = Column(String(256), nullable=False)
    update_datetime = Column(DateTime(), nullable=False, server_default=func.now(), onupdate=partial(datetime.now, timezone.utc))

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

    id = Column(Integer, primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    code = Column(String(19), nullable=False)

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
