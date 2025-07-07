from datetime import datetime
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from typing import Dict, List, Literal, Optional, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from bcrypt import gensalt, hashpw
from sqlalchemy.orm import joinedload

from Database import Database  # type: ignore
from model import Permissions, Roles, RolesPermissions, RolesUsers, UserColumnsPreferences, UserRecoveryCodes, UserSessions  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for ui_database module")


class UIDatabase(Database):
    # Initialize UIDatabase with logging support and database connection parameters.
    # Extends the base Database class to provide UI-specific database operations with proper logging and session management.
    def __init__(self, logger_instance=None, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        # Use the provided logger or fall back to the module logger
        self.logger = logger_instance or logger
        super().__init__(self.logger, sqlalchemy_string, ui=True, pool=pool, log=log, **kwargs)

    def get_ui_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[UiUsers, dict]]:
        # Get ui user. If username is None, return the first admin user.
        # Returns user object with roles, recovery codes, and column preferences loaded, ensures admin role assignment and default preferences.
        if DEBUG_MODE:
            logger.debug(f"get_ui_user() called with username: {username}, as_dict: {as_dict}")
        
        with self._db_session() as session:
            # Build query based on parameters
            query = session.query(UiUsers)
            query = query.filter_by(username=username) if username else query.filter_by(admin=True)
            query = query.options(joinedload(UiUsers.roles), joinedload(UiUsers.recovery_codes), joinedload(UiUsers.columns_preferences))

            ui_user = query.first()
            if not ui_user:
            if DEBUG_MODE:
                logger.debug(f"No user found for username: {username or 'admin'}")
            return None

        if DEBUG_MODE:
            logger.debug(f"Found user: {ui_user.username}, admin: {ui_user.admin}, has {len(ui_user.roles)} roles")

            # Ensure admin users have the "admin" role
            if ui_user.admin and not self.readonly:
                admin_role_exists = any(role.role_name == "admin" for role in ui_user.roles)

                if not admin_role_exists:
                    if DEBUG_MODE:
                        logger.debug(f"Adding admin role to user: {ui_user.username} (role missing)")
                    
                    # Check if admin role exists, create it if not
                    admin_role = session.query(Roles).filter_by(name="admin").first()
                    if not admin_role:
                        if DEBUG_MODE:
                            logger.debug("Creating admin role with default permissions")
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
                if DEBUG_MODE:
                    logger.debug(f"Adding default column preferences for user: {ui_user.username} ({len(COLUMNS_PREFERENCES_DEFAULTS)} tables)")
                
                for table_name, columns in COLUMNS_PREFERENCES_DEFAULTS.items():
                    session.add(UserColumnsPreferences(user_name=ui_user.username, table_name=table_name, columns=columns))
                session.commit()
                session.refresh(ui_user)

            if not as_dict:
                return ui_user

            user_dict = {
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
            
            if DEBUG_MODE:
                logger.debug(f"Returning user dictionary with {len(user_dict['roles'])} roles and {len(user_dict['recovery_codes'])} recovery codes")
            
            return user_dict

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
        # Create ui user.
        # Validates uniqueness, role existence, and sets up default preferences and recovery codes with comprehensive error checking.
        if DEBUG_MODE:
            logger.debug(f"create_ui_user() called for username: {username}, admin: {admin}, roles: {roles}, has_totp: {totp_secret is not None}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot create user")
                return "The database is read-only, the changes will not be saved"

            if admin and session.query(UiUsers).with_entities(UiUsers.username).filter_by(admin=True).first():
                if DEBUG_MODE:
                    logger.debug("Admin user already exists, cannot create another")
                return "An admin user already exists"

            user = session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first()
            if user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} already exists")
                return f"User {username} already exists"

            for role in roles:
                if not session.query(Roles).with_entities(Roles.name).filter_by(name=role).first():
                    if DEBUG_MODE:
                        logger.debug(f"Role {role} doesn't exist, cannot create user")
                    return f"Role {role} doesn't exist"
                session.add(RolesUsers(user_name=username, role_name=role))
                if DEBUG_MODE:
                    logger.debug(f"Added role {role} to user {username}")

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

            if DEBUG_MODE:
                logger.debug(f"Added user {username} to session with theme: {theme}, language: {language}")

            recovery_code_count = len(totp_recovery_codes or [])
            for code in totp_recovery_codes or []:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            if DEBUG_MODE and recovery_code_count > 0:
                logger.debug(f"Added {recovery_code_count} recovery codes for user {username}")

            for table_name, columns in COLUMNS_PREFERENCES_DEFAULTS.items():
                session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=columns))

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully created user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to create user {username}")
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
        # Update ui user.
        # Handles username changes, TOTP updates, and recovery code refresh when needed with cascading updates for related tables.
        if DEBUG_MODE:
            logger.debug(f"update_ui_user() called for username: {username}, old_username: {old_username}, theme: {theme}")
        
        totp_changed = False
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot update user")
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=old_username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {old_username} doesn't exist")
                return f"User {old_username} doesn't exist"

            if username != old_username:
                if DEBUG_MODE:
                    logger.debug(f"Username change from {old_username} to {username}, updating related tables")
                
                if session.query(UiUsers).with_entities(UiUsers.username).filter_by(username=username).first():
                    return f"User {username} already exists"

                user.username = username

                # Update all related tables with new username
                session.query(RolesUsers).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserRecoveryCodes).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserSessions).filter_by(user_name=old_username).update({"user_name": username})
                session.query(UserColumnsPreferences).filter_by(user_name=old_username).update({"user_name": username})

            totp_changed = user.totp_secret != totp_secret
            if DEBUG_MODE and totp_changed:
                logger.debug(f"TOTP secret changed for user: {username}")

            user.email = email
            user.password = password.decode("utf-8")
            user.totp_secret = totp_secret
            user.method = method
            user.theme = theme
            user.language = language
            user.update_date = datetime.now().astimezone()

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully updated user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to update user {username}")
                return str(e)

        if totp_changed:
            if DEBUG_MODE:
                logger.debug(f"TOTP changed for user {username}, updating recovery codes")
            if totp_recovery_codes:
                self.refresh_ui_user_recovery_codes(username, totp_recovery_codes or [])
            else:
                self.delete_ui_user_recovery_codes(username)

        return ""

    def delete_ui_user(self, username: str) -> str:
        # Delete ui user.
        # Performs cascading deletion to maintain database consistency and remove all user traces from the system.
        if DEBUG_MODE:
            logger.debug(f"delete_ui_user() called for username: {username}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot delete user")
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            # Delete all user-related data in proper order
            roles_deleted = session.query(RolesUsers).filter_by(user_name=username).delete()
            codes_deleted = session.query(UserRecoveryCodes).filter_by(user_name=username).delete()
            prefs_deleted = session.query(UserColumnsPreferences).filter_by(user_name=username).delete()
            session.delete(user)

            if DEBUG_MODE:
                logger.debug(f"Deleted {roles_deleted} roles, {codes_deleted} recovery codes, {prefs_deleted} preferences for user {username}")

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully deleted user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to delete user {username}")
                return str(e)

        return ""

    def mark_ui_user_login(self, username: str, date: datetime, ip: str, user_agent: str) -> Union[str, int]:
        # Mark ui user login.
        # Creates new session entry and returns session ID for tracking user activity and security monitoring.
        if DEBUG_MODE:
            logger.debug(f"mark_ui_user_login() called for username: {username}, ip: {ip}, user_agent: {user_agent[:50]}...")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot mark login")
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
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
                if DEBUG_MODE:
                    logger.debug(f"Created session {session_id} for user: {username}")
                return session_id
            except BaseException as e:
                logger.exception(f"Failed to mark login for user {username}")
                return str(e)

    def mark_ui_user_access(self, session_id: int, date: datetime) -> str:
        # Mark ui user access.
        # Maintains session activity records for security and audit purposes, enables session timeout detection.
        if DEBUG_MODE:
            logger.debug(f"mark_ui_user_access() called for session_id: {session_id}, timestamp: {date}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot mark access")
                return "The database is read-only, the changes will not be saved"

            user_session = session.query(UserSessions).filter_by(id=session_id).first()
            if not user_session:
                if DEBUG_MODE:
                    logger.debug(f"Session {session_id} doesn't exist")
                return f"Session {session_id} doesn't exist"

            user_session.last_activity = date

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Updated last activity for session: {session_id}")
            except BaseException as e:
                logger.exception(f"Failed to mark access for session {session_id}")
                return str(e)

        return ""

    def create_ui_role(self, name: str, description: str, permissions: List[str]) -> str:
        # Create ui role.
        # Validates role uniqueness and creates associated permission mappings with automatic permission creation if needed.
        if DEBUG_MODE:
            logger.debug(f"create_ui_role() called for role: {name}, permissions: {permissions}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot create role")
                return "The database is read-only, the changes will not be saved"

            if session.query(Roles).with_entities(Roles.name).filter_by(name=name).first():
                if DEBUG_MODE:
                    logger.debug(f"Role {name} already exists")
                return f"Role {name} already exists"

            session.add(Roles(name=name, description=description, update_datetime=datetime.now().astimezone()))
            if DEBUG_MODE:
                logger.debug(f"Added role {name} to session")

            for permission in permissions:
                if not session.query(Permissions).with_entities(Permissions.name).filter_by(name=permission).first():
                    session.add(Permissions(name=permission))
                    if DEBUG_MODE:
                        logger.debug(f"Created new permission: {permission}")
                session.add(RolesPermissions(role_name=name, permission_name=permission))

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully created role: {name}")
            except BaseException as e:
                logger.exception(f"Failed to create role {name}")
                return str(e)

        return ""

    def get_ui_roles(self, *, as_dict: bool = False) -> Union[str, List[Union[Roles, dict]]]:
        # Get ui roles.
        # Returns roles as objects or dictionaries based on as_dict parameter, includes comprehensive permission mapping.
        if DEBUG_MODE:
            logger.debug(f"get_ui_roles() called with as_dict: {as_dict}")
        
        with self._db_session() as session:
            try:
                roles = session.query(Roles).with_entities(Roles.name, Roles.description, Roles.update_datetime).all()
                if not as_dict:
                    if DEBUG_MODE:
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

                    permission_count = 0
                    for permission in session.query(RolesPermissions).with_entities(RolesPermissions.permission_name).filter_by(role_name=role.name):
                        role_data["permissions"].append(permission.permission_name)
                        permission_count += 1

                    if DEBUG_MODE:
                        logger.debug(f"Role {role.name} has {permission_count} permissions")
                    roles_data.append(role_data)

                if DEBUG_MODE:
                    logger.debug(f"Returning {len(roles_data)} roles as dictionaries")
                return roles_data
            except BaseException as e:
                logger.exception("Failed to get UI roles")
                return str(e)

    def refresh_ui_user_recovery_codes(self, username: str, codes: List[str]) -> str:
        # Refresh ui user recovery codes.
        # Hashes codes before storage and ensures only valid codes are accepted, removes all existing codes first.
        if DEBUG_MODE:
            logger.debug(f"refresh_ui_user_recovery_codes() called for username: {username}, code count: {len(codes)}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot refresh recovery codes")
                return "The database is read-only, the changes will not be saved"

            if not codes:
                if DEBUG_MODE:
                    logger.debug("No recovery codes provided")
                return "No recovery codes provided"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()
            if DEBUG_MODE:
                logger.debug(f"Cleared existing recovery codes for user: {username}")

            for code in codes:
                session.add(UserRecoveryCodes(user_name=username, code=hashpw(code.encode("utf-8"), gensalt(rounds=10)).decode("utf-8")))

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully refreshed {len(codes)} recovery codes for user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to refresh recovery codes for user {username}")
                return str(e)

        return ""

    # Remove all recovery codes for specified user.
    # Used when disabling TOTP or cleaning up authentication data, ensures complete removal from database.
    def delete_ui_user_recovery_codes(self, username: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"delete_ui_user_recovery_codes() called for username: {username}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot delete recovery codes")
                return "The database is read-only, the changes will not be saved"

            session.query(UserRecoveryCodes).filter_by(user_name=username).delete()

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully deleted all recovery codes for user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to delete recovery codes for user {username}")
                return str(e)

        return ""

    # Get list of role names assigned to specified user.
    # Returns role names for authorization and permission checking, used for access control validation.
    def get_ui_user_roles(self, username: str) -> List[str]:
        if DEBUG_MODE:
            logger.debug(f"get_ui_user_roles() called for username: {username}")
        
        with self._db_session() as session:
            roles = [role.role_name for role in session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)]
            if DEBUG_MODE:
                logger.debug(f"User {username} has roles: {roles}")
            return roles

    # Get list of permission names for specified role.
    # Returns permissions to determine role capabilities and access levels, essential for RBAC implementation.
    def get_ui_role_permissions(self, role_name: str) -> List[str]:
        if DEBUG_MODE:
            logger.debug(f"get_ui_role_permissions() called for role: {role_name}")
        
        with self._db_session() as session:
            permissions = [
                permission.permission_name
                for permission in session.query(RolesPermissions).with_entities(RolesPermissions.permission_name).filter_by(role_name=role_name)
            ]
            if DEBUG_MODE:
                logger.debug(f"Role {role_name} has permissions: {permissions}")
            return permissions

    # Get list of hashed recovery codes for specified user.
    # Returns stored recovery codes for TOTP verification processes, codes are bcrypt hashed for security.
    def get_ui_user_recovery_codes(self, username: str) -> List[str]:
        if DEBUG_MODE:
            logger.debug(f"get_ui_user_recovery_codes() called for username: {username}")
        
        with self._db_session() as session:
            codes = [code.code for code in session.query(UserRecoveryCodes).with_entities(UserRecoveryCodes.code).filter_by(user_name=username)]
            if DEBUG_MODE:
                logger.debug(f"User {username} has {len(codes)} recovery codes")
            return codes

    # Get aggregated list of all permissions for user based on assigned roles.
    # Combines permissions from all user roles for comprehensive authorization checking, removes duplicates automatically.
    def get_ui_user_permissions(self, username: str) -> List[str]:
        if DEBUG_MODE:
            logger.debug(f"get_ui_user_permissions() called for username: {username}")
        
        with self._db_session() as session:
            query = session.query(RolesUsers).with_entities(RolesUsers.role_name).filter_by(user_name=username)

        permissions = []
        for role in query:
            permissions.extend(self.get_ui_role_permissions(role.role_name))
        
        unique_permissions = list(set(permissions))
        if DEBUG_MODE:
            logger.debug(f"User {username} has {len(unique_permissions)} unique permissions")
        return unique_permissions

    # Consume and remove recovery code after successful TOTP verification.
    # Ensures recovery codes are single-use for security purposes, prevents replay attacks and code reuse.
    def use_ui_user_recovery_code(self, username: str, hashed_code: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"use_ui_user_recovery_code() called for username: {username}")
        
        with self._db_session() as session:
            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            recovery_code = session.query(UserRecoveryCodes).filter_by(user_name=username, code=hashed_code).first()
            if not recovery_code:
                if DEBUG_MODE:
                    logger.debug(f"Invalid recovery code for user: {username}")
                return "Invalid recovery code"

            session.delete(recovery_code)

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully used recovery code for user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to use recovery code for user {username}")
                return str(e)

        return ""

    # Delete all user sessions except the most recent one.
    # Maintains only current session while cleaning up old session data, useful for security and storage management.
    def delete_ui_user_old_sessions(self, username: str) -> str:
        if DEBUG_MODE:
            logger.debug(f"delete_ui_user_old_sessions() called for username: {username}")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot delete sessions")
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            sessions_to_delete = session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc()).offset(1).all()
            for session_to_delete in sessions_to_delete:
                session.delete(session_to_delete)

            if DEBUG_MODE:
                logger.debug(f"Found {len(sessions_to_delete)} old sessions to delete for user: {username}")

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully deleted {len(sessions_to_delete)} old sessions for user: {username}")
            except BaseException as e:
                logger.exception(f"Failed to delete old sessions for user {username}")
                return str(e)

        return ""

    # Update user's column visibility preferences for specified table.
    # Customizes UI display settings per user and table for better user experience, maintains individual user preferences.
    def update_ui_user_columns_preferences(self, username: str, table_name: str, columns: Dict[str, bool]) -> str:
        if DEBUG_MODE:
            logger.debug(f"update_ui_user_columns_preferences() called for username: {username}, table: {table_name}, columns: {len(columns)} settings")
        
        with self._db_session() as session:
            if self.readonly:
                if DEBUG_MODE:
                    logger.debug("Database is read-only, cannot update column preferences")
                return "The database is read-only, the changes will not be saved"

            user = session.query(UiUsers).filter_by(username=username).first()
            if not user:
                if DEBUG_MODE:
                    logger.debug(f"User {username} doesn't exist")
                return f"User {username} doesn't exist"

            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                if DEBUG_MODE:
                    logger.debug(f"Table {table_name} doesn't exist")
                return f"Table {table_name} doesn't exist"

            columns_preferences.columns = columns

            try:
                session.commit()
                if DEBUG_MODE:
                    logger.debug(f"Successfully updated column preferences for user {username}, table: {table_name}")
            except BaseException as e:
                logger.exception(f"Failed to update column preferences for user {username}")
                return str(e)

        return ""

    # Get user's column visibility preferences for specified table with default fallback.
    # Returns column settings for UI customization or creates defaults if missing, ensures consistent user experience.
    def get_ui_user_columns_preferences(self, username: str, table_name: str) -> Dict[str, bool]:
        if DEBUG_MODE:
            logger.debug(f"get_ui_user_columns_preferences() called for username: {username}, table: {table_name}")
        
        with self._db_session() as session:
            columns_preferences = session.query(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).first()
            if not columns_preferences:
                default_columns = COLUMNS_PREFERENCES_DEFAULTS.get(table_name, {})
                if DEBUG_MODE:
                    logger.debug(f"No preferences found for {username}/{table_name}, using {len(default_columns)} default settings")
                
                if not self.readonly and session.query(UiUsers).filter_by(username=username).first():
                    session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=default_columns))
                    session.commit()
                    if DEBUG_MODE:
                        logger.debug(f"Created default column preferences for {username}/{table_name}")
                return default_columns

            if DEBUG_MODE:
                logger.debug(f"Retrieved {len(columns_preferences.columns)} column preferences for {username}/{table_name}")
            return columns_preferences.columns
