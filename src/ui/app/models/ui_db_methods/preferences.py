#!/usr/bin/env python3
from typing import Any, Optional

from sqlalchemy import select

from model import UserPreferences  # type: ignore

from db_methods.common import DatabaseMixinBase  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS


class UIPreferencesMethodsMixin(DatabaseMixinBase):
    """Web UI per-user key/value preferences.

    `key` is a shared namespace: DataTables ids and feature keys live side by side, so
    `COLUMNS_PREFERENCES_DEFAULTS` is consulted only as the fallback for a table id and a
    caller storing anything else passes its own `default`.
    """

    def set_ui_user_preference(self, username: str, key: str, value: Any) -> str:
        """Set one of a ui user's preferences, creating it if it does not exist yet."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            preference = session.scalars(select(UserPreferences).filter_by(user_name=username, key=key).limit(1)).first()
            if not preference:
                # Upsert rather than reject: a feature key has no seeded row to update, and
                # the API-side mixin has always upserted here. Refusing was the odd one out.
                session.add(UserPreferences(user_name=username, key=key, value=value))
            else:
                preference.value = value

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_ui_user_preference(self, username: str, key: str, default: Optional[Any] = None) -> Any:
        """Get one of a ui user's preferences, seeding the stored default on first read."""
        with self._db_session() as session:
            preference = session.scalars(select(UserPreferences).filter_by(user_name=username, key=key).limit(1)).first()
            if not preference:
                fallback = COLUMNS_PREFERENCES_DEFAULTS.get(key, {}) if default is None else default
                if not self.readonly and session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first():
                    session.add(UserPreferences(user_name=username, key=key, value=fallback))
                    session.commit()
                return fallback

            return preference.value
