#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List

from model import Global_values, Metadata, Plugins, Services, Services_settings, Settings  # type: ignore

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import aliased

from default_server import DEFAULT_SERVER_ID, DEFAULT_SERVER_METHOD, DEFAULT_SERVER_SEEDED_SETTINGS  # type: ignore
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

    @staticmethod
    def _stored_multisite(session) -> str:
        """The effective global MULTISITE value, read straight from the tables.

        `get_config` cannot always answer this and the difference is load-bearing: `config_read`
        force-adds MULTISITE to a filtered query only when `global_only` is False
        (`config_read.py:112-113`), so a `global_only=True, filtered_settings=("SERVER_NAME",)` read
        -- the shape the UI's service-exists check uses -- carries no MULTISITE key at all and would
        read every deployment as single-site.

        No override row means the effective value IS the setting's default, because `config_save`
        never stores a value equal to it -- which is also why "absent" and "no" are the same state.

        Known limit: a MULTISITE coming from a global TEMPLATE layer (`Template_settings`) is
        resolved by `get_config` and invisible here. No shipped template sets MULTISITE, and the
        callers only fall back to this when `get_config` cannot answer, but a template that did would
        read as single-site.
        """
        value = session.scalar(select(Global_values.value).where(Global_values.setting_id == "MULTISITE", Global_values.suffix == 0))
        if value is None:
            value = session.scalar(select(Settings.default).where(Settings.id == "MULTISITE"))
        return value or "no"

    def _default_server_is_wanted(self, session) -> bool:
        """Whether this deployment is multisite, or has not said yet.

        Three-valued on purpose -- see :meth:`seed_default_server_service` for why "MULTISITE is
        absent" cannot be read as "single-site" before the scheduler's first pass.
        """
        metadata = session.get(Metadata, 1)
        if metadata is None or not metadata.first_config_saved:
            return True

        return self._stored_multisite(session) == "yes"

    @retry_on_transient_db_errors
    def is_multisite(self) -> bool:
        """Is this deployment in multisite mode?

        One scalar lookup. ``get_config(global_only=True, filtered_settings=("MULTISITE",))`` answers
        the same question but scans ``bw_services`` to rebuild ``SERVER_NAME`` on the way, and the
        caller that needs this most -- ``GET /services`` -- is the hottest endpoint the web UI has.
        """
        with self._db_session() as session:
            return self._stored_multisite(session) == "yes"

    @retry_on_transient_db_errors
    def seed_default_server_service(self) -> str:
        """Create the reserved ``default-server`` row if it is not there yet. Idempotent.

        The default server -- the block that answers every request matching no configured service --
        is configured through a permanent pseudo-service rather than through the global settings, so
        it needs exactly one row in ``bw_services``. Called at API startup (the API owns the
        database) on every boot, which is what gives an UPGRADED database the row without a
        migration: the row is data, not schema, and ``methods_enum`` gains no value
        (``DEFAULT_SERVER_METHOD`` reuses ``wizard``, the only existing value that is both editable
        and already undeletable).

        Three settings rows ARE seeded with it (PO ruling of 2026-09-03), and only these three:
        ``DEFAULT_SERVER_SEEDED_SETTINGS``. The default server now RUNS the curated plugin subset in
        ``set``/``access``/``header``, unconditionally, so a row with no rows of its own would take
        the GLOBAL values -- and two of those change what an upgraded deployment answers to
        legitimate catch-all traffic: a 301 to https from ``ssl:access``, and a whitelist chain that
        was skipped here until now. The seeded values pin both back to what the block did before;
        everything else (bans, headers, ACME, the 405 on a method outside ``ALLOWED_METHODS``) is
        deliberately left at the global value, per the same ruling.

        Written ONLY when the row has none of its own, so an operator's later edit is never
        overwritten -- including an edit that sets one of these three back to ``yes``.

        ON CREATION, and only there. Not "while the row has no settings of its own": a value equal to
        its setting default is not stored at all (``config_save``), so an operator who sets all three
        back to ``yes``/``no`` leaves the row with no rows again -- and a "top it up when it is
        empty" rule would put the seeds back on the next boot, over the top of exactly the edit this
        promises not to touch.

        The cost of that choice is on the FRESH-install path only: ``bw_settings`` is the scheduler's
        ``init_tables`` and the API's lifespan can win the race against it, and the FK on
        ``bw_services_settings.setting_id`` means the seeds cannot be written before it. The row is
        still created (that needs nothing but ``bw_services``) and simply carries no seeds -- a new
        deployment has no previous behaviour to preserve. On the UPGRADE path, the one the ruling is
        about, ``bw_settings`` is already populated from the previous version and the first boot
        seeds.

        MULTISITE-ONLY (PO ruling of 2026-09-06). The default server is configurable through this row
        only where the per-site machinery exists: ``config_read`` materialises ``<service>_<SETTING>``
        rows and ``helpers.lua`` builds ``variables[<server>]`` tables under ``MULTISITE=yes`` and
        nowhere else, so a row created on a single-site deployment would be a page whose settings
        resolve to the globals -- inert, and it would put the reserved id in that deployment's
        ``SERVER_NAME``. On ``MULTISITE=no`` the whole feature therefore stands down and the default
        block behaves exactly as it did in 1.6.

        "Not multisite" is decided on ``first_config_saved`` as well as on the MULTISITE value,
        because the value alone cannot answer the question early enough. ``config_save`` never
        stores a global value equal to its default and MULTISITE defaults to ``no``, so an ABSENT
        row means either "single-site" or "nothing has written the configuration yet" -- and the
        second state is the normal one when this runs on a fresh install: the scheduler's entrypoint
        pre-initialises the database (``save_config.py --init``, which sets
        ``metadata.is_initialized`` and exits BEFORE any global value is written), and
        ``is_initialized`` is the only thing the API's gunicorn pre-fork hook waits on. Reading that
        state as "single-site" would skip the seeding on every fresh multisite install.

        ``first_config_saved`` is the flag that separates them, and it is worth being exact about
        what it means, because it is NOT "save_config ran once": ``config_save.py`` only latches it
        under ``changed=True``, which the scheduler's own generation path does not pass
        (``gen/save_config.py`` saves with ``changed=False``). The latch that fires in practice is
        ``scheduler/main.py`` -> ``checked_changes(["config"])`` -> ``db_methods/metadata.py``, so
        the flag means **the scheduler has completed a configuration pass** -- which is a strictly
        later, and therefore safer, point than the first write of MULTISITE. So: the scheduler has
        been round at least once and MULTISITE is not ``yes`` -> skip; not yet -> seed, and let the
        guards elsewhere (roster strip, runner gate, ``GET /services``, the UI list) keep the row
        invisible if the deployment turns out to be single-site.

        Called from TWO places for the same reason: the API lifespan (``api/app/main.py``) and the
        end of ``save_config``. The lifespan alone decides once per API boot, and both of the states
        above can change afterwards -- the first save writes MULTISITE, and an operator can flip it
        to ``yes`` at any later point. The second call site turns that flip into a seeding instead of
        a support ticket. Idempotent, so it costs one primary-key lookup per save.

        Returns an empty string on success (including "already there"), or an error message.
        """
        with self._db_session() as session:
            existing = session.get(Services, DEFAULT_SERVER_ID)
            if existing is not None:
                if existing.method != DEFAULT_SERVER_METHOD:
                    # A row an operator created under the reserved name, before 1.7 reserved it or
                    # through a path that does not go past the API router (autoconf derives ids from
                    # container and ingress names, and a single-label name is ordinary there). It is
                    # NOT adopted: seeding it would silently hand the operator's service to the
                    # default server, and its own `server{}` block is already gone -- `http.conf` and
                    # `stream.conf` drop the reserved id from their roster loops by name, whatever
                    # the method. Loud, and with the exit: the rename and delete refusals lift for a
                    # row in this state (`is_reserved_default_server`).
                    self.logger.error(
                        f"The service {DEFAULT_SERVER_ID!r} already exists with method "
                        f"{existing.method!r} and was NOT adopted as the reserved default server: "
                        f"{DEFAULT_SERVER_ID!r} is a reserved id since 1.7 and that service no longer gets a server "
                        "block of its own. Rename it (the rename refusal does not apply to it) to bring it back."
                    )
                return ""

            if not self._default_server_is_wanted(session):
                self.logger.info(
                    f"MULTISITE is not enabled, skipping the seeding of the reserved {DEFAULT_SERVER_ID!r} service: "
                    "the default server is configurable in multisite mode only."
                )
                return ""

            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            now = datetime.now().astimezone()
            session.add(Services(id=DEFAULT_SERVER_ID, method=DEFAULT_SERVER_METHOD, is_draft=False, creation_date=now, last_update=now))

            # Only the settings the database already knows: the FK is on `bw_settings.id`, which the
            # scheduler populates, and a missing one means "too early" rather than "unknown".
            known = set(session.scalars(select(Settings.id).where(Settings.id.in_(tuple(DEFAULT_SERVER_SEEDED_SETTINGS)))).all())
            for setting_id, value in DEFAULT_SERVER_SEEDED_SETTINGS.items():
                if setting_id in known:
                    session.add(Services_settings(service_id=DEFAULT_SERVER_ID, setting_id=setting_id, value=value, suffix=0, method=DEFAULT_SERVER_METHOD))

            # Same signal a service creation raises in save_config: the roster changed, so every
            # plugin's configuration has to be regenerated. A flag without a fresh timestamp is
            # indistinguishable from the previous one for the scheduler's poll comparison.
            with suppress(ProgrammingError, OperationalError):
                session.execute(
                    update(Plugins).values({Plugins.config_changed: True, Plugins.last_config_change: now}).execution_options(synchronize_session=False)
                )

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    @retry_on_transient_db_errors
    def delete_services(self, service_ids: List[str]) -> str:
        """Hard-delete services and all their related rows (settings, custom configs, job caches).

        Bypasses the method-based protection in ``save_config`` and is intended for callers
        that have already authorised the deletion (e.g. the UI deleting a drafted autoconf
        service). Returns an empty string on success, or an error message.

        The reserved ``default-server`` row is the one thing it will not delete. Defence in depth:
        both production callers refuse it before they get here (the API router's 403 and the UI's
        ``can_delete_service``), but ``save_config`` grew three id-based exclusions for the same
        invariant and this method had none -- and it is the one that bypasses every method check, so
        a future authorised-deletion caller walks straight into it. Judged on the row's METHOD as
        well as its id, so an operator's own service that took the name before 1.7 reserved it stays
        deletable (see :func:`is_reserved_default_server`).
        """
        if not service_ids:
            return ""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            reserved = session.get(Services, DEFAULT_SERVER_ID) if DEFAULT_SERVER_ID in service_ids else None
            if reserved is not None and reserved.method == DEFAULT_SERVER_METHOD:
                return f"{DEFAULT_SERVER_ID} is the reserved default server: it answers requests that match no " "configured service, so it cannot be deleted."

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
