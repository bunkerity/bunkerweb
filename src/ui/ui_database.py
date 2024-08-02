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

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.exc import IntegrityError

from Database import Database  # type: ignore
from model import Metadata  # type: ignore

from models import Base, Users, Roles, RolesUsers, UserRecoveryCodes, RolesPermissions, Permissions


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
                for table_name in metadata.tables.keys():
                    if table_name in Base.metadata.tables:
                        with self._db_session() as session:
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
                ui_user = session.query(Users).filter_by(username=username).first()
            else:
                ui_user = session.query(Users).filter_by(admin=True).first()

            if not ui_user:
                return None
            elif not as_dict:
                return ui_user

            ui_user_data = {
                "username": ui_user.username,
                "email": ui_user.email,
                "password": ui_user.password.encode("utf-8"),
                "method": ui_user.method,
                "last_login_at": ui_user.last_login_at,
                "last_login_ip": ui_user.last_login_ip,
                "login_count": ui_user.login_count,
                "totp_secret": ui_user.totp_secret,
                "creation_date": ui_user.creation_date,
                "update_date": ui_user.update_date,
                "roles": [],
                "recovery_codes": [],
            }

            for role in session.query(RolesUsers).filter_by(user_name=ui_user.username).all():
                ui_user_data["roles"].append(role.role_name)
            for recovery_code in session.query(UserRecoveryCodes).filter_by(user_name=ui_user.username).all():
                ui_user_data["recovery_codes"].append(recovery_code.code)

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

            if admin and session.query(Users).filter_by(admin=True).first():
                return "An admin user already exists"

            user = session.query(Users).filter_by(username=username).first()
            if user:
                return f"User {username} already exists"

            for role in roles:
                if not session.query(Roles).filter_by(name=role).first():
                    return f"Role {role} doesn't exist"
                session.add(RolesUsers(user_name=username, role_name=role))

            session.add(
                Users(
                    username=username,
                    email=email,
                    password=password.decode("utf-8"),
                    method=method,
                    admin=admin,
                    totp_secret=totp_secret,
                    totp_refreshed=bool(totp_secret),
                )
            )

            for code in totp_recovery_codes or []:
                session.add(UserRecoveryCodes(user_name=username, code=code))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user(
        self, username: str, password: bytes, totp_secret: Optional[str], *, totp_recovery_codes: Optional[List[str]] = None, method: str = "manual"
    ) -> str:
        """Update ui user."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            if user.totp_secret != totp_secret:
                user.totp_refreshed = True

            user.password = password.decode("utf-8")
            user.totp_secret = totp_secret
            user.method = method

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        if user.totp_refreshed:
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

    def mark_ui_user_login(self, username: str, date: datetime, ip: str) -> str:
        """Mark ui user login."""
        with self._db_session() as session:
            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            user.last_login_at = date
            user.last_login_ip = ip
            user.login_count += 1

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

            if session.query(Roles).filter_by(name=name).first():
                return f"Role {name} already exists"

            session.add(Roles(name=name, description=description))

            for permission in permissions:
                if not session.query(Permissions).filter_by(name=permission).first():
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
            roles = session.query(Roles).all()
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

                for permission in session.query(RolesPermissions).filter_by(role_name=role.name).all():
                    role_data["permissions"].append(permission.permission_name)

                roles_data.append(role_data)

            return roles_data

    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        """Refresh ui user recovery codes."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            if not codes:
                return "No recovery codes provided"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            for code in codes:
                session.add(UserRecoveryCodes(user_name=username, code=code))

            user.totp_refreshed = True

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
            return [role.role_name for role in session.query(RolesUsers).filter_by(user_name=username).all()]

    def get_ui_role_permissions(self, role_name: str) -> List[str]:
        """Get ui role permissions."""
        with self._db_session() as session:
            return [permission.permission_name for permission in session.query(RolesPermissions).filter_by(role_name=role_name).all()]

    def get_ui_user_recovery_codes(self, username: str) -> List[str]:
        """Get ui user recovery codes."""
        with self._db_session() as session:
            return [code.code for code in session.query(UserRecoveryCodes).filter_by(user_name=username).all()]

    def get_ui_user_permissions(self, username: str) -> List[str]:
        """Get ui user permissions."""
        with self._db_session() as session:
            roles = session.query(RolesUsers).filter_by(user_name=username).all()

        permissions = []
        for role in roles:
            permissions.extend(self.get_ui_role_permissions(role.role_name))
        return permissions

    def use_ui_user_recovery_code(self, username: str, code: str) -> str:
        """Use ui user recovery code."""
        with self._db_session() as session:
            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            recovery_code = session.query(UserRecoveryCodes).filter_by(user_name=username, code=code).first()
            if not recovery_code:
                return "Invalid recovery code"

            session.delete(recovery_code)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

    def set_ui_user_recovery_code_refreshed(self, username: str, value: bool) -> str:
        """Set ui user recovery code refreshed."""
        with self._db_session() as session:
            user = session.query(Users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            user.totp_refreshed = value

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
