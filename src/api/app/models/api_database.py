from datetime import datetime
from logging import Logger
from os import sep
from os.path import join
from sys import path as sys_path
from typing import Optional, Union


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

"""
APIDatabase: API-specific user accessors respecting API models.

Note: Method signatures keep UI-compatible parameters for callers,
but only API model fields are used/stored.
"""

from Database import Database  # type: ignore
from model import API_RESOURCE_ENUM, API_PERMISSION_ENUM, API_users, API_permissions  # type: ignore


class APIDatabase(Database):
    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, pool: Optional[bool] = None, log: bool = True, **kwargs) -> None:
        super().__init__(logger, sqlalchemy_string, external=True, pool=pool, log=log, **kwargs)

    # API-convention methods
    def get_api_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[API_users, dict]]:
        """Get API user. If username is None, return the first admin user."""
        with self._db_session() as session:
            query = session.query(API_users)
            query = query.filter_by(username=username) if username else query.filter_by(admin=True)

            api_user = query.first()
            if not api_user:
                return None

            if not as_dict:
                return api_user

            return {
                "username": api_user.username,
                "password": api_user.password.encode("utf-8"),
                "method": api_user.method,
                "admin": api_user.admin,
                "creation_date": api_user.creation_date.astimezone(),
                "update_date": api_user.update_date.astimezone(),
            }

    def create_api_user(
        self,
        username: str,
        password: bytes,
        *,
        creation_date: Optional[datetime] = None,
        method: str = "manual",
        admin: bool = False,
    ) -> str:
        """Create API user (API fields only)."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if admin and session.query(API_users).with_entities(API_users.username).filter_by(admin=True).first():
                return "An admin user already exists"

            user = session.query(API_users).with_entities(API_users.username).filter_by(username=username).first()
            if user:
                return f"User {username} already exists"

            current_time = datetime.now().astimezone()
            session.add(
                API_users(
                    username=username,
                    password=password.decode("utf-8"),
                    method=method,
                    admin=admin,
                    creation_date=creation_date or current_time,
                    update_date=current_time,
                )
            )

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def has_api_user(self) -> bool:
        """Return True if at least one API user exists."""
        with self._db_session() as session:
            return session.query(API_users).first() is not None

    def list_api_users(self):
        """Return list of (username, admin) for all API users."""
        with self._db_session() as session:
            rows = session.query(API_users).with_entities(API_users.username, API_users.admin).all()
            return [(u, bool(a)) for (u, a) in rows]

    # --------------------
    # Permissions (ACL)
    # --------------------
    def _allowed_resources(self) -> set:
        """Return the set of allowed resource types if available from the model enum."""
        return set(getattr(API_RESOURCE_ENUM, "enums", []) or [])

    def _allowed_permissions(self) -> set:
        """Return the set of allowed permission names if available from the model enum."""
        return set(getattr(API_PERMISSION_ENUM, "enums", []) or [])

    def grant_api_permission(
        self,
        username: str,
        permission: str,
        *,
        resource_type: str,
        resource_id: Optional[str] = None,
        granted: bool = True,
    ) -> str:
        """Grant or update a specific permission for an API user.

        Creates or updates a row in bw_api_user_permissions for the given
        (user, resource_type, resource_id, permission) with the provided granted flag.
        Returns an empty string on success or an error message on failure.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Validate inputs when possible
            if resource_type not in self._allowed_resources():
                return f"Invalid resource_type: {resource_type}"
            if permission not in self._allowed_permissions():
                return f"Invalid permission: {permission}"

            user = session.query(API_users).filter_by(username=username).first()
            if not user:
                return f"User {username} doesn't exist"

            now = datetime.now().astimezone()
            record = (
                session.query(API_permissions).filter_by(api_user=username, resource_type=resource_type, resource_id=resource_id, permission=permission).first()
            )

            if record:
                record.granted = granted
                record.updated_at = now
            else:
                session.add(
                    API_permissions(
                        api_user=username,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        permission=permission,
                        granted=granted,
                        created_at=now,
                        updated_at=now,
                    )
                )

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def revoke_api_permission(
        self,
        username: str,
        permission: str,
        *,
        resource_type: str,
        resource_id: Optional[str] = None,
        hard_delete: bool = False,
    ) -> str:
        """Revoke a specific permission for an API user.

        If hard_delete is True, delete the row; otherwise, mark granted=False.
        Returns an empty string on success or an error message on failure.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if resource_type not in self._allowed_resources():
                return f"Invalid resource_type: {resource_type}"
            # Permit any permission value but prefer validating known permissions
            if permission not in self._allowed_permissions():
                return f"Invalid permission: {permission}"

            record = (
                session.query(API_permissions).filter_by(api_user=username, resource_type=resource_type, resource_id=resource_id, permission=permission).first()
            )
            if not record:
                return ""

            if hard_delete:
                session.delete(record)
            else:
                record.granted = False
                record.updated_at = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_api_permissions(
        self,
        username: str,
        *,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        as_dict: bool = False,
        include_denied: bool = False,
    ) -> Union[list, dict]:
        """List permissions for an API user.

        Filters by resource_type/resource_id when provided. By default returns only granted permissions unless include_denied=True.
        If as_dict=True, returns a nested mapping: {resource_type: {resource_id or "*": {permission: granted}}}.
        """
        with self._db_session() as session:
            q = session.query(API_permissions).filter_by(api_user=username)
            if resource_type is not None:
                q = q.filter_by(resource_type=resource_type)
            if resource_id is not None:
                q = q.filter_by(resource_id=resource_id)
            if not include_denied:
                q = q.filter_by(granted=True)

            rows = q.all()

            if not as_dict:
                return rows

            result: dict = {}
            for row in rows:
                rtype = row.resource_type
                rid = row.resource_id or "*"
                result.setdefault(rtype, {})
                result[rtype].setdefault(rid, {})
                result[rtype][rid][row.permission] = bool(row.granted)
            return result

    def check_api_permission(
        self,
        username: str,
        permission: str,
        *,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if the user has the given permission.

        - Admin users are always allowed.
        - If resource_type is provided, checks both specific (resource_id) and global (resource_id is NULL) grants.
        - If resource_type is None, checks any grant across resource types for that permission name.
        """
        with self._db_session() as session:
            user = session.query(API_users).filter_by(username=username).first()
            if not user:
                return False
            if bool(user.admin):
                return True

            q = session.query(API_permissions).filter_by(api_user=username, permission=permission, granted=True)

            if resource_type is None:
                return session.query(q.exists()).scalar() or False

            q = q.filter_by(resource_type=resource_type)
            if resource_id is None:
                # Global grant only
                q_global = q.filter_by(resource_id=None)
                return session.query(q_global.exists()).scalar() or False

            # Prefer specific resource grant, fallback to global
            q_specific = q.filter_by(resource_id=resource_id)
            if session.query(q_specific.exists()).scalar():
                return True
            q_global = q.filter_by(resource_id=None)
            return session.query(q_global.exists()).scalar() or False

    def update_api_user(
        self,
        username: str,
        password: bytes,
        *,
        old_username: Optional[str] = None,
        method: str = "manual",
    ) -> str:
        """Update API user (API fields only)."""
        old_username = old_username or username
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(API_users).filter_by(username=old_username).first()
            if not user:
                return f"User {old_username} doesn't exist"

            # Handle rename if needed
            if username != old_username:
                if session.query(API_users).with_entities(API_users.username).filter_by(username=username).first():
                    return f"User {username} already exists"

                user.username = username

                # Update related permissions ownership
                session.query(API_permissions).filter_by(api_user=old_username).update({"api_user": username})

            user.password = password.decode("utf-8")
            user.method = method
            user.update_date = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
