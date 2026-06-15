#!/usr/bin/env python3
from datetime import datetime
from typing import Optional, Union

from model import API_users, API_permissions  # type: ignore

from sqlalchemy import select, update

from db_methods.common import DatabaseMixinBase  # type: ignore


class APIUsersMethodsMixin(DatabaseMixinBase):
    """API user accessors respecting API models.

    Note: Method signatures keep UI-compatible parameters for callers,
    but only API model fields are used/stored.
    """

    # API-convention methods
    def get_api_user(self, *, username: Optional[str] = None, as_dict: bool = False) -> Optional[Union[API_users, dict]]:
        """Get API user. If username is None, return the first admin user."""
        with self._db_session() as session:
            stmt = select(API_users)
            stmt = stmt.filter_by(username=username) if username else stmt.filter_by(admin=True)

            api_user = session.scalars(stmt.limit(1)).first()
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

            if admin and session.execute(select(API_users.username).filter_by(admin=True).limit(1)).first():
                return "An admin user already exists"

            user = session.execute(select(API_users.username).filter_by(username=username).limit(1)).first()
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
            return session.scalars(select(API_users).limit(1)).first() is not None

    def list_api_users(self):
        """Return list of (username, admin) for all API users."""
        with self._db_session() as session:
            rows = session.execute(select(API_users.username, API_users.admin)).all()
            return [(u, bool(a)) for (u, a) in rows]

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

            user = session.scalars(select(API_users).filter_by(username=old_username).limit(1)).first()
            if not user:
                return f"User {old_username} doesn't exist"

            # Handle rename if needed
            if username != old_username:
                if session.execute(select(API_users.username).filter_by(username=username).limit(1)).first():
                    return f"User {username} already exists"

                user.username = username

                # Update related permissions ownership
                session.execute(update(API_permissions).filter_by(api_user=old_username).values(api_user=username))

            user.password = password.decode("utf-8")
            user.method = method
            user.update_date = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
