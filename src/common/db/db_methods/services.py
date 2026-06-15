#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List

from model import Custom_configs, Jobs_cache, Metadata, Services, Services_settings  # type: ignore

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import aliased

from .common import DatabaseMixinBase, retry_on_transient_db_errors


class DatabaseServicesMixin(DatabaseMixinBase):
    """Multisite service listing and deletion."""

    @retry_on_transient_db_errors
    def get_services(self, *, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services from the database"""
        services = []
        with self._db_session() as session:
            # Fetch all services with their USE_TEMPLATE and SECURITY_MODE settings in a single optimized query
            # This avoids N+1 query problem when loading many services
            template_alias = aliased(Services_settings)
            security_mode_alias = aliased(Services_settings)

            stmt = (
                select(
                    Services.id,
                    Services.method,
                    Services.is_draft,
                    Services.creation_date,
                    Services.last_update,
                    template_alias.value.label("template"),
                    security_mode_alias.value.label("security_mode"),
                )
                .select_from(Services)
                .outerjoin(template_alias, (Services.id == template_alias.service_id) & (template_alias.setting_id == "USE_TEMPLATE"))
                .outerjoin(security_mode_alias, (Services.id == security_mode_alias.service_id) & (security_mode_alias.setting_id == "SECURITY_MODE"))
            )

            if not with_drafts:
                stmt = stmt.where(Services.is_draft == False)  # noqa: E712

            db_services = session.execute(stmt).all()

        for service in db_services:
            services.append(
                {
                    "id": service.id,
                    "method": service.method,
                    "is_draft": service.is_draft,
                    "creation_date": service.creation_date,
                    "last_update": service.last_update,
                    "template": service.template or "",
                    "security_mode": service.security_mode or "block",
                }
            )

        return services

    @retry_on_transient_db_errors
    def delete_services(self, service_ids: List[str]) -> str:
        """Hard-delete services and all their related rows (settings, custom configs, job caches).

        Bypasses the method-based protection in ``save_config`` and is intended for callers
        that have already authorised the deletion (e.g. the UI deleting a drafted autoconf
        service). Returns an empty string on success, or an error message.
        """
        if not service_ids:
            return ""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.execute(delete(Services_settings).where(Services_settings.service_id.in_(service_ids)), execution_options={"synchronize_session": False})
            session.execute(delete(Custom_configs).where(Custom_configs.service_id.in_(service_ids)), execution_options={"synchronize_session": False})
            session.execute(delete(Jobs_cache).where(Jobs_cache.service_id.in_(service_ids)), execution_options={"synchronize_session": False})
            session.execute(delete(Services).where(Services.id.in_(service_ids)), execution_options={"synchronize_session": False})

            with suppress(ProgrammingError, OperationalError):
                metadata = session.get(Metadata, 1)
                if metadata is not None:
                    now = datetime.now().astimezone()
                    metadata.custom_configs_changed = True
                    metadata.last_custom_configs_change = now

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""
