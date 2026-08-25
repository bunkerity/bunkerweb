#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List

from model import Global_values, Metadata, Services, Services_settings, Settings  # type: ignore

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import aliased

from ports import HTTPS_PORT_SETTING  # type: ignore

from .common import DatabaseMixinBase, delete_service_rows, retry_on_transient_db_errors


class DatabaseServicesMixin(DatabaseMixinBase):
    """Multisite service listing and deletion."""

    @retry_on_transient_db_errors
    def get_services(self, *, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services from the database"""
        services = []
        with self._db_session() as session:
            # Fetch all services with their USE_TEMPLATE, SECURITY_MODE and SERVER_TYPE settings
            # in a single optimized query. This avoids N+1 query problem when loading many
            # services. SERVER_TYPE tells HTTP services apart from stream ones, which callers
            # need to know before offering anything that only applies to one of the two.
            template_alias = aliased(Services_settings)
            security_mode_alias = aliased(Services_settings)
            server_type_alias = aliased(Services_settings)

            stmt = (
                select(
                    Services.id,
                    Services.method,
                    Services.is_draft,
                    Services.creation_date,
                    Services.last_update,
                    template_alias.value.label("template"),
                    security_mode_alias.value.label("security_mode"),
                    server_type_alias.value.label("server_type"),
                )
                .select_from(Services)
                .outerjoin(template_alias, (Services.id == template_alias.service_id) & (template_alias.setting_id == "USE_TEMPLATE"))
                .outerjoin(security_mode_alias, (Services.id == security_mode_alias.service_id) & (security_mode_alias.setting_id == "SECURITY_MODE"))
                .outerjoin(server_type_alias, (Services.id == server_type_alias.service_id) & (server_type_alias.setting_id == "SERVER_TYPE"))
            )

            if not with_drafts:
                stmt = stmt.where(Services.is_draft == False)  # noqa: E712

            db_services = session.execute(stmt).all()

            # Two indexed lookups, once for the whole call rather than once per service, so a
            # caller that ignores `link_port` pays two extra key reads and no N+1.
            service_ports: Dict[str, List[str]] = {}
            for row in session.execute(
                select(Services_settings.service_id, Services_settings.value)
                .where(Services_settings.setting_id == HTTPS_PORT_SETTING)
                .order_by(Services_settings.service_id, Services_settings.suffix)
            ).all():
                if row.value:
                    service_ports.setdefault(row.service_id, []).append(row.value)

            global_ports = [
                row.value
                for row in session.execute(
                    select(Global_values.value).where(Global_values.setting_id == HTTPS_PORT_SETTING).order_by(Global_values.suffix)
                ).all()
                if row.value
            ]
            if not global_ports:
                # No global row means the setting sits at its declared default.
                declared = session.execute(select(Settings.default).where(Settings.id == HTTPS_PORT_SETTING)).scalar()
                global_ports = [declared] if declared else []

        for service in db_services:
            # The port an absolute link to this service must carry, or "" to carry none. Empty for
            # every service that listens where the fleet does -- which is every service on a
            # deployment that does not use per-service ports -- because the rendered port is not
            # the published one there (the images publish 80:8080 / 443:8443).
            own_ports = service_ports.get(service.id, [])
            link_port = own_ports[0] if own_ports and own_ports != global_ports else ""
            services.append(
                {
                    "id": service.id,
                    "method": service.method,
                    "is_draft": service.is_draft,
                    "creation_date": service.creation_date,
                    "last_update": service.last_update,
                    "template": service.template or "",
                    "security_mode": service.security_mode or "block",
                    "server_type": service.server_type or "http",
                    "link_port": link_port,
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

            delete_service_rows(session, service_ids)

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
