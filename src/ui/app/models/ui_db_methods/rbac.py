#!/usr/bin/env python3
from datetime import datetime
from typing import List, Union

from bcrypt import gensalt, hashpw
from sqlalchemy import delete, select

from model import Permissions, Roles, RolesPermissions, RolesUsers, UserRecoveryCodes  # type: ignore

from db_methods.common import DatabaseMixinBase  # type: ignore

from app.models.models import UiUsers


class UIRBACMethodsMixin(DatabaseMixinBase):
    """Web UI roles, permissions and recovery-code management."""

    def create_ui_role(self, name: str, description: str, permissions: List[str]) -> str:
        """Create ui role."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            if session.execute(select(Roles.name).filter_by(name=name).limit(1)).first():
                return f"Role {name} already exists"

            session.add(Roles(name=name, description=description, update_datetime=datetime.now().astimezone()))

            for permission in permissions:
                if not session.execute(select(Permissions.name).filter_by(name=permission).limit(1)).first():
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
                roles = session.execute(select(Roles.name, Roles.description, Roles.update_datetime)).all()
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

                    for permission in session.execute(select(RolesPermissions.permission_name).filter_by(role_name=role.name)):
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

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            session.execute(delete(UserRecoveryCodes).filter_by(user_name=username))

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

            session.execute(delete(UserRecoveryCodes).filter_by(user_name=username))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_user_roles(self, username: str) -> List[str]:
        """Get ui user roles."""
        with self._db_session() as session:
            return [role.role_name for role in session.execute(select(RolesUsers.role_name).filter_by(user_name=username))]

    def get_ui_role_permissions(self, role_name: str) -> List[str]:
        """Get ui role permissions."""
        with self._db_session() as session:
            return [permission.permission_name for permission in session.execute(select(RolesPermissions.permission_name).filter_by(role_name=role_name))]

    def get_ui_user_recovery_codes(self, username: str) -> List[str]:
        """Get ui user recovery codes."""
        with self._db_session() as session:
            return [code.code for code in session.execute(select(UserRecoveryCodes.code).filter_by(user_name=username))]

    def get_ui_user_permissions(self, username: str) -> List[str]:
        """Get ui user permissions."""
        with self._db_session() as session:
            roles = session.execute(select(RolesUsers.role_name).filter_by(user_name=username)).all()

        permissions = []
        for role in roles:
            permissions.extend(self.get_ui_role_permissions(role.role_name))
        return permissions

    def use_ui_user_recovery_code(self, username: str, hashed_code: str) -> str:
        """Use ui user recovery code."""
        with self._db_session() as session:
            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            recovery_code = session.scalars(select(UserRecoveryCodes).filter_by(user_name=username, code=hashed_code).limit(1)).first()
            if not recovery_code:
                return "Invalid recovery code"

            session.delete(recovery_code)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
