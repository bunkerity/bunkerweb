#!/usr/bin/env python3
from typing import Dict

from sqlalchemy import select

from model import UserColumnsPreferences  # type: ignore

from db_methods.common import DatabaseMixinBase  # type: ignore

from app.models.models import UiUsers
from app.utils import COLUMNS_PREFERENCES_DEFAULTS


class UIPreferencesMethodsMixin(DatabaseMixinBase):
    """Web UI per-user column preferences."""

    def update_ui_user_columns_preferences(self, username: str, table_name: str, columns: Dict[str, bool]) -> str:
        """Update ui user columns preferences."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first()
            if not user:
                return f"User {username} doesn't exist"

            columns_preferences = session.scalars(select(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).limit(1)).first()
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
            columns_preferences = session.scalars(select(UserColumnsPreferences).filter_by(user_name=username, table_name=table_name).limit(1)).first()
            if not columns_preferences:
                default_columns = COLUMNS_PREFERENCES_DEFAULTS.get(table_name, {})
                if not self.readonly and session.scalars(select(UiUsers).filter_by(username=username).limit(1)).first():
                    session.add(UserColumnsPreferences(user_name=username, table_name=table_name, columns=default_columns))
                    session.commit()
                return default_columns

            return columns_preferences.columns
