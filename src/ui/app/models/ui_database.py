from datetime import datetime
from logging import Logger
from os import sep
from os.path import join
from sys import path as sys_path
from time import sleep
from typing import List, Optional, Tuple, Union


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bcrypt import gensalt, hashpw
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from Database import Database  # type: ignore
from model import Metadata  # type: ignore

from app.models.models import Base, Permissions, Roles, RolesPermissions, RolesUsers, Users, UserRecoveryCodes, UserSessions


class UIDatabase(Database):
    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, ui=True, pool=pool, log=log, **kwargs)

    def init_ui_tables(self, bunkerweb_version: str) -> Tuple[bool, str]:
        """Initialize the database ui tables and return the result"""

        if self.readonly:
            return False, "The database is read-only, the changes will not be saved"

        assert self.sql_engine is not None, "The database engine is not initialized"

        inspector = inspect(self.sql_engine)
        db_version = None
        has_all_tables = True
        old_data = {}

        if inspector and len(inspector.get_table_names()):
            metadata = self.get_metadata()
            db_version = metadata["ui_version"]
            if metadata["default"]:
                db_version = "error"

            if db_version != bunkerweb_version:
                self.logger.warning(f"UI tables version ({db_version}) is different from BunkerWeb version ({bunkerweb_version}), migrating them ...")
                current_time = datetime.now()
                error = True
                while error:
                    try:
                        metadata = MetaData()
                        metadata.reflect(self.sql_engine)
                        error = False
                    except BaseException as e:
                        if (datetime.now() - current_time).total_seconds() > 10:
                            raise e
                        sleep(1)

                assert isinstance(metadata, MetaData)

                for table_name in Base.metadata.tables.keys():
                    if not inspector.has_table(table_name):
                        self.logger.warning(f'UI table "{table_name}" is missing, creating it')
                        has_all_tables = False
                        continue

                    with self._db_session() as session:
                        old_data[table_name] = session.query(metadata.tables[table_name]).all()

                # Rename the old tables
                db_version_id = db_version.replace(".", "_")
                with self._db_session() as session:
                    for table_name in metadata.tables.keys():
                        if table_name in Base.metadata.tables:
                            if inspector.has_table(f"{table_name}_{db_version_id}"):
                                self.logger.warning(f'UI table "{table_name}" already exists, dropping it to make room for the new one')
                                session.execute(text(f"DROP TABLE {table_name}_{db_version_id}"))
                            session.execute(text(f"ALTER TABLE {table_name} RENAME TO {table_name}_{db_version_id}"))
                            session.commit()

                Base.metadata.drop_all(self.sql_engine)
            else:
                for table_name in Base.metadata.tables.keys():
                    if not inspector.has_table(table_name):
                        self.logger.warning(f'UI table "{table_name}" is missing, creating it')
                        has_all_tables = False
                        continue

        if has_all_tables and db_version and db_version == bunkerweb_version:
            return False, ""

        self.logger.info("Creating UI tables ...")

        try:
            Base.metadata.create_all(self.sql_engine, checkfirst=True)
        except BaseException as e:
            return False, str(e)

        if db_version and db_version != bunkerweb_version:
            for table_name, data in old_data.items():
                if not data:
                    continue

                self.logger.warning(f'Restoring data for ui table "{table_name}"')
                self.logger.debug(f"Data: {data}")
                for row in data:
                    two_factor_enabled = getattr(row, "is_two_factor_enabled", None)
                    row = {column: getattr(row, column) for column in Base.metadata.tables[table_name].columns.keys() if hasattr(row, column)}

                    if table_name == "bw_ui_users" and two_factor_enabled is not None:
                        if two_factor_enabled:
                            self.logger.warning(
                                "Detected old user model, as we implemented advanced security in the new model (custom salt for passwords, totp, etc.), you will have to re set the two factor authentication for the admin user."
                            )
                        row["admin"] = True

                    with self._db_session() as session:
                        try:
                            # Check if the row already exists in the table
                            existing_row = session.query(Base.metadata.tables[table_name]).filter_by(**row).first()
                            if not existing_row:
                                session.execute(Base.metadata.tables[table_name].insert().values(row))
                                session.commit()
                        except IntegrityError as e:
                            session.rollback()
                            if "Duplicate entry" not in str(e):
                                self.logger.error(f"Error when trying to restore data for table {table_name}: {e}")
                                continue
                            self.logger.debug(e)

        with self._db_session() as session:
            try:
                metadata = session.query(Metadata).get(1)
                if metadata:
                    metadata.ui_version = bunkerweb_version
                    session.commit()
            except BaseException as e:
                self.logger.error(f"Error when trying to update ui_version field in metadata: {e}")

        return True, ""

    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[Users, dict]]:
        """Get ui user. If username is None, return the first admin user."""
        with self._db_session() as session:
            if username:
                query = session.query(Users).filter_by(username=username)
            else:
                query = session.query(Users).filter_by(admin=True)
            query = query.options(joinedload(Users.roles), joinedload(Users.recovery_codes))

            ui_user = query.first()

            if not ui_user:
                return None
            elif not as_dict:
                return ui_user

            ui_user_data = {
                "username": ui_user.username,
                "email": ui_user.email,
                "password": ui_user.password.encode("utf-8"),
                "method": ui_user.method,
                "totp_secret": ui_user.totp_secret,
                "creation_date": ui_user.creation_date,
                "update_date": ui_user.update_date,
                "roles": [role.role_name for role in ui_user.roles],
                "recovery_codes": [recovery_code.code for recovery_code in ui_user.recovery_codes],
            }

            return ui_user_data

    def create_ui_user(
        self,
        username: str,
        password: bytes,
        roles: List[str],
        email: Optional[str] = None,
        *,
        totp_secret: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        method: str = "manual",
        admin: bool = False,
    ) -> str:
        """Create ui user."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if admin and session.query(Users).with_entities(Users.username).filter_by(admin=True).first():
                return "An admin user already exists"

            user = session.query(Users).with_entities(Users.username).filter_by(username=username).first()
            if user:
                return f"User {username} already exists"

            for role in roles:
                if not session.query(Roles).with_entities(Roles.name).filter_by(name=role).first():
                    return f"Role {role} doesn't exist"
                session.add(RolesUsers(user_name=username, role_name=role))

            current_time = datetime.now()
            session.add(
                Users(
                    username=username,
                    email=email,
                    password=password.decode("utf-8"),
                    method=method,
                    admin=admin,
                    totp_secret=totp_secret,
                    creation_date=current_time,
                    update_date=current_time,
                )
            )

            for code in totp_recovery_codes or []:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

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
        old_username: Optional[str] = None,
        email: Optional[str] = None,
        totp_recovery_codes: Optional[List[str]] = None,
        method: str = "manual",
    ) -> str:
        """Update ui user."""
        totp_changed = False
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(username=old_username).first()
            if not user:
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if session.query(Users).with_entities(Users.username).filter_by(username=username).first():
                    return f"User {username} already exists"

                user.username = username

                session.query(RolesUsers).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserRecoveryCodes).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserSessions).filter_by(user_name=old_username).update({"user_name": username})

            totp_changed = user.totp_secret != totp_secret

            user.email = email
            user.password = password.decode("utf-8")
            user.totp_secret = totp_secret
            user.method = method
            user.update_date = datetime.now()

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

            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            session.query(RolesUsers).filter_by(user_name=username).delete()
            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()
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

            user = session.query(Users).filter_by(username=username).first()
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
                session.commit()
                session.refresh(user_session)
                session_id = user_session.id
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

            session.add(Roles(name=name, description=description, update_datetime=datetime.now()))

            for permission in permissions:
                if not session.query(Permissions).with_entities(Permissions.name).filter_by(name=permission).first():
                    session.add(Permissions(name=permission))
                session.add(RolesPermissions(role_name=name, permission_name=permission))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_roles(self, *, as_dict: bool = False) -> List[Union[Roles, dict]]:
        """Get ui roles."""
        with self._db_session() as session:
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

    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        """Refresh ui user recovery codes."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if not codes:
                return "No recovery codes provided"

            user = session.query(Users).filter_by(username=username).first()
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
            user = session.query(Users).filter_by(username=username).first()
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

    def get_ui_user_last_session(self, username: str) -> Optional[UserSessions]:
        """Get ui user last session."""
        with self._db_session() as session:
            return session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).first()

    def get_ui_user_sessions(self, username: str) -> List[UserSessions]:
        """Get ui user sessions."""
        with self._db_session() as session:
            return session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).limit(10).all()

    def delete_ui_user_old_sessions(self, username: str) -> str:
        """Delete ui user old sessions."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(username=username).first()
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
