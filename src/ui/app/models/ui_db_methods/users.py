#!/usr/bin/env python3
from datetime import datetime
from typing import List, Literal, Optional, Union

from bcrypt import gensalt, hashpw
from sqlalchemy import delete, select, update
from sqlalchemy.orm import joinedload

from model import Permissions, Roles, RolesPermissions, RolesUsers, UserColumnsPreferences, UserRecoveryCodes, UserSessions  # type: ignore

from db_methods.common import DatabaseMixinBase  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS


class UIUsersMethodsMixin(DatabaseMixinBase):
    """Web UI users, sessions and login/access bookkeeping."""

    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[UiUsers, dict]]:
        """Get ui user. If username is None, return the first admin user."""
        with self._db_session() as session:
            # Build query based on parameters
            stmt = select(UiUsers)
            stmt = stmt.filter_by(username=username) if username else stmt.filter_by(admin=True)
            stmt = stmt.options(joinedload(UiUsers.roles), joinedload(UiUsers.recovery_codes), joinedload(UiUsers.columns_preferences))

            ui_user = session.scalars(stmt.limit(1)).unique().first()
            if not ui_user:
                return None

            # Ensure admin users have the "admin" role
            if ui_user.admin and not self.readonly:
                admin_role_exists = any(role.role_name == "admin" for role in ui_user.roles)

                if not admin_role_exists:
                    # Check if admin role exists, create it if not
                    admin_role = session.scalars(select(Roles).filter_by(name="admin").limit(1)).first()
                    if not admin_role:
                        current_time = datetime.now().astimezone()
                        admin_role = Roles(name="admin", description="Admins can create new users, edit and read the data.", update_datetime=current_time)
                        session.add(admin_role)

                        # Add default permissions
                        for permission in ("manage", "write", "read"):
                            if not session.scalars(select(Permissions).filter_by(name=permission).limit(1)).first():
                                session.add(Permissions(name=permission))
                            session.add(RolesPermissions(role_name="admin", permission_name=permission))

                    session.add(RolesUsers(user_name=ui_user.username, role_name="admin"))
                    session.commit()
                    session.refresh(ui_user)

            # Add default column preferences if missing
            if not ui_user.columns_preferences and not self.readonly:
                for table_name, columns in COLUMNS_PREFERENCES_DEFAULTS.items():
                    session.add(UserColumnsPreferences(user_name=ui_user.username, table_name=table_name, columns=columns))
                session.commit()
                session.refresh(ui_user)

            if not as_dict:
                return ui_user

            return {
                "username": ui_user.username,
                "email": ui_user.email,
                "password": ui_user.password.encode("utf-8"),
                "method": ui_user.method,
                "admin": ui_user.admin,
                "theme": ui_user.theme,
                "language": ui_user.language,
                "totp_secret": ui_user.totp_secret,
                "creation_date": ui_user.creation_date.astimezone(),
                "update_date": ui_user.update_date.astimezone(),
                "roles": [role.role_name for role in ui_user.roles],
                "recovery_codes": [rc.code for rc in ui_user.recovery_codes],
            }

    def create_ui_user(
        self,
        username: str,
        password: bytes,
        roles: List[str],
        email: Optional[str] = None,
        *,
        theme: Union[Literal["light"], Literal["dark"]] = "light",
        language: str = "en",
        totp_secret: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        creation_date: Optional[datetime] = None,
        method: str = "manual",
        admin: bool = False,
    ) -> str:
        """Create ui user."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if admin and session.execute(select(UiUsers.username).filter_by(admin=True).limit(1)).first():
                return "An admin user already exists"

            user = session.execute(select(UiUsers.username).filter_by(username=username).limit(1)).first()
            if user:
                return f"User {username} already exists"

            for role in roles:
                if not session.execute(select(Roles.name).filter_by(name=role).limit(1)).first():
                    return f"Role {role} doesn't exist"
                session.add(RolesUsers(user_name=username, role_name=role))

            current_time = datetime.now().astimezone()
            session.add(
                UiUsers(
                    username=username,
                    email=email,
                    password=password.decode("utf-8"),
                    method=method,
                    admin=admin,
                    theme=theme,
                    language=language,
                    totp_secret=totp_secret,
                    creation_date=creation_date or current_time,
                    update_date=current_time,
                )
            )

            for code in totp_recovery_codes or []:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            for table_name, columns in COLUMNS_PREFERENCES_DEFAULTS.items():
                session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=columns))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user(
        self,
        username: str,
        password: bytes,
        totp_secret: Optional[str],
        *,
        theme: Union[Literal["light"], Literal["dark"]] = "light",
        old_username: Optional[str] = None,
        email: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        method: str = "manual",
        language: str = "en",
    ) -> str:
        """Update ui user."""
        totp_changed = False
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=old_username).limit(1)).first()
            if not user:
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if session.execute(select(UiUsers.username).filter_by(username=username).limit(1)).first():
                    return f"User {username} already exists"

                user.username = username

                session.execute(update(RolesUsers).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserRecoveryCodes).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserSessions).filter_by(user_name=old_username).values({"user_name": username}))
                session.execute(update(UserColumnsPreferences).filter_by(user_name=old_username).values({"user_name": username}))

            totp_changed = user.totp_secret != totp_secret

            user.email = email
            user.password = password.decode("utf-8")
            user.totp_secret = totp_secret
            user.method = method
            user.theme = theme
            user.language = language
            user.update_date = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        if totp_changed:
            if totp_recovery_codes:
                self.refresh_ui_user_recovery_codes(username, totp_recovery_codes or [])
            else:
                self.delete_ui_user_recovery_codes(username)

        return ""

    def delete_ui_user(self, username: str) -> str:
        """Delete ui user."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            session.execute(delete(RolesUsers).filter_by(user_name=username))
            session.execute(delete(UserRecoveryCodes).filter_by(user_name=username))
            session.execute(delete(UserColumnsPreferences).filter_by(user_name=username))
            session.delete(user)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def mark_ui_user_login(self, username: str, date: datetime, ip: str, user_agent: str) -> Union[str, int]:
        """Mark ui user login."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            user_session = UserSessions(
                user_name=username,
                ip=ip,
                user_agent=user_agent,
                creation_date=date,
                last_activity=date,
            )
            session.add(user_session)

            try:
                session.flush()  # Flush to get the auto-generated ID
                session_id = user_session.id
                session.commit()
                return session_id
            except BaseException as e:
                return str(e)

    def mark_ui_user_access(self, session_id: int, date: datetime) -> str:
        """Mark ui user access."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user_session = session.scalars(select(UserSessions).filter_by(id=session_id).limit(1)).first()
            if not user_session:
                return f"Session {session_id} doesn't exist"

            user_session.last_activity = date

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_ui_user_old_sessions(self, username: str) -> str:
        """Delete ui user old sessions."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            sessions_to_delete = session.scalars(select(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).offset(1)).all()
            for session_to_delete in sessions_to_delete:
                session.delete(session_to_delete)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
