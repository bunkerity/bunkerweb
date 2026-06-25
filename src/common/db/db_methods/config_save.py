#!/usr/bin/env python3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from model import Custom_configs, Global_values, Jobs_cache, Metadata, Plugins, Services, Services_settings, Settings, Template_settings  # type: ignore

from common_utils import normalize_check_value, normalize_list_value  # type: ignore
from unit_parser import normalize_unit  # type: ignore

from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase


@dataclass
class _SaveConfigContext:
    """Shared, phase-populated state threaded through the save_config helpers.

    Mirrors the variables the original nested closures captured from the
    enclosing save_config scope. ``config`` and ``db_config`` are the *same*
    dict objects save_config works on (config is mutated in place by the
    reconciliation phase via ``pop``, exactly like before). ``template``,
    ``drafts`` and the lookup dicts are filled in as the corresponding phases
    run, matching the point where the original code defined them.
    """

    config: Dict[str, Any]
    db_config: Dict[str, Any]
    method: str
    normalized_file_names: Dict[str, str]
    # NOTE: typed Any on purpose — the original multisite template-collection loop
    # rebinds the enclosing ``template`` variable to the last Template_settings row
    # (see _sc_collect_multisite_data); that behavior is preserved verbatim.
    template: Any = ""
    drafts: Set[str] = field(default_factory=set)
    settings_dict: Dict[str, dict] = field(default_factory=dict)
    existing_service_settings_dict: Dict[Tuple[str, str, int], dict] = field(default_factory=dict)
    templates: Dict[Any, Dict[Tuple[str, int], Any]] = field(default_factory=dict)


def _get_setting_file_name(
    ctx: _SaveConfigContext, setting_type: str, original_key: str, value_changed: bool, current_file_name: str = ""
) -> Tuple[Optional[str], bool]:
    if setting_type != "file":
        return None, False

    if original_key in ctx.normalized_file_names:
        file_name = ctx.normalized_file_names[original_key]
        return file_name or None, file_name != current_file_name

    # If value was edited without a file name metadata, clear stale file references.
    if value_changed and current_file_name:
        return None, True

    return None, False


def _is_default_value(
    ctx: _SaveConfigContext, val: str, key: str, setting: dict, template_default: Optional[str] = None, suffix: int = 0, is_global: bool = False
) -> bool:
    """
    Determines whether the provided value is considered the default value.
    This function checks the value 'val' against an expected default based on several conditions:
    1. If a 'template_default' is provided (i.e., not None), then the expected default is
        this template value, and the function returns True only if 'val' exactly matches it.
    2. If 'template_default' is None:
        - If the configuration key 'key' is not present in both 'config' and 'db_config',
          then the expected default is defined by setting["default"].
        - Otherwise, the expected default should be one of the values associated with 'key'
          in either 'config' or 'db_config'.
    """
    if template_default is not None:
        return val == template_default

    if (is_global and not suffix) or (key not in ctx.config and key not in ctx.db_config):
        return val == setting["default"]

    if is_global:
        return False

    # Acceptable values are the ones from either config or db_config.
    return (
        val in (ctx.config.get(key), ctx.db_config.get(key)) if not suffix else val in (ctx.config.get(f"{key}_{suffix}"), ctx.db_config.get(f"{key}_{suffix}"))
    )


def _check_value(ctx: _SaveConfigContext, key: str, value: str, setting: dict, template_default: Optional[str], suffix: int, is_global: bool = False) -> bool:
    """
    Determine if a configuration value should be considered default.

    Immediately returns False for the key "SERVER_NAME". For non-suffix values, if a template default
    is provided, the value must match it; otherwise, the value must satisfy is_default_value using the
    original key. For suffix values, if the base value (using key) is not default, the check passes;
    otherwise, the suffix value must also be default (using original_key).
    """
    if key == "SERVER_NAME":
        return False

    return _is_default_value(ctx, value, key, setting, template_default, suffix, is_global)


def _canonicalize_stored_value(setting_type: Optional[str], value: Any, separator: Optional[str] = " ") -> Any:
    """Canonicalize a value to its stored form by setting type (mirrors
    ``Configurator.__canonicalize_value``): check -> yes/no, size/duration -> NGINX unit
    form, multivalue/multiselect -> trimmed items. Invalid size/duration values are left
    unchanged so the stored value stays whatever was provided. Other types untouched."""
    if setting_type == "check":
        return normalize_check_value(value)
    if setting_type in ("size", "duration"):
        canonical = normalize_unit(setting_type, value)
        return canonical if canonical is not None else value
    if setting_type in ("multiselect", "multivalue"):
        return normalize_list_value(value, separator or " ")
    return value


class DatabaseConfigSaveMixin(DatabaseMixinBase):
    """Whole-configuration persistence (save_config)."""

    def save_config(
        self,
        config: Dict[str, Any],
        method: str,
        changed: Optional[bool] = True,
        file_names: Optional[Dict[str, str]] = None,
        *,
        skip_service_management: bool = False,
        disable_cleanup: bool = False,
    ) -> Union[str, Set[str]]:
        """Save the config in the database.

        Args:
            skip_service_management: When True, the entire service-management block is
                                     skipped — service settings cleanup, the SERVER_NAME
                                     reconciliation that adds/draftifies/deletes Services
                                     rows, and the multisite per-service settings pass.
                                     Use this when the caller only intends to update
                                     global settings and must not touch any service rows.
                                     The historical name was ``global_only`` which was
                                     misleading: it does not restrict input to global
                                     settings, it only disables the service-management
                                     side-effects.
        """
        to_put = []
        to_update = []
        to_delete = []
        changed_plugins = set()
        changed_services = False
        service_template_change = False

        db_config = {}
        if method == "autoconf":
            db_config = self.get_non_default_settings(with_drafts=True)

        normalized_file_names = {k: ("" if v is None else v.strip()) for k, v in (file_names or {}).items()}

        ctx = _SaveConfigContext(config=config, db_config=db_config, method=method, normalized_file_names=normalized_file_names)

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            self.logger.debug(f"Saving config for method {method}")

            drafted_service_ids = self._sc_compute_drafted_service_ids(session, ctx, skip_service_management, disable_cleanup)

            refused, global_settings_to_delete, ret_changed_services = self._sc_cleanup_global_settings(session, ctx, changed_plugins)
            if ret_changed_services:
                changed_services = True
            if refused:
                # Scheduler 100%-wipe data-loss guard tripped — abort with the
                # plugins collected so far, exactly like the original early return.
                return changed_plugins

            refused, service_settings_to_delete, ret_changed_services, ret_service_template_change = self._sc_cleanup_service_settings(
                session, ctx, skip_service_management, drafted_service_ids, changed_plugins
            )
            if ret_changed_services:
                changed_services = True
            if ret_service_template_change:
                service_template_change = True
            if refused:
                # ui/api whole-service-wipe data-loss guard tripped — abort with the
                # plugins collected so far, exactly like the original early return.
                return changed_plugins

            if config:
                config.pop("DATABASE_URI", None)

                ctx.template = config.get("USE_TEMPLATE", "")

                if not skip_service_management:
                    refused, services, db_ids, drafts, ret_changed_services, ret_service_template_change = self._sc_reconcile_services(
                        session, ctx, disable_cleanup, to_put, to_update
                    )
                    if ret_changed_services:
                        changed_services = True
                    if ret_service_template_change:
                        service_template_change = True
                    if refused:
                        # Empty-SERVER_NAME data-loss guards tripped — abort with the
                        # plugins collected so far, exactly like the original early returns.
                        return changed_plugins
                    ctx.drafts = drafts

                if not skip_service_management and config.get("MULTISITE", "no") == "yes":
                    self.logger.debug("Checking if the multisite settings have changed")

                    service_configs, global_config = self._sc_split_multisite_config(ctx, services, db_ids)

                    self._sc_collect_multisite_data(session, ctx)

                    # Use ThreadPoolExecutor to process services in parallel
                    with ThreadPoolExecutor() as executor:
                        futures = [
                            executor.submit(self._sc_process_service, ctx, service_name, service_config, db_ids)
                            for service_name, service_config in service_configs.items()
                        ]

                        # Process global settings in another thread or the main thread
                        futures.append(executor.submit(self._sc_process_global_settings, session, ctx, global_config))

                        # Collect results from threads
                        for future in as_completed(futures):
                            try:
                                ret_to_put, ret_to_update, ret_to_delete, ret_changed_plugins, ret_changed_services, ret_service_template_change = (
                                    future.result()
                                )
                                to_put.extend(ret_to_put)
                                to_update.extend(ret_to_update)
                                to_delete.extend(ret_to_delete)
                                changed_plugins.update(ret_changed_plugins)
                                if not changed_services:
                                    changed_services = ret_changed_services
                                if not service_template_change:
                                    service_template_change = ret_service_template_change
                            except Exception as e:
                                self.logger.error(f"Thread raised an exception: {e}")

                else:
                    ret_changed_services, ret_service_template_change = self._sc_apply_non_multisite_config(
                        session, ctx, skip_service_management, to_put, to_update, to_delete, changed_plugins
                    )
                    if ret_changed_services:
                        changed_services = True
                    if ret_service_template_change:
                        service_template_change = True

            if changed_services:
                changed_plugins = set(plugin.id for plugin in session.execute(select(Plugins.id)).all())

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        if not metadata.first_config_saved:
                            metadata.first_config_saved = True
                        if service_template_change:
                            metadata.custom_configs_changed = True
                            metadata.last_custom_configs_change = datetime.now().astimezone()

                    if changed_plugins:
                        session.execute(
                            update(Plugins)
                            .filter(Plugins.id.in_(changed_plugins))
                            .values({Plugins.config_changed: True})
                            .execution_options(synchronize_session=False)
                        )

            try:
                # Apply collected deletions
                for delete_item in to_delete:
                    session.execute(delete(delete_item["model"]).filter_by(**delete_item["filter"]).execution_options(synchronize_session=False))

                # Apply collected updates
                for update_item in to_update:
                    session.execute(
                        update(update_item["model"])
                        .filter_by(**update_item["filter"])
                        .values(update_item["values"])
                        .execution_options(synchronize_session=False)
                    )

                # Add new objects
                session.add_all(to_put)

                # Delete old global settings
                for global_setting in global_settings_to_delete:
                    session.delete(global_setting)

                # Delete old service settings
                for service_setting in service_settings_to_delete:
                    session.delete(service_setting)

                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)

        return changed_plugins

    def _sc_compute_drafted_service_ids(self, session, ctx: _SaveConfigContext, skip_service_management: bool, disable_cleanup: bool) -> Set[str]:
        """save_config phase: drafted-service-id precomputation (no session writes)."""
        # When the autoconf disable_cleanup flag is on, precompute the set of existing
        # autoconf services missing from the incoming SERVER_NAME so the services_settings
        # cleanup pass below leaves their rows in place (the service itself will be flipped
        # to is_draft=True further down instead of being deleted).
        drafted_service_ids: Set[str] = set()
        if disable_cleanup and ctx.method == "autoconf" and not skip_service_management:
            server_name_value = ctx.config.get("SERVER_NAME", "")
            if isinstance(server_name_value, str):
                incoming_service_ids = {s for s in server_name_value.strip().split() if s}
            elif isinstance(server_name_value, list):
                incoming_service_ids = {s for s in server_name_value if s}
            else:
                incoming_service_ids = set()
            existing_autoconf_services = session.execute(select(Services.id).filter_by(method="autoconf")).all()
            drafted_service_ids = {row.id for row in existing_autoconf_services if row.id not in incoming_service_ids}
        return drafted_service_ids

    def _sc_cleanup_global_settings(self, session, ctx: _SaveConfigContext, changed_plugins: Set[str]) -> Tuple[bool, List[Any], bool]:
        """save_config phase: global settings cleanup collection.

        Returns ``(refused, global_settings_to_delete, changed_services)``.
        ``refused`` is True when the scheduler 100%-wipe data-loss guard trips;
        save_config must then return ``changed_plugins`` unchanged (the original
        early return). Mutates ``changed_plugins`` in place, like the original.
        """
        changed_services = False

        self.logger.debug(f"Cleaning up {ctx.method} old global settings")
        # Collect global settings to delete
        global_settings_to_delete = []
        global_method_total = 0
        for db_global_config in session.scalars(select(Global_values).filter_by(method=ctx.method)).all():
            global_method_total += 1
            key = db_global_config.setting_id
            if db_global_config.suffix:
                key = f"{key}_{db_global_config.suffix}"

            try:
                # Check if the setting should be deleted based on key presence
                should_delete = key not in ctx.config and (db_global_config.suffix or f"{key}_0" not in ctx.config)

                if should_delete:
                    global_settings_to_delete.append(db_global_config)
                    # Get plugin ID with safer query and null checking
                    plugin_query = session.execute(select(Settings.plugin_id).filter_by(id=db_global_config.setting_id).limit(1)).first()
                    if plugin_query:
                        plugin_id = plugin_query.plugin_id
                        if plugin_id:
                            changed_plugins.add(plugin_id)

                    # Handle special SERVER_NAME case
                    if key == "SERVER_NAME":
                        changed_services = True
            except Exception as e:
                self.logger.warning(f"Error processing global config {db_global_config.setting_id}: {e}")
                continue

        # Data-loss guard (mirror of the SERVER_NAME guard below): refuse the cleanup pass
        # when it would wipe every single existing global value for this method. A 100% wipe
        # is almost always a transient state issue — an empty or partially-loaded variables.env
        # at scheduler startup, a race with the plugin download jobs, or a caller that forgot
        # to include the current config in its payload — rather than a legitimate intent to
        # purge everything. Callers that really want to clear all scheduler-method globals
        # can do so explicitly by deleting individual rows or using the admin API.
        if ctx.method == "scheduler" and global_method_total > 0 and len(global_settings_to_delete) == global_method_total:
            self.logger.warning(
                f"Refusing to delete all {global_method_total} scheduler-method global setting(s) via "
                f"save_config — the incoming config would wipe every existing row for method {ctx.method!r}. "
                f"This almost always indicates a transient variables.env or environment race at scheduler "
                f"startup. Aborting save_config to prevent data loss."
            )
            return True, global_settings_to_delete, changed_services

        return False, global_settings_to_delete, changed_services

    def _sc_cleanup_service_settings(
        self, session, ctx: _SaveConfigContext, skip_service_management: bool, drafted_service_ids: Set[str], changed_plugins: Set[str]
    ) -> Tuple[bool, List[Any], bool, bool]:
        """save_config phase: per-service settings cleanup collection.

        Returns ``(refused, service_settings_to_delete, changed_services, service_template_change)``.
        ``refused`` is True when the ui/api whole-service-wipe data-loss guard trips;
        save_config must then return ``changed_plugins`` unchanged (the original
        early return). Mutates ``changed_plugins`` in place, like the original.
        """
        changed_services = False
        service_template_change = False

        self.logger.debug(f"Cleaning up {ctx.method} old services settings")
        # Collect service settings to delete (skip entirely when skip_service_management to avoid deleting service settings)
        service_settings_to_delete = []
        # Track per-service totals so we can detect would-wipe-the-whole-service deletions below.
        service_method_total: Dict[str, int] = defaultdict(int)
        service_method_to_delete: Dict[str, int] = defaultdict(int)
        for db_service_config in [] if skip_service_management else session.scalars(select(Services_settings).filter_by(method=ctx.method)).all():
            # Preserve settings of services about to be drafted by the autoconf disable_cleanup path
            # so they can be re-published when the orchestration object returns.
            if db_service_config.service_id in drafted_service_ids:
                continue
            service_method_total[db_service_config.service_id] += 1
            key = f"{db_service_config.service_id}_{db_service_config.setting_id}"
            if db_service_config.suffix:
                key = f"{key}_{db_service_config.suffix}"

            try:
                # Check if the setting should be deleted based on key presence
                should_delete = key not in ctx.config and (db_service_config.suffix or f"{key}_0" not in ctx.config)

                if should_delete:
                    service_settings_to_delete.append(db_service_config)
                    service_method_to_delete[db_service_config.service_id] += 1
                    # Get plugin ID with safer query and null checking
                    plugin_query = session.execute(select(Settings.plugin_id).filter_by(id=db_service_config.setting_id).limit(1)).first()
                    if plugin_query:
                        plugin_id = plugin_query.plugin_id
                        if plugin_id:
                            changed_plugins.add(plugin_id)

                    # Handle special SERVER_NAME case
                    if key in ("SERVER_NAME", f"{db_service_config.service_id}_SERVER_NAME"):
                        changed_services = True
                    elif key in ("USE_TEMPLATE", f"{db_service_config.service_id}_USE_TEMPLATE"):
                        service_template_change = True
            except Exception as e:
                self.logger.warning(f"Error processing service config {db_service_config.setting_id}: {e}")
                continue

        # Data-loss guard (mirror of the scheduler global guard above): refuse the cleanup
        # when a ui/api save_config would wipe every method-owned row of an existing service
        # while the service itself is still listed in SERVER_NAME. A 100% wipe with the
        # service still alive almost always means the caller submitted an incomplete config
        # (Advanced-mode form post missing keys, JS form rebuild race, plugin tab that failed
        # to render). Genuine service deletion drops the id from SERVER_NAME and flows
        # through the removal path further down, so this guard never blocks legitimate deletes.
        if ctx.method in ("ui", "api") and service_method_to_delete and not skip_service_management:
            incoming_server_name = ctx.config.get("SERVER_NAME", "")
            if isinstance(incoming_server_name, str):
                incoming_service_ids = {s for s in incoming_server_name.strip().split() if s}
            elif isinstance(incoming_server_name, list):
                incoming_service_ids = {s for s in incoming_server_name if s}
            else:
                incoming_service_ids = set()

            refused_service_ids = sorted(
                sid
                for sid, total in service_method_total.items()
                if total > 0 and service_method_to_delete.get(sid, 0) == total and sid in incoming_service_ids
            )
            if refused_service_ids:
                self.logger.warning(
                    f"Refusing save_config: incoming method={ctx.method!r} payload would wipe every "
                    f"{ctx.method}-method setting row for service(s) {refused_service_ids} while the "
                    f"service(s) are still present in SERVER_NAME. This indicates the caller "
                    f"submitted an incomplete config (e.g. an Advanced-mode form post missing keys). "
                    f"Aborting save_config to prevent data loss."
                )
                return True, service_settings_to_delete, changed_services, service_template_change

        return False, service_settings_to_delete, changed_services, service_template_change

    def _sc_reconcile_services(
        self, session, ctx: _SaveConfigContext, disable_cleanup: bool, to_put: List[Any], to_update: List[Any]
    ) -> Tuple[bool, List[str], Dict[str, dict], Set[str], bool, bool]:
        """save_config phase: SERVER_NAME service reconciliation (add/draftify/delete).

        Returns ``(refused, services, db_ids, drafts, changed_services, service_template_change)``.
        ``refused`` is True when one of the empty-SERVER_NAME data-loss guards trips;
        save_config must then return ``changed_plugins`` unchanged (the original
        early returns). Appends to ``to_put``/``to_update`` in place, like the original.
        """
        changed_services = False
        service_template_change = False

        self.logger.debug("Checking if the services have changed")
        db_services = session.execute(select(Services.id, Services.method, Services.is_draft)).all()
        db_ids: Dict[str, dict] = {service.id: {"method": service.method, "is_draft": service.is_draft} for service in db_services}
        missing_ids = []
        services = ctx.config.get("SERVER_NAME", [])

        if isinstance(services, str):
            services = services.strip().split()

        services = [service for service in services if service]  # Clean up empty strings

        # Only meaningful for the autoconf method.
        disable_cleanup = disable_cleanup and ctx.method == "autoconf"

        if db_services:
            # Guard: if an empty services list is received but DB has services for this method,
            # abort the entire save_config to prevent catastrophic data loss.
            # For autoconf: only guard when existing DB services were created by a *different*
            # method (ui/api/manual). If every existing service was itself created by autoconf,
            # an empty SERVER_NAME is a legitimate "all ingresses removed" signal and clearing
            # those services is the correct behaviour. Without this relaxation, tearing down
            # the last Ingress and re-applying a new one gets stuck with stale services in the DB.
            # For other methods: protects against callers that omit SERVER_NAME entirely
            # (e.g. a global-only config update that forgot to set skip_service_management=True).
            method_services = [s for s in db_services if s.method == ctx.method or (s.method in ("ui", "api") and ctx.method in ("ui", "api"))]
            if not services and method_services and (ctx.method == "autoconf" or "SERVER_NAME" not in ctx.config):
                if ctx.method == "autoconf":
                    foreign_services = [s for s in db_services if s.method not in ("autoconf", "scheduler")]
                    if not foreign_services:
                        self.logger.debug(
                            f"Received empty SERVER_NAME for autoconf and all {len(method_services)} existing service(s) are autoconf-owned; "
                            "proceeding with removal"
                        )
                        missing_ids = [service.id for service in method_services]
                    else:
                        self.logger.warning(
                            f"Received empty SERVER_NAME for method 'autoconf' but database has {len(foreign_services)} non-autoconf service(s), "
                            "skipping entire config save to prevent data loss"
                        )
                        return True, services, db_ids, set(), changed_services, service_template_change
                else:
                    self.logger.warning(
                        f"Received empty SERVER_NAME for method '{ctx.method}' but database has {len(method_services)} existing service(s), "
                        "skipping entire config save to prevent data loss"
                    )
                    return True, services, db_ids, set(), changed_services, service_template_change
            else:
                missing_ids = [
                    service.id
                    for service in db_services
                    if (service.method == ctx.method or (service.method in ("ui", "api") and ctx.method in ("ui", "api"))) and service.id not in services
                ]

            if missing_ids:
                # When AUTOCONF_DISABLE_CLEANUP is on, convert removed autoconf services to draft
                # instead of hard-deleting them so that settings / custom configs / job caches
                # survive and the service can be republished by bringing the orchestration object
                # back. Services owned by other methods (shouldn't happen when method=autoconf but
                # kept defensively) still follow the legacy cascade-delete path.
                draftable_ids = [sid for sid in missing_ids if db_ids.get(sid, {}).get("method") == "autoconf"] if disable_cleanup else []
                hard_delete_ids = [sid for sid in missing_ids if sid not in draftable_ids]

                if draftable_ids:
                    self.logger.debug(f"Converting {len(draftable_ids)} autoconf services to draft instead of deleting them")
                    session.execute(
                        update(Services)
                        .filter(Services.id.in_(draftable_ids))
                        .values({Services.is_draft: True, Services.last_update: datetime.now().astimezone()})
                        .execution_options(synchronize_session=False)
                    )
                    session.execute(
                        update(Custom_configs)
                        .filter(Custom_configs.service_id.in_(draftable_ids))
                        .values({Custom_configs.is_draft: True})
                        .execution_options(synchronize_session=False)
                    )
                    session.execute(
                        update(Metadata)
                        .filter_by(id=1)
                        .values({Metadata.custom_configs_changed: True, Metadata.last_custom_configs_change: datetime.now().astimezone()})
                    )
                    changed_services = True
                    if any(ctx.config.get(f"{sid}_USE_TEMPLATE", "") for sid in draftable_ids):
                        service_template_change = True

                if hard_delete_ids:
                    self.logger.debug(f"Removing {len(hard_delete_ids)} services that are no longer in the list")
                    # Remove services that are no longer in the list
                    session.execute(delete(Services).filter(Services.id.in_(hard_delete_ids)).execution_options(synchronize_session=False))
                    session.execute(
                        delete(Services_settings).filter(Services_settings.service_id.in_(hard_delete_ids)).execution_options(synchronize_session=False)
                    )
                    session.execute(delete(Custom_configs).filter(Custom_configs.service_id.in_(hard_delete_ids)).execution_options(synchronize_session=False))
                    session.execute(delete(Jobs_cache).filter(Jobs_cache.service_id.in_(hard_delete_ids)).execution_options(synchronize_session=False))
                    session.execute(
                        update(Metadata)
                        .filter_by(id=1)
                        .values({Metadata.custom_configs_changed: True, Metadata.last_custom_configs_change: datetime.now().astimezone()})
                    )
                    changed_services = True
                    if any(ctx.config.get(f"{sid}_USE_TEMPLATE", "") for sid in hard_delete_ids):
                        service_template_change = True

        self.logger.debug("Checking if the drafts have changed")
        drafts = {service for service in services if ctx.config.pop(f"{service}_IS_DRAFT", "no") == "yes"}
        db_drafts = {service.id for service in db_services if service.is_draft}

        if db_drafts:
            missing_drafts = [
                service.id
                for service in db_services
                if (service.method == ctx.method or (service.method in ("ui", "api") and ctx.method in ("ui", "api")))
                and service.id not in drafts
                and service.id not in missing_ids
            ]

            if missing_drafts:
                self.logger.debug(f"Removing {len(missing_drafts)} drafts that are no longer in the list")
                # Update services to remove draft status
                session.execute(
                    update(Services).filter(Services.id.in_(missing_drafts)).values({Services.is_draft: False}).execution_options(synchronize_session=False)
                )
                changed_services = True

        for draft in drafts:
            if draft not in db_drafts:
                current_time = datetime.now().astimezone()
                if draft not in db_ids:
                    self.logger.debug(f"Adding draft {draft}")
                    to_put.append(Services(id=draft, method=ctx.method, is_draft=True, creation_date=current_time, last_update=current_time))
                    db_ids[draft] = {"method": ctx.method, "is_draft": True}
                elif db_ids[draft]["method"] == ctx.method or (db_ids[draft]["method"] in ("ui", "api") and ctx.method in ("ui", "api")):
                    self.logger.debug(f"Updating draft {draft}")
                    to_update.append({"model": Services, "filter": {"id": draft}, "values": {"is_draft": True, "last_update": current_time}})
                    changed_services = True

        return False, services, db_ids, drafts, changed_services, service_template_change

    def _sc_split_multisite_config(
        self, ctx: _SaveConfigContext, services: List[str], db_ids: Dict[str, dict]
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        """save_config phase: split the flat config into per-service configs and a global config."""
        service_configs = defaultdict(dict)
        global_config = {}

        services_set = set(services)
        # Supplement with DB-resident, non-draft services so that
        # multisite-prefixed keys for services created out-of-band
        # (UI/API/autoconf) aren't mis-classified as global settings
        # when the caller's SERVER_NAME payload hasn't yet been rebuilt
        # to include them. Mirrors the DB-supplement done in
        # Configurator.get_config() (with_drafts=False).
        services_set.update(sid for sid, meta in db_ids.items() if not meta.get("is_draft"))

        for key, value in ctx.config.items():
            matched = False
            underscore_pos = 0
            while True:
                underscore_pos = key.find("_", underscore_pos)
                if underscore_pos == -1:
                    break
                potential_service = key[:underscore_pos]
                if potential_service in services_set:
                    stripped_key = key[underscore_pos + 1 :]  # noqa: E203
                    service_configs[potential_service][stripped_key] = value
                    matched = True
                    break
                underscore_pos += 1
            if not matched:
                global_config[key] = value

        return service_configs, global_config

    def _sc_collect_multisite_data(self, session, ctx: _SaveConfigContext) -> None:
        """save_config phase: collect the settings/service-settings/template lookup dicts used by the
        multisite worker threads, storing them on ``ctx`` (read-only afterwards)."""
        # Collect necessary data before threading
        settings_data = session.execute(select(Settings.id, Settings.default, Settings.plugin_id, Settings.type, Settings.separator)).all()
        ctx.settings_dict = {
            s.id: {"default": self._empty_if_none(s.default), "plugin_id": s.plugin_id, "type": s.type, "separator": s.separator} for s in settings_data
        }

        # Collect existing service settings
        existing_service_settings = session.execute(
            select(
                Services_settings.service_id,
                Services_settings.setting_id,
                Services_settings.suffix,
                Services_settings.value,
                Services_settings.file_name,
                Services_settings.method,
            )
        ).all()
        ctx.existing_service_settings_dict = {
            (s.service_id, s.setting_id, s.suffix or 0): {
                "value": self._empty_if_none(s.value),
                "file_name": self._empty_if_none(s.file_name),
                "method": s.method,
            }
            for s in existing_service_settings
        }

        # Collect template settings
        templates = {}
        # The loop variable deliberately reuses the name ``template``: in the original
        # nested implementation this loop rebound the enclosing ``template`` variable,
        # so when the query returns rows the downstream service/global processing sees
        # the last Template_settings row instead of the USE_TEMPLATE string. Preserved
        # as-is via ctx.template (pure structural refactor — zero behavior change).
        template = ctx.template
        for template in session.execute(
            select(Template_settings.template_id, Template_settings.setting_id, Template_settings.suffix, Template_settings.default).order_by(
                Template_settings.order
            )
        ):
            if template.template_id not in templates:
                templates[template.template_id] = {}
            templates[template.template_id][(template.setting_id, template.suffix or 0)] = template.default
        ctx.template = template
        ctx.templates = templates

    def _sc_process_service(self, ctx: _SaveConfigContext, server_name: str, service_config: Dict[str, str], db_ids: Dict[str, dict]):
        """save_config worker (runs in ThreadPoolExecutor threads): per-service multisite settings pass.

        Verbatim body of the original nested ``process_service`` closure, with the
        captured variables read from ``ctx`` instead. Returns the same 6-tuple.
        """
        local_to_put = []
        local_to_update = []
        local_to_delete = []
        local_changed_plugins = set()
        local_changed_services = False
        local_service_template_change = False

        service_template = service_config.get("USE_TEMPLATE", ctx.template)

        for original_key, value in service_config.items():
            suffix = 0
            key = deepcopy(original_key)
            if self.SUFFIX_RX.search(key):
                suffix = int(key.split("_")[-1])
                key = key[: -len(str(suffix)) - 1]

            setting = ctx.settings_dict.get(key)
            if not setting:
                self.logger.debug(f"Setting {key} does not exist")
                continue

            value = _canonicalize_stored_value(setting["type"], value, setting.get("separator"))

            if server_name not in db_ids:
                self.logger.debug(f"Adding service {server_name}")
                current_time = datetime.now().astimezone()
                local_to_put.append(
                    Services(id=server_name, method=ctx.method, is_draft=server_name in ctx.drafts, creation_date=current_time, last_update=current_time)
                )
                db_ids[server_name] = {"method": ctx.method, "is_draft": server_name in ctx.drafts}
                if server_name not in ctx.drafts:
                    local_changed_services = True

            service_setting = ctx.existing_service_settings_dict.get((server_name, key, suffix))
            current_file_name = service_setting["file_name"] if service_setting else ""
            value_changed = bool(service_setting and service_setting["value"] != value)
            should_update_value = (value_changed and self._methods_are_compatible(ctx.method, service_setting["method"])) or (
                bool(service_setting) and ctx.method == "autoconf" and service_setting["method"] != "autoconf"
            )
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting["type"], original_key, value_changed, current_file_name)

            template_setting_default = None
            if service_template:
                template_setting_default = ctx.templates.get(service_template, {}).get((key, suffix))
                local_service_template_change = True

            # Determine if we need to add, update, or delete
            if not service_setting:
                if _check_value(ctx, key, value, setting, template_setting_default, suffix):
                    continue

                self.logger.debug(f"Adding setting {key} for service {server_name}")
                local_changed_plugins.add(setting["plugin_id"])
                local_to_put.append(
                    Services_settings(
                        service_id=server_name,
                        setting_id=key,
                        value=value,
                        file_name=target_file_name if setting["type"] == "file" else None,
                        suffix=suffix,
                        method=ctx.method,
                    )
                )
                # Update Services.last_update
                local_to_update.append({"model": Services, "filter": {"id": server_name}, "values": {"last_update": datetime.now().astimezone()}})
                if key == "SERVER_NAME":
                    local_changed_services = True
            elif should_update_value or file_name_changed:
                if should_update_value:
                    local_changed_plugins.add(setting["plugin_id"])

                if should_update_value and _check_value(ctx, key, value, setting, template_setting_default, suffix):
                    self.logger.debug(f"Removing setting {key} for service {server_name}")
                    local_to_delete.append({"model": Services_settings, "filter": {"service_id": server_name, "setting_id": key, "suffix": suffix}})
                    continue

                self.logger.debug(f"Updating setting {key} for service {server_name}")
                setting_values = {"value": self._empty_if_none(value), "method": ctx.method}
                if setting["type"] == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                local_to_update.extend(
                    [
                        {
                            "model": Services_settings,
                            "filter": {"service_id": server_name, "setting_id": key, "suffix": suffix},
                            "values": setting_values,
                        },
                        {"model": Services, "filter": {"id": server_name}, "values": {"last_update": datetime.now().astimezone()}},
                    ]
                )
                if key == "SERVER_NAME":
                    local_changed_services = True

        return local_to_put, local_to_update, local_to_delete, local_changed_plugins, local_changed_services, local_service_template_change

    def _sc_process_global_settings(self, session, ctx: _SaveConfigContext, global_config: Dict[str, str]):
        """save_config worker (runs in a ThreadPoolExecutor thread): multisite global settings pass.

        Verbatim body of the original nested ``process_global_settings`` closure, with the
        captured variables read from ``ctx`` and the *same* scoped session passed in
        explicitly (the closure used to capture it). Returns the same 6-tuple.
        """
        local_to_put = []
        local_to_update = []
        local_to_delete = []
        local_changed_plugins = set()
        local_service_template_change = False

        for original_key, value in global_config.items():
            suffix = 0
            key = deepcopy(original_key)
            if self.SUFFIX_RX.search(key):
                suffix = int(key.split("_")[-1])
                key = key[: -len(str(suffix)) - 1]

            setting = ctx.settings_dict.get(key)
            if not setting:
                self.logger.debug(f"Setting {key} does not exist")
                continue

            value = _canonicalize_stored_value(setting["type"], value, setting.get("separator"))

            global_value = session.execute(
                select(Global_values.value, Global_values.file_name, Global_values.method).filter_by(setting_id=key, suffix=suffix).limit(1)
            ).first()
            current_file_name = self._empty_if_none(global_value.file_name) if global_value else ""
            value_changed = bool(global_value and global_value.value != value)
            should_update_value = (value_changed and self._methods_are_compatible(ctx.method, global_value.method)) or (
                bool(global_value) and ctx.method == "autoconf" and global_value.method != "autoconf"
            )
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting["type"], original_key, value_changed, current_file_name)

            template_setting_default = None
            if ctx.template:
                template_setting_default = ctx.templates.get(ctx.template, {}).get((key, suffix))
                local_service_template_change = True

            if not global_value:
                if _check_value(ctx, key, value, setting, template_setting_default, suffix, True):
                    continue

                self.logger.debug(f"Adding global setting {key}")
                local_changed_plugins.add(setting["plugin_id"])
                local_to_put.append(
                    Global_values(
                        setting_id=key,
                        value=value,
                        file_name=target_file_name if setting["type"] == "file" else None,
                        suffix=suffix,
                        method=ctx.method,
                    )
                )
            elif should_update_value or file_name_changed:
                if should_update_value:
                    local_changed_plugins.add(setting["plugin_id"])

                if should_update_value and _check_value(ctx, key, value, setting, template_setting_default, suffix, True):
                    self.logger.debug(f"Removing global setting {key}")
                    local_to_delete.append({"model": Global_values, "filter": {"setting_id": key, "suffix": suffix}})
                    continue

                self.logger.debug(f"Updating global setting {key}")
                setting_values = {"value": self._empty_if_none(value), "method": ctx.method}
                if setting["type"] == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                local_to_update.append(
                    {
                        "model": Global_values,
                        "filter": {"setting_id": key, "suffix": suffix},
                        "values": setting_values,
                    }
                )

        return local_to_put, local_to_update, local_to_delete, local_changed_plugins, False, local_service_template_change

    def _sc_apply_non_multisite_config(
        self,
        session,
        ctx: _SaveConfigContext,
        skip_service_management: bool,
        to_put: List[Any],
        to_update: List[Any],
        to_delete: List[Any],
        changed_plugins: Set[str],
    ) -> Tuple[bool, bool]:
        """save_config phase: non-multisite settings pass.

        Returns ``(changed_services, service_template_change)``. Appends to
        ``to_put``/``to_update``/``to_delete`` and mutates ``changed_plugins``
        in place, like the original inline block.
        """
        changed_services = False
        service_template_change = False

        # Non-multisite configuration
        self.logger.debug("Checking if non-multisite settings have changed")

        if not skip_service_management:
            server_name = ctx.config.get("SERVER_NAME", None)
            if ctx.template and server_name is None:
                server_name = session.execute(select(Template_settings.value).filter_by(template_id=ctx.template, setting_id="SERVER_NAME").limit(1)).first()

            if server_name is None or server_name:
                server_name = server_name or "www.example.com"
                first_server = server_name.split(" ")[0]

                if not session.execute(select(Services.id).filter_by(id=first_server).limit(1)).first():
                    self.logger.debug(f"Adding service {first_server}")
                    current_time = datetime.now().astimezone()
                    to_put.append(
                        Services(
                            id=first_server,
                            method=ctx.method,
                            is_draft=first_server in ctx.drafts,
                            creation_date=current_time,
                            last_update=current_time,
                        )
                    )
                    changed_services = True

        for original_key, value in ctx.config.items():
            key = deepcopy(original_key)
            suffix = 0
            if self.SUFFIX_RX.search(key):
                suffix = int(key.split("_")[-1])
                key = key[: -len(str(suffix)) - 1]

            setting = session.execute(select(Settings.default, Settings.plugin_id, Settings.type, Settings.separator).filter_by(id=key).limit(1)).first()

            if not setting:
                continue

            value = _canonicalize_stored_value(setting.type, value, setting.separator)

            global_value = session.execute(
                select(Global_values.value, Global_values.file_name, Global_values.method).filter_by(setting_id=key, suffix=suffix).limit(1)
            ).first()
            current_file_name = self._empty_if_none(global_value.file_name) if global_value else ""
            value_changed = bool(global_value and global_value.value != value)
            should_update_value = bool(global_value and self._methods_are_compatible(ctx.method, global_value.method) and value_changed)
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting.type, original_key, value_changed, current_file_name)

            template_setting = None
            if ctx.template:
                template_setting = session.execute(
                    select(Template_settings.default).filter_by(template_id=ctx.template, setting_id=key, suffix=suffix).limit(1)
                ).first()
                service_template_change = True

            if not global_value:
                if value == (template_setting.default if template_setting is not None else setting.default):
                    continue

                self.logger.debug(f"Adding global setting {key}")
                changed_plugins.add(setting.plugin_id)
                to_put.append(
                    Global_values(
                        setting_id=key,
                        value=value,
                        file_name=target_file_name if setting.type == "file" else None,
                        suffix=suffix,
                        method=ctx.method,
                    )
                )
            elif should_update_value or file_name_changed:
                if should_update_value:
                    changed_plugins.add(setting.plugin_id)

                if should_update_value and value == (template_setting.default if template_setting is not None else setting.default):
                    self.logger.debug(f"Removing global setting {key}")
                    to_delete.append({"model": Global_values, "filter": {"setting_id": key, "suffix": suffix}})
                    continue

                self.logger.debug(f"Updating global setting {key}")
                setting_values = {"value": self._empty_if_none(value), "method": ctx.method}
                if setting.type == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                to_update.append(
                    {
                        "model": Global_values,
                        "filter": {"setting_id": key, "suffix": suffix},
                        "values": setting_values,
                    }
                )

        return changed_services, service_template_change
