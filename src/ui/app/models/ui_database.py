from datetime import datetime
from os import sep
from os.path import join
from sys import path as sys_path
from typing import Dict, List, Literal, Optional, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-ui-database",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-ui-database")

from bcrypt import gensalt, hashpw
from sqlalchemy.orm import joinedload

from Database import Database  # type: ignore
from model import Permissions, Roles, RolesPermissions, RolesUsers, UserColumnsPreferences, UserRecoveryCodes, UserSessions  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS


class UIDatabase(Database):
    # Initialize the UIDatabase instance with database connection and logging.
    # Inherits from Database class and configures UI-specific database settings.
    def __init__(self, logger_param=None, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, ui=True, pool=pool, log=log, **kwargs)

    # Get UI user by username or return the first admin user if username is None.
    # Ensures admin users have proper roles and default column preferences configured.
    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[UiUsers, dict]]:
        logger.debug(f"get_ui_user() called with username={username}, as_dict={as_dict}")
        
        with self._db_session() as session:
            # Build query based on parameters
            query = session.query(UiUsers)
            query = query.filter_by(username=username) if username else query.filter_by(admin=True)
            query = query.options(joinedload(UiUsers.roles), joinedload(UiUsers.recovery_codes), joinedload(UiUsers.columns_preferences))

            ui_user = query.first()
            if not ui_user:
                logger.debug("No UI user found")
                return None

            # Ensure admin users have the "admin" role
            if ui_user.admin and not self.readonly:
                logger.debug("Checking admin role for admin user")
                admin_role_exists = any(role.role_name == "admin" for role in ui_user.roles)

                if not admin_role_exists:
                    logger.debug("Admin role missing, creating and assigning it")
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
                logger.debug("Adding default column preferences")
                for table_name, columns in COLUMNS_PREFERENCES_DEFAULTS.items():
                    session.add(UserColumnsPreferences(user_name=ui_user.username, table_name=table_name, columns=columns))
                session.commit()
                session.refresh(ui_user)

            if not as_dict:
                logger.debug("Returning UiUsers object")
                return ui_user

            logger.debug("Converting to dictionary format")
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

    # Create a new UI user with specified credentials and settings.
    # Validates role existence and creates associated recovery codes and preferences.
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
        logger.debug(f"create_ui_user() called with username={username}, admin={admin}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if admin and session.query(UiUsers).with_entities(UiUsers.username).filter_by(admin=True).first():
                logger.debug("Admin user already exists")
                return "An admin user already exists"

            user = session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first()
            if user:
                logger.debug(f"User {username} already exists")
                return f"User {username} already exists"

            for role in roles:
                if not session.query(Roles).with_entities(Roles.name).filter_by(name=role).first():
                    logger.debug(f"Role {role} doesn't exist")
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
                logger.debug(f"User {username} created successfully")
            except BaseException as e:
                logger.exception("Exception while creating UI user")
                return str(e)

        return ""

    # Update existing UI user with new credentials and settings.
    # Handles username changes and updates recovery codes if TOTP secret changes.
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
        logger.debug(f"update_ui_user() called with username={username}, old_username={old_username}")
        
        totp_changed = False
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=old_username).first()
            if not user:
                logger.debug(f"User {old_username} doesn't exist")
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first():
                    logger.debug(f"User {username} already exists")
                    return f"User {username} already exists"

                logger.debug(f"Updating username from {old_username} to {username}")
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
                logger.debug(f"User {username} updated successfully")
            except BaseException as e:
                logger.exception("Exception while updating UI user")
                return str(e)

        if totp_changed:
            logger.debug("TOTP secret changed, updating recovery codes")
            if totp_recovery_codes:
                self.refresh_ui_user_recovery_codes(username, totp_recovery_codes or [])
            else:
                self.delete_ui_user_recovery_codes(username)

        return ""

    # Delete UI user and all associated data from the database.
    # Removes roles, recovery codes, and column preferences for the user.
    def delete_ui_user(self, username: str) -> str:
        logger.debug(f"delete_ui_user() called with username={username}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            session.query(RolesUsers).filter_by(user_name=username).delete()
            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()
            session.query(UserColumnsPreferences).filter_by(user_name=username).delete()
            session.delete(user)

            try:
                session.commit()
                logger.debug(f"User {username} deleted successfully")
            except BaseException as e:
                logger.exception("Exception while deleting UI user")
                return str(e)

        return ""

    # Record user login session with IP address and user agent.
    # Creates a new session entry and returns the session ID for tracking.
    def mark_ui_user_login(self, username: str, date: datetime, ip: str, user_agent: str) -> Union[str, int]:
        logger.debug(f"mark_ui_user_login() called with username={username}, ip={ip}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
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
                logger.debug(f"Login session created with ID {session_id}")
                return session_id
            except BaseException as e:
                logger.exception("Exception while marking UI user login")
                return str(e)

    # Update the last activity timestamp for a user session.
    # Tracks user activity to maintain session validity and statistics.
    def mark_ui_user_access(self, session_id: int, date: datetime) -> str:
        logger.debug(f"mark_ui_user_access() called with session_id={session_id}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user_session = session.query(UserSessions).filter_by(id=session_id).first()
            if not user_session:
                logger.debug(f"Session {session_id} doesn't exist")
                return f"Session {session_id} doesn't exist"

            user_session.last_activity = date

            try:
                session.commit()
                logger.debug(f"Session {session_id} activity updated")
            except BaseException as e:
                logger.exception("Exception while marking UI user access")
                return str(e)

        return ""

    # Create a new role with specified permissions.
    # Validates permissions existence and creates necessary permission entries.
    def create_ui_role(self, name: str, description: str, permissions: List[str]) -> str:
        logger.debug(f"create_ui_role() called with name={name}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if session.query(Roles).with_entities(Roles.name).filter_by(name=name).first():
                logger.debug(f"Role {name} already exists")
                return f"Role {name} already exists"

            session.add(Roles(name=name, description=description, update_datetime=datetime.now().astimezone()))

            for permission in permissions:
                if not session.query(Permissions).with_entities(Permissions.name).filter_by(name=permission).first():
                    session.add(Permissions(name=permission))
                session.add(RolesPermissions(role_name=name, permission_name=permission))

            try:
                session.commit()
                logger.debug(f"Role {name} created successfully")
            except BaseException as e:
                logger.exception("Exception while creating UI role")
                return str(e)

        return ""

    # Retrieve all UI roles with their permissions and metadata.
    # Returns either role objects or dictionary format based on as_dict parameter.
    def get_ui_roles(self, *, as_dict: bool = False) -> Union[str, List[Union[Roles, dict]]]:
        logger.debug(f"get_ui_roles() called with as_dict={as_dict}")
        
        with self._db_session() as session:
            try:
                roles = session.query(Roles).with_entities(Roles.name, Roles.description, Roles.update_datetime).all()
                if not as_dict:
                    logger.debug(f"Returning {len(roles)} roles as objects")
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

                logger.debug(f"Returning {len(roles_data)} roles as dictionaries")
                return roles_data
            except BaseException as e:
                logger.exception("Exception while getting UI roles")
                return str(e)

    # Replace all recovery codes for a user with new ones.
    # Hashes the new codes and stores them securely in the database.
    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        logger.debug(f"refresh_ui_user_recovery_codes() called with username={username}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if not codes:
                logger.debug("No recovery codes provided")
                return "No recovery codes provided"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            for code in codes:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            try:
                session.commit()
                logger.debug(f"Recovery codes refreshed for user {username}")
            except BaseException as e:
                logger.exception("Exception while refreshing UI user recovery codes")
                return str(e)

        return ""

    # Remove all recovery codes for a user from the database.
    # Used when disabling two-factor authentication for a user account.
    def delete_ui_user_recovery_codes(self, username: str) -> str:
        logger.debug(f"delete_ui_user_recovery_codes() called with username={username}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            try:
                session.commit()
                logger.debug(f"Recovery codes deleted for user {username}")
            except BaseException as e:
                logger.exception("Exception while deleting UI user recovery codes")
                return str(e)

        return ""

    # Get all roles assigned to a specific user.
    # Returns a list of role names for authorization checks.
    def get_ui_user_roles(self, username: str) -> List[str]:
        logger.debug(f"get_ui_user_roles() called with username={username}")
        
        with self._db_session() as session:
            roles = [role.role_name for role in session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)]
            logger.debug(f"Found {len(roles)} roles for user {username}")
            return roles

    # Get all permissions granted to a specific role.
    # Returns a list of permission names for access control validation.
    def get_ui_role_permissions(self, role_name: str) -> List[str]:
        logger.debug(f"get_ui_role_permissions() called with role_name={role_name}")
        
        with self._db_session() as session:
            permissions = [
                permission.permission_name
                for permission in session.query(RolesPermissions).with_entities(RolesPermissions.permission_name).filter_by(role_name=role_name)
            ]
            logger.debug(f"Found {len(permissions)} permissions for role {role_name}")
            return permissions

    # Get all recovery codes for a user account.
    # Returns hashed codes for two-factor authentication recovery.
    def get_ui_user_recovery_codes(self, username: str) -> List[str]:
        logger.debug(f"get_ui_user_recovery_codes() called with username={username}")
        
        with self._db_session() as session:
            codes = [code.code for code in session.query(UserRecoveryCodes).with_entities(UserRecoveryCodes.code).filter_by(user_name=username)]
            logger.debug(f"Found {len(codes)} recovery codes for user {username}")
            return codes

    # Get all permissions granted to a user through their assigned roles.
    # Aggregates permissions from all user roles for comprehensive access control.
    def get_ui_user_permissions(self, username: str) -> List[str]:
        logger.debug(f"get_ui_user_permissions() called with username={username}")
        
        with self._db_session() as session:
            query = session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)

        permissions = []
        for role in query:
            permissions.extend(self.get_ui_role_permissions(role.role_name))
        
        logger.debug(f"Found {len(permissions)} total permissions for user {username}")
        return permissions

    # Use and remove a recovery code for two-factor authentication.
    # Validates the code and deletes it from the database after use.
    def use_ui_user_recovery_code(self, username: str, hashed_code: str) -> str:
        logger.debug(f"use_ui_user_recovery_code() called with username={username}")
        
        with self._db_session() as session:
            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            recovery_code = session.query(UserRecoveryCodes).filter_by(user_name=username, code=hashed_code).first()
            if not recovery_code:
                logger.debug("Invalid recovery code provided")
                return "Invalid recovery code"

            session.delete(recovery_code)

            try:
                session.commit()
                logger.debug(f"Recovery code used for user {username}")
            except BaseException as e:
                logger.exception("Exception while using UI user recovery code")
                return str(e)

        return ""

    # Delete all old sessions except the most recent one for a user.
    # Helps maintain session security by removing outdated login sessions.
    def delete_ui_user_old_sessions(self, username: str) -> str:
        logger.debug(f"delete_ui_user_old_sessions() called with username={username}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            sessions_to_delete = session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).offset(1).all()
            for session_to_delete in sessions_to_delete:
                session.delete(session_to_delete)

            try:
                session.commit()
                logger.debug(f"Deleted {len(sessions_to_delete)} old sessions for user {username}")
            except BaseException as e:
                logger.exception("Exception while deleting UI user old sessions")
                return str(e)

        return ""

    # Update column visibility preferences for a user's table view.
    # Allows users to customize which columns are shown in data tables.
    def update_ui_user_columns_preferences(self, username: str, table_name: str, columns: Dict[str, bool]) -> str:
        logger.debug(f"update_ui_user_columns_preferences() called with username={username}, table={table_name}")
        
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                logger.debug(f"Table {table_name} doesn't exist")
                return f"Table {table_name} doesn't exist"

            columns_preferences.columns = columns

            try:
                session.commit()
                logger.debug(f"Column preferences updated for user {username}, table {table_name}")
            except BaseException as e:
                logger.exception("Exception while updating UI user columns preferences")
                return str(e)

        return ""

    # Get column visibility preferences for a user's table view.
    # Returns preferences or creates defaults if none exist for the user.
    def get_ui_user_columns_preferences(self, username: str, table_name: str) -> Dict[str, bool]:
        logger.debug(f"get_ui_user_columns_preferences() called with username={username}, table={table_name}")
        
        with self._db_session() as session:
            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                default_columns = COLUMNS_PREFERENCES_DEFAULTS.get(table_name, {})
                if not self.readonly and session.query(UiUsers).filter_by(username=username).first():
                    logger.debug(f"Creating default preferences for user {username}, table {table_name}")
                    session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=default_columns))
                    session.commit()
                return default_columns

            logger.debug(f"Retrieved column preferences for user {username}, table {table_name}")
            return columns_preferences.columns
