#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union

from model import Metadata, Plugins  # type: ignore

from sqlalchemy import select, text, update

from .common import DatabaseMixinBase, retry_on_transient_db_errors


class DatabaseMetadataMixin(DatabaseMixinBase):
    """Database metadata, versioning and change-flag methods."""

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if metadata:
                    metadata.version = version
                    metadata.integration = integration
                    # initialize_db() means the schema is ready: ensure the flag is set even
                    # on an existing row (e.g. a partial prior init left it False) so the API's
                    # DB-init wait cannot deadlock against the scheduler on upgrade.
                    metadata.is_initialized = True
                else:
                    session.add(
                        Metadata(
                            is_initialized=True,
                            first_config_saved=False,
                            scheduler_first_start=True,
                            version=version,
                            integration=integration,
                        )
                    )
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_version(self) -> str:
        """Get the database version"""
        with self._db_session() as session:
            try:
                metadata = session.execute(select(Metadata.version).filter_by(id=1).limit(1)).first()
                if metadata:
                    return metadata.version
                return "1.7.0~beta"
            except BaseException as e:
                return f"Error: {e}"

    @retry_on_transient_db_errors
    def get_metadata(self) -> Dict[str, Any]:
        """Get the metadata from the database"""
        data = {
            "is_initialized": False,
            "is_pro": False,
            "pro_license": "",
            "pro_expire": None,
            "pro_status": "invalid",
            "pro_services": 0,
            "non_draft_services": 0,
            "pro_overlapped": False,
            "last_pro_check": None,
            "force_pro_update": False,
            "failover": False,
            "failover_message": "",
            "first_config_saved": False,
            "autoconf_loaded": False,
            "scheduler_first_start": True,
            "custom_configs_changed": False,
            "external_plugins_changed": False,
            "pro_plugins_changed": False,
            "instances_changed": False,
            "plugins_config_changed": {},
            "last_custom_configs_change": None,
            "last_external_plugins_change": None,
            "last_pro_plugins_change": None,
            "last_instances_change": None,
            "reload_ui_plugins": False,
            "integration": "unknown",
            "version": "1.7.0~beta",
            "database_version": "Unknown",  # ? Extracted from the database
            "default": True,  # ? Extra field to know if the returned data is the default one
        }
        with self._db_session() as session:
            with suppress(BaseException):
                database = self.database_uri.split(":")[0].split("+")[0]
                if database == "sqlite":
                    sql_query = text("SELECT sqlite_version()")
                elif database == "oracle":
                    # Use PRODUCT_COMPONENT_VERSION which is more accessible than v$instance
                    sql_query = text("SELECT version FROM PRODUCT_COMPONENT_VERSION WHERE PRODUCT LIKE 'Oracle%' AND ROWNUM = 1")
                else:
                    sql_query = text("SELECT VERSION()")

                try:
                    data["database_version"] = (session.execute(sql_query).first() or ["unknown"])[0]
                except Exception:
                    data["database_version"] = "Unknown (access restricted)"
                metadata = session.scalars(select(Metadata).filter_by(id=1).limit(1)).first()
                if metadata:
                    for key in data.copy():
                        if hasattr(metadata, key) and key not in ("database_version", "default"):
                            data[key] = getattr(metadata, key)
                    data["default"] = False

                data["plugins_config_changed"] = {
                    plugin.id: plugin.last_config_change
                    for plugin in session.execute(select(Plugins.id, Plugins.last_config_change).filter_by(config_changed=True)).all()
                }

        return data

    def set_metadata(self, data: Dict[str, Any]) -> str:
        """Set the metadata values"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                for key, value in data.items():
                    if not hasattr(metadata, key):
                        self.logger.warning(f"Metadata key {key} does not exist")
                        continue

                    setattr(metadata, key, value)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def checked_changes(
        self,
        changes: Optional[List[str]] = None,
        plugins_changes: Optional[Union[Literal["all"], Set[str], List[str], Tuple[str]]] = None,
        value: Optional[bool] = False,
    ) -> str:
        """Set changed bit for config, custom configs, instances and plugins"""
        changes = changes or ["config", "custom_configs", "external_plugins", "pro_plugins", "instances", "ui_plugins"]
        plugins_changes = plugins_changes or set()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.get(Metadata, 1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                current_time = datetime.now().astimezone()

                if "config" in changes:
                    if not metadata.first_config_saved:
                        metadata.first_config_saved = True
                if "custom_configs" in changes:
                    metadata.custom_configs_changed = value
                    metadata.last_custom_configs_change = current_time
                if "external_plugins" in changes:
                    metadata.external_plugins_changed = value
                    metadata.last_external_plugins_change = current_time
                if "pro_plugins" in changes:
                    metadata.pro_plugins_changed = value
                    metadata.last_pro_plugins_change = current_time
                if "instances" in changes:
                    metadata.instances_changed = value
                    metadata.last_instances_change = current_time
                if "ui_plugins" in changes:
                    metadata.reload_ui_plugins = value

                if plugins_changes:
                    if plugins_changes == "all":
                        session.execute(update(Plugins).values({Plugins.config_changed: value, Plugins.last_config_change: current_time}))
                    else:
                        session.execute(
                            update(Plugins)
                            .where(Plugins.id.in_(plugins_changes))
                            .values({Plugins.config_changed: value, Plugins.last_config_change: current_time})
                        )

                session.commit()
            except BaseException as e:
                return str(e)

        return ""
