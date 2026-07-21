#!/usr/bin/env python3
from datetime import datetime
from typing import Optional, Union

from model import API_RESOURCE_ENUM, API_PERMISSION_ENUM, API_users, API_permissions  # type: ignore

from sqlalchemy import select

from db_methods.common import DatabaseMixinBase  # type: ignore

# Write permissions whose payload is rendered verbatim into raw nginx / OpenResty Lua
# configuration (custom configs, service variables, uploaded plugins, global settings)
# that runs on the BunkerWeb workers/scheduler. Holding any of these is therefore
# equivalent to full administrative (code-execution) access, so they must never be
# granted to a party that is not trusted as an admin.
ADMIN_EQUIVALENT_PERMISSIONS = frozenset(
    {
        "config_create",
        "config_update",
        "config_delete",
        "service_create",
        "service_update",
        "service_convert",
        "plugin_create",
        "global_config_update",
    }
)


class APIPermissionsMethodsMixin(DatabaseMixinBase):
    """Fine-grained API access control (ACL) for API users."""

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

            user = session.scalars(select(API_users).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            if granted and permission in ADMIN_EQUIVALENT_PERMISSIONS and not user.admin:
                self.logger.warning(
                    f"Granting admin-equivalent permission {permission!r} to non-admin API user {username!r} "
                    f"(resource {resource_type}/{resource_id or '*'}): this permission is code-execution-capable "
                    "— it can write configuration that is rendered into raw nginx/OpenResty Lua. "
                    "Only grant it to a party you trust as an administrator."
                )

            now = datetime.now().astimezone()
            record = session.scalars(
                select(API_permissions).filter_by(api_user=username, resource_type=resource_type, resource_id=resource_id, permission=permission).limit(1)
            ).first()

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

            record = session.scalars(
                select(API_permissions).filter_by(api_user=username, resource_type=resource_type, resource_id=resource_id, permission=permission).limit(1)
            ).first()
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
            stmt = select(API_permissions).filter_by(api_user=username)
            if resource_type is not None:
                stmt = stmt.filter_by(resource_type=resource_type)
            if resource_id is not None:
                stmt = stmt.filter_by(resource_id=resource_id)
            if not include_denied:
                stmt = stmt.filter_by(granted=True)

            rows = session.scalars(stmt).all()

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
            user = session.scalars(select(API_users).filter_by(username=username).limit(1)).first()
            if not user:
                return False
            if bool(user.admin):
                return True

            stmt = select(API_permissions).filter_by(api_user=username, permission=permission, granted=True)

            if resource_type is None:
                return session.scalar(select(stmt.exists())) or False

            stmt = stmt.filter_by(resource_type=resource_type)
            if resource_id is None:
                # Global grant only
                stmt_global = stmt.filter_by(resource_id=None)
                return session.scalar(select(stmt_global.exists())) or False

            # Prefer specific resource grant, fallback to global
            stmt_specific = stmt.filter_by(resource_id=resource_id)
            if session.scalar(select(stmt_specific.exists())):
                return True
            stmt_global = stmt.filter_by(resource_id=None)
            return session.scalar(select(stmt_global.exists())) or False
