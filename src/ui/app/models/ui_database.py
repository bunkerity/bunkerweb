from datetime import datetime
from logging import Logger
from os import sep
from os.path import join
from sys import path as sys_path
from typing import Dict, List, Literal, Optional, Union


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bcrypt import gensalt, hashpw
from sqlalchemy.orm import joinedload

from Database import Database  # type: ignore
from model import Permissions, Roles, RolesPermissions, RolesUsers, UserColumnsPreferences, UserRecoveryCodes, UserSessions  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS


class UIDatabase(Database):
    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, external=True, pool=pool, log=log, **kwargs)

    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[UiUsers, dict]]:
        """Get ui user. If username is None, return the first admin user."""
        with self._db_session() as session:
            # Build query based on parameters
            query = session.query(UiUsers)
            query = query.filter_by(username=username) if username else query.filter_by(admin=True)
            query = query.options(joinedload(UiUsers.roles), joinedload(UiUsers.recovery_codes), joinedload(UiUsers.columns_preferences))

            ui_user = query.first()
            if not ui_user:
                return None

            # Ensure admin users have the "admin" role
            if ui_user.admin and not self.readonly:
                admin_role_exists = any(role.role_name == "admin" for role in ui_user.roles)

                if not admin_role_exists:
                    # Check if admin role exists, create it if not
                    admin_role = session.query(Roles).filter_by(name="admin").first()
                    if not admin_role:
                        current_time = datetime.now().astimezone()
                        admin_role = Roles(name="admin", description="Admins can create new users, edit and read the data.", update_datetime=current_time)
                        session.add(admin_role)

                        # Add default permissions
                        for permission in ("manage", "write", "read"):
                            if not session.query(Permissions).filter_by(name=permission).first():
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

            if admin and session.query(UiUsers).with_entities(UiUsers.username).filter_by(admin=True).first():
                return "An admin user already exists"

            user = session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first()
            if user:
                return f"User {username} already exists"

            for role in roles:
                if not session.query(Roles).with_entities(Roles.name).filter_by(name=role).first():
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

            user = session.query(UiUsers).filter_by(username=old_username).first()
            if not user:
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first():
                    return f"User {username} already exists"

                user.username = username

                session.query(RolesUsers).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserRecoveryCodes).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserSessions).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserColumnsPreferences).filter_by(user_name=old_username).update({"user_name": username})

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

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            session.query(RolesUsers).filter_by(user_name=username).delete()
            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()
            session.query(UserColumnsPreferences).filter_by(user_name=username).delete()
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

            user = session.query(UiUsers).filter_by(username=username).first()
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

            user_session = session.query(UserSessions).filter_by(id=session_id).first()
            if not user_session:
                return f"Session {session_id} doesn't exist"

            user_session.last_activity = date

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def create_ui_role(self, name: str, description: str, permissions: List[str]) -> str:
        """Create ui role."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if session.query(Roles).with_entities(Roles.name).filter_by(name=name).first():
                return f"Role {name} already exists"

            session.add(Roles(name=name, description=description, update_datetime=datetime.now().astimezone()))

            for permission in permissions:
                if not session.query(Permissions).with_entities(Permissions.name).filter_by(name=permission).first():
                    session.add(Permissions(name=permission))
                session.add(RolesPermissions(role_name=name, permission_name=permission))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_roles(self, *, as_dict: bool = False) -> Union[str, List[Union[Roles, dict]]]:
        """Get ui roles."""
        with self._db_session() as session:
            try:
                roles = session.query(Roles).with_entities(Roles.name, Roles.description, Roles.update_datetime).all()
                if not as_dict:
                    return roles

                roles_data = []
                for role in roles:
                    role_data = {
                        "name": role.name,
                        "description": role.description,
                        "update_datetime": role.update_datetime,
                        "permissions": [],
                    }

                    for permission in session.query(RolesPermissions).with_entities(RolesPermissions.permission_name).filter_by(role_name=role.name):
                        role_data["permissions"].append(permission.permission_name)

                    roles_data.append(role_data)

                return roles_data
            except BaseException as e:
                return str(e)

    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        """Refresh ui user recovery codes."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if not codes:
                return "No recovery codes provided"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            for code in codes:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_ui_user_recovery_codes(self, username: str) -> str:
        """Delete ui user recovery codes."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_user_roles(self, username: str) -> List[str]:
        """Get ui user roles."""
        with self._db_session() as session:
            return [role.role_name for role in session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)]

    def get_ui_role_permissions(self, role_name: str) -> List[str]:
        """Get ui role permissions."""
        with self._db_session() as session:
            return [
                permission.permission_name
                for permission in session.query(RolesPermissions).with_entities(RolesPermissions.permission_name).filter_by(role_name=role_name)
            ]

    def get_ui_user_recovery_codes(self, username: str) -> List[str]:
        """Get ui user recovery codes."""
        with self._db_session() as session:
            return [code.code for code in session.query(UserRecoveryCodes).with_entities(UserRecoveryCodes.code).filter_by(user_name=username)]

    def get_ui_user_permissions(self, username: str) -> List[str]:
        """Get ui user permissions."""
        with self._db_session() as session:
            query = session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)

        permissions = []
        for role in query:
            permissions.extend(self.get_ui_role_permissions(role.role_name))
        return permissions

    def use_ui_user_recovery_code(self, username: str, hashed_code: str) -> str:
        """Use ui user recovery code."""
        with self._db_session() as session:
            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            recovery_code = session.query(UserRecoveryCodes).filter_by(user_name=username, code=hashed_code).first()
            if not recovery_code:
                return "Invalid recovery code"

            session.delete(recovery_code)

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

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            sessions_to_delete = session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).offset(1).all()
            for session_to_delete in sessions_to_delete:
                session.delete(session_to_delete)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user_columns_preferences(self, username: str, table_name: str, columns: Dict[str, bool]) -> str:
        """Update ui user columns preferences."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                return f"Table {table_name} doesn't exist"

            columns_preferences.columns = columns

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_user_columns_preferences(self, username: str, table_name: str) -> Dict[str, bool]:
        """Get ui user columns preferences."""
        with self._db_session() as session:
            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                default_columns = COLUMNS_PREFERENCES_DEFAULTS.get(table_name, {})
                if not self.readonly and session.query(UiUsers).filter_by(username=username).first():
                    session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=default_columns))
                    session.commit()
                return default_columns

            return columns_preferences.columns
