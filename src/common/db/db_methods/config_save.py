#!/usr/bin/env python3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from model import (  # type: ignore
    Custom_configs,
    Global_values,
    Metadata,
    Multiselects,
    Plugins,
    Selects,
    Services,
    Services_settings,
    Settings,
    Template_settings,
)

from location_claims import LOCATION_FAMILIES, inline_location_conflict  # type: ignore
from redirect_resolver import config_servers, scan_prefixes  # type: ignore
from resource_group_resolver import kind_for_key, validate_resource_group_refs  # type: ignore

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from .common import EDITABLE_METHODS, DatabaseMixinBase, canonicalize_setting_value, delete_service_rows
from .locations import server_type_attachment_conflict


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
    # Raw environment/variables keys explicitly declared by the caller (e.g.
    # Configurator.explicit_keys), service-prefixed and suffixed forms included. Only
    # consulted when method == "scheduler": a scheduler pass may overwrite a ui/api-owned
    # row only for keys in this set. Empty means the scheduler never touches ui/api rows
    # (the incoming config is treated as default-filled, not user-declared).
    explicit_keys: frozenset = field(default_factory=frozenset)


def _scheduler_can_override(ctx: _SaveConfigContext, full_key: str, incoming_value: Any) -> bool:
    """Whether a scheduler-method pass may overwrite a ui/api-owned row for ``full_key``.

    Only keys explicitly declared in the environment (``ctx.explicit_keys``) qualify, so a
    default-filled scheduler pass never clobbers UI/API customizations. The Linux dummy
    variables.env ships ``SERVER_NAME=`` — an explicitly-declared but EMPTY SERVER_NAME must
    not clobber a ui/api-owned service list.
    """
    if full_key not in ctx.explicit_keys:
        return False
    if full_key == "SERVER_NAME" and not str(incoming_value).strip():
        return False
    return True


def _log_ownership_refusal(logger, ctx: _SaveConfigContext, target: str, owner_method: Optional[str]) -> None:
    """Report a write dropped purely because the incoming method may not overwrite the row's.

    That refusal used to be entirely silent: the caller got an empty changed-plugins set and no
    way to tell its write had been dropped, which is how `PATCH /global_settings` answered 200
    "success" having written nothing.

    A SCHEDULER refusal is not that -- it is `_scheduler_can_override` doing its job, and it is
    the steady state, not an incident. Configurator default-fills every setting before applying
    the environment, so every ui/api-customised row is refused on every scheduler pass; at WARNING
    that is one line per customised setting per service per save. Hence debug for scheduler,
    warning for the callers that actually asked for a specific write and did not get it.
    """
    # method-decision: deliberate: picks a log level, owns nothing. See the docstring above for why scheduler is quieter.
    message = f"Refusing to overwrite {target} (owned by method {owner_method}) with method {ctx.method}: value left unchanged"
    if ctx.method == "scheduler":
        logger.debug(message)
    else:
        logger.warning(message)


def _get_setting_file_name(
    ctx: _SaveConfigContext,
    setting_type: str,
    original_key: str,
    value_changed: bool,
    current_file_name: str = "",
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
    ctx: _SaveConfigContext,
    val: str,
    key: str,
    setting: dict,
    template_default: Optional[str] = None,
    suffix: int = 0,
    is_global: bool = False,
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


def _check_value(
    ctx: _SaveConfigContext,
    key: str,
    value: str,
    setting: dict,
    template_default: Optional[str],
    suffix: int,
    is_global: bool = False,
) -> bool:
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


def _canonicalize_stored_value(
    setting_type: Optional[str],
    value: Any,
    separator: Optional[str] = " ",
    options: Optional[List[str]] = None,
    case_insensitive: bool = False,
) -> Any:
    """Canonicalize a value to its stored form by setting type (mirrors
    ``Configurator.__normalize_value``): trim -> check yes/no -> size/duration NGINX unit
    form -> select/multiselect casefold to declared option casing (when ``case_insensitive``)
    -> multivalue/multiselect trimmed items. Invalid size/duration values are left unchanged
    so the stored value stays whatever was provided. Other types untouched."""
    canonical = canonicalize_setting_value(setting_type, value, separator, options, case_insensitive)
    return value if canonical is None else canonical


def _compute_anchored_slots(ctx: "_SaveConfigContext", cfg: Dict[str, str], cfg_template: str, suffix_rx) -> set:
    """Multiple-group slots kept alive by a member the user actually set.

    A slot ``(group, suffix>=1)`` is *anchored* when at least one of its members in the incoming
    config differs from its template-or-plugin default. ``get_config`` re-materialises every member
    of a detected slot at its default, so the scheduler round-trip re-ingests those default
    siblings; an anchored slot survives on its non-default member's row, which makes the default
    siblings spurious -- and persisting them renders the field disabled in the Web UI even though
    the value was never touched. A slot with no anchor is a user-declared all-default slot and must
    be kept, or it would vanish.
    """
    anchored = set()
    for anchor_key, anchor_value in cfg.items():
        anchor_suffix = 0
        anchor_base = anchor_key
        if suffix_rx.search(anchor_base):
            anchor_suffix = int(anchor_base.split("_")[-1])
            anchor_base = anchor_base[: -len(str(anchor_suffix)) - 1]
        if anchor_suffix == 0:
            continue
        anchor_setting = ctx.settings_dict.get(anchor_base)
        if not anchor_setting or not anchor_setting.get("multiple"):
            continue
        anchor_default = ctx.templates.get(cfg_template, {}).get((anchor_base, anchor_suffix)) if cfg_template else None
        if anchor_default is None:
            anchor_default = anchor_setting["default"]
        if anchor_value != anchor_default:
            anchored.add((anchor_setting["multiple"], anchor_suffix))
    return anchored


def _compute_template_slots(ctx: "_SaveConfigContext", cfg_template: str) -> set:
    """Slots kept alive by a template that defines any member at that suffix.

    ``get_config`` rebuilds such a slot from ``Template_settings`` with no row of its own, so its
    default members must not be persisted either. Keyed per ``(group, suffix)`` so the partial case
    works too: a template's ``HOST_1`` keeps its sibling ``TIMEOUT_1``'s slot alive.
    """
    slots = set()
    for member_id, member_suffix in ctx.templates.get(cfg_template, {}):
        if member_suffix and member_suffix > 0:
            member_setting = ctx.settings_dict.get(member_id)
            if member_setting and member_setting.get("multiple"):
                slots.add((member_setting["multiple"], member_suffix))
    return slots


def _slot_flags(setting: dict, suffix: int, value: str, template_setting_default: Optional[str], alive_slots: set) -> Tuple[bool, bool]:
    """``(is_spurious_default_sibling, is_anchorless_multiple_member)`` for a suffixed group member.

    ``alive_slots`` are the slots kept alive by an anchor row or by a template.

    * spurious   -- a default-valued member of a kept-alive slot: drop it, the slot survives via its
      anchor member or its template and the field stays editable.
    * anchorless -- a member of a slot kept alive by nothing: persist it even at its default, else
      the whole user-declared all-default slot would vanish.
    """
    group = setting.get("multiple")
    if suffix <= 0 or group is None:
        return False, False
    slot_default = template_setting_default if template_setting_default is not None else setting["default"]
    alive = (group, suffix) in alive_slots
    return (value == slot_default and alive), (not alive)


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
        explicit_keys: Optional[Set[str]] = None,
        retry_on_conflict: bool = True,
    ) -> Union[str, Set[str]]:
        """Save the config in the database.

        Args:
            explicit_keys: Raw environment/variables keys explicitly declared by the
                           caller (e.g. Configurator.explicit_keys), service-prefixed
                           and suffixed forms included. Only consulted when
                           method == "scheduler": a scheduler pass may overwrite a
                           ui/api-owned row only for keys in this set. None or empty
                           means the scheduler never touches ui/api-owned rows (the
                           incoming config is treated as default-filled, not
                           user-declared).
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
            retry_on_conflict: Recompute and save once more when the flush hits a unique
                               violation because another writer inserted the same rows
                               between our read and our flush. Set False on the retry
                               itself so a genuine conflict cannot loop.
        """
        to_put = []
        to_update = []
        to_delete = []
        conflict = None
        changed_plugins = set()
        changed_services = False
        service_template_change = False

        db_config = {}
        if method == "autoconf":
            db_config = self.get_non_default_settings(with_drafts=True)

        # Read here, not from inside the session below: `get_non_default_settings` opens a
        # session of its own and `_db_session` is not reentrant -- its `finally` calls
        # `session.remove()`, which closes the session the save is holding and discards
        # whatever is pending in it. Nothing is pending at that point today, which is the only
        # reason this has not bitten yet.
        stored_values = db_config or self.get_non_default_settings(with_drafts=True)

        normalized_file_names = {k: ("" if v is None else v.strip()) for k, v in (file_names or {}).items()}

        ctx = _SaveConfigContext(
            config=config,
            db_config=db_config,
            method=method,
            normalized_file_names=normalized_file_names,
            explicit_keys=frozenset(explicit_keys or ()),
        )

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            self.logger.debug(f"Saving config for method {method}")

            service_ids = set(str(config.get("SERVER_NAME", "")).split())
            service_ids.update(session.scalars(select(Services.id)).all())
            # Only values this save actually changes. Callers hand us the MERGED config (autoconf
            # and the scheduler always do), so validating all of it would let one pre-existing
            # illegal row — and the DB is known to hold some — refuse every future save, forever.
            # That also contradicts the rule the API routers state verbatim (services.py,
            # global_settings.py): never validate the merged snapshot. Comparing against what is
            # actually stored still closes the PUT /global_settings/config bypass, and costs one
            # config read instead of one validation round trip per key.
            for key, value in config.items():
                if key == "DATABASE_URI":
                    continue
                normalized = "" if value is None else str(value)
                previous = stored_values.get(key)
                if previous is not None and normalized == str(previous):
                    continue
                is_service_setting = any(key.startswith(f"{service_id}_") for service_id in service_ids)
                success, error = self.is_valid_setting(
                    key,
                    value=normalized,
                    multisite=is_service_setting,
                    session=session,
                    extra_services=list(service_ids),
                )
                if not success:
                    return f"Invalid setting {key}: {error}"

            if error := server_type_attachment_conflict(session, config):
                return error

            if any(isinstance(value, str) and "@" in value and kind_for_key(key) for key, value in config.items()):
                try:
                    group_index = self._get_resource_group_index(session)
                except (ProgrammingError, OperationalError) as exc:
                    session.rollback()
                    self.logger.warning(f"Could not load resource groups while validating config: {exc}")
                    group_index = {}

                if error := validate_resource_group_refs(config, group_index):
                    self.logger.warning(error)
                    return error

            # reverseproxy, grpc and redirect all render a `location` into the same server, and
            # NGINX refuses two locations with the same URI. An incoming inline rule of any of
            # them must therefore not land on a path an attached resource already serves — the
            # mirror of the check the redirects and upstreams mixins run on the resource side.
            if any(isinstance(key, str) and any(trigger in key for trigger, _ in LOCATION_FAMILIES.values()) for key in config):
                try:
                    service_redirects = self._service_redirects(session)
                    service_upstreams = self._service_upstreams(session)
                except (ProgrammingError, OperationalError) as exc:
                    session.rollback()
                    self.logger.warning(f"Could not load attached resources while validating config: {exc}")
                    service_redirects, service_upstreams = {}, {}

                multisite = str(config.get("MULTISITE", "no")) == "yes"
                for server in config_servers(config):
                    paths = [rule["from_path"] for rule in service_redirects.get(server, [])]
                    # A stream pool has no location, so it cannot collide with one.
                    paths += [pool["match_path"] or "/" for pool in service_upstreams.get(server, []) if pool.get("protocol") != "stream"]
                    if error := inline_location_conflict(config, server, scan_prefixes(server, multisite), paths):
                        self.logger.warning(error)
                        return error

            drafted_service_ids = self._sc_compute_drafted_service_ids(session, ctx, skip_service_management, disable_cleanup)

            refused, global_settings_to_delete, ret_changed_services = self._sc_cleanup_global_settings(session, ctx, changed_plugins)
            if ret_changed_services:
                changed_services = True
            if refused:
                # Scheduler 100%-wipe data-loss guard tripped — abort with the
                # plugins collected so far, exactly like the original early return.
                return changed_plugins

            (
                refused,
                service_settings_to_delete,
                ret_changed_services,
                ret_service_template_change,
            ) = self._sc_cleanup_service_settings(
                session,
                ctx,
                skip_service_management,
                drafted_service_ids,
                changed_plugins,
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
                    (
                        refused,
                        services,
                        db_ids,
                        drafts,
                        ret_changed_services,
                        ret_service_template_change,
                    ) = self._sc_reconcile_services(session, ctx, disable_cleanup, to_put, to_update)
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
                            executor.submit(
                                self._sc_process_service,
                                ctx,
                                service_name,
                                service_config,
                                db_ids,
                            )
                            for service_name, service_config in service_configs.items()
                        ]

                        # Process global settings in another thread or the main thread
                        futures.append(
                            executor.submit(
                                self._sc_process_global_settings,
                                session,
                                ctx,
                                global_config,
                            )
                        )

                        # Collect results from threads
                        for future in as_completed(futures):
                            try:
                                (
                                    ret_to_put,
                                    ret_to_update,
                                    ret_to_delete,
                                    ret_changed_plugins,
                                    ret_changed_services,
                                    ret_service_template_change,
                                ) = future.result()
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
                        session,
                        ctx,
                        skip_service_management,
                        to_put,
                        to_update,
                        to_delete,
                        changed_plugins,
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
                        # `last_config_change` must move with the flag. `get_metadata` exports
                        # this as `{plugin_id: last_config_change}` and the scheduler compares
                        # that map against the previous poll to decide whether a change is new
                        # -- so a flag raised without a fresh timestamp is indistinguishable
                        # from the one before it, and whoever acknowledges the change cannot
                        # tell "the change I applied" from "one that landed while I worked".
                        session.execute(
                            update(Plugins)
                            .filter(Plugins.id.in_(changed_plugins))
                            .values({Plugins.config_changed: True, Plugins.last_config_change: datetime.now().astimezone()})
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
            except IntegrityError as e:
                session.rollback()
                if not retry_on_conflict:
                    return str(e)
                conflict = str(e)
            except BaseException as e:
                session.rollback()
                return str(e)

        if conflict is not None:
            # Another writer inserted rows we had read as missing, between our read and our flush --
            # the scheduler's first-run save against autoconf applying its initial configuration on
            # a fresh database is the common one. Dropping the batch loses every setting the other
            # writer does not send: they stay at their defaults, and the per-service rows a later
            # save materialises from them then shadow the globals. Recompute against the committed
            # state instead. Outside the session block: retrying inside it would nest one scoped
            # session in another.
            self.logger.debug(f"Concurrent write while saving the config ({conflict}), recomputing and retrying once ...")
            return self.save_config(
                config,
                method,
                changed,
                file_names,
                skip_service_management=skip_service_management,
                disable_cleanup=disable_cleanup,
                explicit_keys=explicit_keys,
                retry_on_conflict=False,
            )

        return changed_plugins

    def _sc_compute_drafted_service_ids(
        self,
        session,
        ctx: _SaveConfigContext,
        skip_service_management: bool,
        disable_cleanup: bool,
    ) -> Set[str]:
        """save_config phase: drafted-service-id precomputation (no session writes)."""
        # When the autoconf disable_cleanup flag is on, precompute the set of existing
        # autoconf services missing from the incoming SERVER_NAME so the services_settings
        # cleanup pass below leaves their rows in place (the service itself will be flipped
        # to is_draft=True further down instead of being deleted).
        # method-decision: deliberate: AUTOCONF_DISABLE_CLEANUP is an autoconf-only flag; no other method drafts on teardown.
        drafted_service_ids: Set[str] = set()
        if disable_cleanup and ctx.method == "autoconf" and not skip_service_management:
            server_name_value = ctx.config.get("SERVER_NAME", "")
            if isinstance(server_name_value, str):
                incoming_service_ids = {s for s in server_name_value.strip().split() if s}
            elif isinstance(server_name_value, list):
                incoming_service_ids = {s for s in server_name_value if s}
            else:
                incoming_service_ids = set()
            # method-decision: deliberate: the rows being spared are autoconf's own, by definition of the flag above.
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
        # Same rule as the service-settings cleanup below: the editable methods own one another's
        # rows, so cleanup uses the same set the write path does, and every other caller keeps the
        # exact match. The wizard writes global settings too (setup.py:289 hands base_config to
        # new_service(override_method="wizard")), so without this a global setting the wizard wrote
        # could be overwritten from the UI but never cleared -- the save reported success and the
        # old value stayed.
        # The scheduler wipe guard below is unaffected: it only fires for ctx.method == "scheduler",
        # which is not in EDITABLE_METHODS, so global_method_total is still an exact-match count there.
        cleanup_methods = EDITABLE_METHODS if ctx.method in EDITABLE_METHODS else {ctx.method}
        for db_global_config in session.scalars(select(Global_values).filter(Global_values.method.in_(cleanup_methods))).all():
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
        # method-decision: deliberate. Scheduler-only, and not an EDITABLE_METHODS question at all: it exists for the
        # variables.env / environment race at scheduler startup, where a transient empty environment
        # would otherwise delete every config-as-code row. No other method has that failure mode.
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
        self,
        session,
        ctx: _SaveConfigContext,
        skip_service_management: bool,
        drafted_service_ids: Set[str],
        changed_plugins: Set[str],
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
        # Which rows this save may CLEAN UP. The editable methods own one another's rows -- that is
        # what _is_method_compatible has always said, and 33f42592d added "wizard" to the set -- so
        # cleanup has to use the same set the write path does. Matching only ctx.method meant a save
        # could WRITE a sibling method's row but never CLEAR one: unchecking a setting on a
        # wizard-created service reported success and silently kept the old value, and because a UI
        # write does not migrate the row's method it never healed on a later edit either.
        # scheduler and autoconf are deliberately NOT in EDITABLE_METHODS: config-as-code rows stay
        # owned by the method that declared them, so an exact match is kept for every other caller.
        cleanup_methods = EDITABLE_METHODS if ctx.method in EDITABLE_METHODS else {ctx.method}
        for db_service_config in (
            [] if skip_service_management else session.scalars(select(Services_settings).filter(Services_settings.method.in_(cleanup_methods))).all()
        ):
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
                    if key in (
                        "SERVER_NAME",
                        f"{db_service_config.service_id}_SERVER_NAME",
                    ):
                        changed_services = True
                    elif key in (
                        "USE_TEMPLATE",
                        f"{db_service_config.service_id}_USE_TEMPLATE",
                    ):
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
        # method-decision: deliberate. ("ui", "api") and not EDITABLE_METHODS, while the cleanup select above uses
        # the wider set: this guard is pinned to that loop, which only ever yields rows the caller
        # may clean up, so the only thing "wizard" would add here is guarding the setup wizard's own
        # single, server-built save. No user action is silently discarded either way, and the wizard
        # save path is exactly where this port has already regressed once today. Asymmetric on
        # purpose -- do not "complete" it without a ruling. (manager, 12:18 CEST)
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
                return (
                    True,
                    service_settings_to_delete,
                    changed_services,
                    service_template_change,
                )

        return (
            False,
            service_settings_to_delete,
            changed_services,
            service_template_change,
        )

    def _sc_reconcile_services(
        self,
        session,
        ctx: _SaveConfigContext,
        disable_cleanup: bool,
        to_put: List[Any],
        to_update: List[Any],
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

        # method-decision: deliberate: same flag, same reason.
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
            # method-decision: deliberate: DELETION ownership, not edit ownership -- this decides whose services an empty
            # SERVER_NAME may remove. "wizard" stays out because the wizard service cannot be deleted
            # at all (api/app/routers/services.py:240, 403). The autoconf branches below are autoconf's
            # ingress-teardown semantics, covered by the same token.
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
                        return (
                            True,
                            services,
                            db_ids,
                            set(),
                            changed_services,
                            service_template_change,
                        )
                else:
                    self.logger.warning(
                        f"Received empty SERVER_NAME for method '{ctx.method}' but database has {len(method_services)} existing service(s), "
                        "skipping entire config save to prevent data loss"
                    )
                    return (
                        True,
                        services,
                        db_ids,
                        set(),
                        changed_services,
                        service_template_change,
                    )
            else:
                missing_ids = [
                    service.id
                    for service in db_services
                    # method-decision: deliberate: DELETION ownership again -- the removal path. Same reason as above: widening this
                    # would make the undeletable wizard service deletable through a save that omits it.
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
                        .values(
                            {
                                Services.is_draft: True,
                                Services.last_update: datetime.now().astimezone(),
                            }
                        )
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
                        .values(
                            {
                                Metadata.custom_configs_changed: True,
                                Metadata.last_custom_configs_change: datetime.now().astimezone(),
                            }
                        )
                    )
                    changed_services = True
                    if any(ctx.config.get(f"{sid}_USE_TEMPLATE", "") for sid in draftable_ids):
                        service_template_change = True

                if hard_delete_ids:
                    self.logger.debug(f"Removing {len(hard_delete_ids)} services that are no longer in the list")
                    delete_service_rows(session, hard_delete_ids)
                    session.execute(
                        update(Metadata)
                        .filter_by(id=1)
                        .values(
                            {
                                Metadata.custom_configs_changed: True,
                                Metadata.last_custom_configs_change: datetime.now().astimezone(),
                            }
                        )
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
                if (service.method == ctx.method or (service.method in EDITABLE_METHODS and ctx.method in EDITABLE_METHODS))
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
                    to_put.append(
                        Services(
                            id=draft,
                            method=ctx.method,
                            is_draft=True,
                            creation_date=current_time,
                            last_update=current_time,
                        )
                    )
                    db_ids[draft] = {"method": ctx.method, "is_draft": True}
                elif db_ids[draft]["method"] == ctx.method or (db_ids[draft]["method"] in EDITABLE_METHODS and ctx.method in EDITABLE_METHODS):
                    self.logger.debug(f"Updating draft {draft}")
                    to_update.append(
                        {
                            "model": Services,
                            "filter": {"id": draft},
                            "values": {"is_draft": True, "last_update": current_time},
                        }
                    )
                    changed_services = True

        return (
            False,
            services,
            db_ids,
            drafts,
            changed_services,
            service_template_change,
        )

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

    @staticmethod
    def _sc_load_select_options(session, setting_ids: Optional[Set[str]] = None) -> Dict[str, List[str]]:
        """Map setting_id -> flat list of canonical option values (select + multiselect),
        used to casefold-canonicalize case-insensitive selects on store (A3)."""
        options: Dict[str, List[str]] = {}
        sel_q = select(Selects.setting_id, Selects.value).order_by(Selects.order)
        msel_q = select(Multiselects.setting_id, Multiselects.value).order_by(Multiselects.order)
        if setting_ids is not None:
            sel_q = sel_q.filter(Selects.setting_id.in_(setting_ids))
            msel_q = msel_q.filter(Multiselects.setting_id.in_(setting_ids))
        for row in session.execute(sel_q):
            options.setdefault(row.setting_id, []).append(row.value or "")
        for row in session.execute(msel_q):
            options.setdefault(row.setting_id, []).append(row.value or "")
        return options

    def _sc_collect_multisite_data(self, session, ctx: _SaveConfigContext) -> None:
        """save_config phase: collect the settings/service-settings/template lookup dicts used by the
        multisite worker threads, storing them on ``ctx`` (read-only afterwards)."""
        # Collect necessary data before threading
        settings_data = session.execute(
            select(
                Settings.id,
                Settings.default,
                Settings.plugin_id,
                Settings.type,
                Settings.separator,
                Settings.case_insensitive,
                Settings.multiple,
            )
        ).all()
        select_options = self._sc_load_select_options(session)
        ctx.settings_dict = {
            s.id: {
                "default": self._empty_if_none(s.default),
                "plugin_id": s.plugin_id,
                "type": s.type,
                "separator": s.separator,
                "case_insensitive": s.case_insensitive,
                "options": select_options.get(s.id),
                # The multiple-group name, or None. The slot helpers use it to tell which suffixed
                # keys belong to the same group.
                "multiple": s.multiple,
            }
            for s in settings_data
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

        # Collect template settings. The loop variable is deliberately NOT named ``template``: it
        # used to be, and rebinding it left ``ctx.template`` holding the last Template_settings Row
        # instead of the USE_TEMPLATE id. The core templates (low/medium/high/ui) always seed rows,
        # so that happened on every multisite save. A Row is truthy and matches no lookup, so
        # ``service_config.get("USE_TEMPLATE", ctx.template)`` stopped falling back to the global
        # template -- services without their own USE_TEMPLATE lost its defaults -- and
        # ``if ctx.template:`` in _sc_process_global_settings became always-true, setting
        # local_service_template_change for every setting on every save.
        # Fixed upstream in origin/dev 907b3aa93; the previous refactor preserved the defect on
        # purpose and said so, which is why this is a rename rather than an investigation.
        templates = {}
        for template_row in session.execute(
            select(
                Template_settings.template_id,
                Template_settings.setting_id,
                Template_settings.suffix,
                Template_settings.default,
            ).order_by(Template_settings.order)
        ):
            if template_row.template_id not in templates:
                templates[template_row.template_id] = {}
            templates[template_row.template_id][(template_row.setting_id, template_row.suffix or 0)] = template_row.default
        ctx.templates = templates

    def _sc_process_service(
        self,
        ctx: _SaveConfigContext,
        server_name: str,
        service_config: Dict[str, str],
        db_ids: Dict[str, dict],
    ):
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
        alive_slots = _compute_anchored_slots(ctx, service_config, service_template, self.SUFFIX_RX) | _compute_template_slots(ctx, service_template)

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

            value = _canonicalize_stored_value(
                setting["type"],
                value,
                setting.get("separator"),
                setting.get("options"),
                setting.get("case_insensitive", False),
            )

            if server_name not in db_ids:
                self.logger.debug(f"Adding service {server_name}")
                current_time = datetime.now().astimezone()
                local_to_put.append(
                    Services(
                        id=server_name,
                        method=ctx.method,
                        is_draft=server_name in ctx.drafts,
                        creation_date=current_time,
                        last_update=current_time,
                    )
                )
                db_ids[server_name] = {
                    "method": ctx.method,
                    "is_draft": server_name in ctx.drafts,
                }
                if server_name not in ctx.drafts:
                    local_changed_services = True

            service_setting = ctx.existing_service_settings_dict.get((server_name, key, suffix))
            current_file_name = service_setting["file_name"] if service_setting else ""
            value_changed = bool(service_setting and service_setting["value"] != value)
            should_update_value = (
                # method-decision: deliberate: the compatible-methods half is delegated to _methods_are_compatible
                # (that is the EDITABLE_METHODS decision). The clause below it is autoconf's
                # own escalation: autoconf adopts a row another method owns, which no other
                # method may do.
                value_changed
                and self._methods_are_compatible(
                    ctx.method,
                    service_setting["method"],
                    allow_scheduler_override=_scheduler_can_override(ctx, f"{server_name}_{original_key}", value),
                )
            ) or (bool(service_setting) and ctx.method == "autoconf" and service_setting["method"] != "autoconf")
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting["type"], original_key, value_changed, current_file_name)

            template_setting_default = None
            if service_template:
                template_setting_default = ctx.templates.get(service_template, {}).get((key, suffix))
                local_service_template_change = True

            is_spurious_default_sibling, is_anchorless_multiple_member = _slot_flags(setting, suffix, value, template_setting_default, alive_slots)
            # A default-valued sibling of a slot that stays alive on its own (an anchor member, or a
            # template defining the slot) is round-trip material, not user intent: drop it, and clear
            # any stale row, so the field stays editable in the UI. The slot itself survives.
            if is_spurious_default_sibling:
                if service_setting and self._methods_are_compatible(
                    ctx.method,
                    service_setting["method"],
                    allow_scheduler_override=_scheduler_can_override(ctx, f"{server_name}_{original_key}", value),
                ):
                    self.logger.debug(f"Removing spurious default multiple-group setting {key}_{suffix} for service {server_name}")
                    local_to_delete.append({"model": Services_settings, "filter": {"service_id": server_name, "setting_id": key, "suffix": suffix}})
                    if value_changed:
                        local_changed_plugins.add(setting["plugin_id"])
                continue

            # Determine if we need to add, update, or delete
            if not service_setting:
                # A member of an ANCHORLESS slot is persisted even at its default value: dropping it
                # would make the whole user-declared all-default slot vanish.
                if _check_value(ctx, key, value, setting, template_setting_default, suffix) and not is_anchorless_multiple_member:
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
                local_to_update.append(
                    {
                        "model": Services,
                        "filter": {"id": server_name},
                        "values": {"last_update": datetime.now().astimezone()},
                    }
                )
                if key == "SERVER_NAME":
                    local_changed_services = True
            elif should_update_value or file_name_changed:
                if should_update_value:
                    local_changed_plugins.add(setting["plugin_id"])

                # Editing a value back down to its default removes the row, defaults being implicit
                # -- except for a member of an anchorless slot, where removing the last rows would
                # vanish the whole user-declared slot; persist the default instead.
                if should_update_value and _check_value(ctx, key, value, setting, template_setting_default, suffix) and not is_anchorless_multiple_member:
                    self.logger.debug(f"Removing setting {key} for service {server_name}")
                    local_to_delete.append(
                        {
                            "model": Services_settings,
                            "filter": {
                                "service_id": server_name,
                                "setting_id": key,
                                "suffix": suffix,
                            },
                        }
                    )
                    continue

                self.logger.debug(f"Updating setting {key} for service {server_name}")
                setting_values = {
                    "value": self._empty_if_none(value),
                    "method": ctx.method,
                }
                if setting["type"] == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                local_to_update.extend(
                    [
                        {
                            "model": Services_settings,
                            "filter": {
                                "service_id": server_name,
                                "setting_id": key,
                                "suffix": suffix,
                            },
                            "values": setting_values,
                        },
                        {
                            "model": Services,
                            "filter": {"id": server_name},
                            "values": {"last_update": datetime.now().astimezone()},
                        },
                    ]
                )
                if key == "SERVER_NAME":
                    local_changed_services = True
            elif value_changed:
                # Refused on ownership grounds only: had the methods been compatible,
                # should_update_value would be true. Never reached for autoconf (always
                # compatible) nor on the no-change path.
                _log_ownership_refusal(self.logger, ctx, f"setting {key} of service {server_name}", service_setting["method"])

        return (
            local_to_put,
            local_to_update,
            local_to_delete,
            local_changed_plugins,
            local_changed_services,
            local_service_template_change,
        )

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

        alive_slots = _compute_anchored_slots(ctx, global_config, ctx.template, self.SUFFIX_RX) | _compute_template_slots(ctx, ctx.template)

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

            value = _canonicalize_stored_value(
                setting["type"],
                value,
                setting.get("separator"),
                setting.get("options"),
                setting.get("case_insensitive", False),
            )

            global_value = session.execute(
                select(Global_values.value, Global_values.file_name, Global_values.method).filter_by(setting_id=key, suffix=suffix).limit(1)
            ).first()
            current_file_name = self._empty_if_none(global_value.file_name) if global_value else ""
            value_changed = bool(global_value and global_value.value != value)
            should_update_value = (
                # method-decision: deliberate: the compatible-methods half is delegated to _methods_are_compatible
                # (that is the EDITABLE_METHODS decision). The clause below it is autoconf's
                # own escalation: autoconf adopts a row another method owns, which no other
                # method may do.
                value_changed
                and self._methods_are_compatible(
                    ctx.method,
                    global_value.method,
                    allow_scheduler_override=_scheduler_can_override(ctx, original_key, value),
                )
            ) or (bool(global_value) and ctx.method == "autoconf" and global_value.method != "autoconf")
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting["type"], original_key, value_changed, current_file_name)

            template_setting_default = None
            if ctx.template:
                template_setting_default = ctx.templates.get(ctx.template, {}).get((key, suffix))
                local_service_template_change = True

            is_spurious_default_sibling, is_anchorless_multiple_member = _slot_flags(setting, suffix, value, template_setting_default, alive_slots)
            # Same rule as the per-service pass, on the global settings page.
            if is_spurious_default_sibling:
                if global_value and self._methods_are_compatible(
                    ctx.method,
                    global_value.method,
                    allow_scheduler_override=_scheduler_can_override(ctx, original_key, value),
                ):
                    self.logger.debug(f"Removing spurious default global multiple-group setting {key}_{suffix}")
                    local_to_delete.append({"model": Global_values, "filter": {"setting_id": key, "suffix": suffix}})
                    if value_changed:
                        local_changed_plugins.add(setting["plugin_id"])
                continue

            if not global_value:
                # A member of an ANCHORLESS slot is persisted even at its default value, else the
                # whole user-declared all-default slot would never materialise.
                if _check_value(ctx, key, value, setting, template_setting_default, suffix, True) and not is_anchorless_multiple_member:
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

                # Editing back down to the default removes the row -- except for a member of an
                # anchorless slot, where that would vanish the whole user-declared slot.
                if should_update_value and _check_value(ctx, key, value, setting, template_setting_default, suffix, True) and not is_anchorless_multiple_member:
                    self.logger.debug(f"Removing global setting {key}")
                    local_to_delete.append(
                        {
                            "model": Global_values,
                            "filter": {"setting_id": key, "suffix": suffix},
                        }
                    )
                    continue

                self.logger.debug(f"Updating global setting {key}")
                setting_values = {
                    "value": self._empty_if_none(value),
                    "method": ctx.method,
                }
                if setting["type"] == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                local_to_update.append(
                    {
                        "model": Global_values,
                        "filter": {"setting_id": key, "suffix": suffix},
                        "values": setting_values,
                    }
                )
            elif value_changed:
                # Same ownership refusal as in the per-service pass — see _log_ownership_refusal.
                _log_ownership_refusal(self.logger, ctx, f"global setting {key}", global_value.method)

        return (
            local_to_put,
            local_to_update,
            local_to_delete,
            local_changed_plugins,
            False,
            local_service_template_change,
        )

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
                # `Template_settings.value` does not exist -- the table stores the value in
                # `default` -- so this raised AttributeError whenever a non-multisite config set
                # USE_TEMPLATE without a SERVER_NAME. `.scalar()` and not `.first()`: the result is
                # split on " " a few lines down, which a Row would not survive either.
                server_name = session.execute(select(Template_settings.default).filter_by(template_id=ctx.template, setting_id="SERVER_NAME").limit(1)).scalar()

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

        # Anchor-awareness for multiple-group slots, mirroring _compute_anchored_slots in the
        # multisite branch. This pass has no ctx.settings_dict, so the data is read here directly.
        # A slot whose members are ALL at their default has no anchor row, so its default members
        # must still be persisted or the whole user-declared slot vanishes.
        # Assumes multiple-setting defaults are non-NULL strings (true for every core plugin); a
        # NULL default would need _empty_if_none normalisation to match the per-key check below.
        nm_multiple = {
            s.id: (self._empty_if_none(s.default), s.multiple) for s in session.execute(select(Settings.id, Settings.default, Settings.multiple)).all()
        }
        nm_template_defaults = {}
        nm_template_slots = set()  # (group, suffix) kept alive by the template -> must not be persisted
        if ctx.template:
            for ts in session.execute(
                select(Template_settings.setting_id, Template_settings.suffix, Template_settings.default).filter_by(template_id=ctx.template)
            ):
                nm_template_defaults[(ts.setting_id, ts.suffix or 0)] = ts.default
                if ts.suffix and ts.suffix > 0 and ts.setting_id in nm_multiple and nm_multiple[ts.setting_id][1]:
                    nm_template_slots.add((nm_multiple[ts.setting_id][1], ts.suffix))
        nm_anchored_slots = set()
        for anchor_key, anchor_value in ctx.config.items():
            anchor_suffix = 0
            anchor_base = anchor_key
            if self.SUFFIX_RX.search(anchor_base):
                anchor_suffix = int(anchor_base.split("_")[-1])
                anchor_base = anchor_base[: -len(str(anchor_suffix)) - 1]
            if anchor_suffix == 0 or anchor_base not in nm_multiple or not nm_multiple[anchor_base][1]:
                continue
            anchor_default = nm_template_defaults.get((anchor_base, anchor_suffix), nm_multiple[anchor_base][0])
            if anchor_value != anchor_default:
                nm_anchored_slots.add((nm_multiple[anchor_base][1], anchor_suffix))

        for original_key, value in ctx.config.items():
            key = deepcopy(original_key)
            suffix = 0
            if self.SUFFIX_RX.search(key):
                suffix = int(key.split("_")[-1])
                key = key[: -len(str(suffix)) - 1]

            setting = session.execute(
                select(
                    Settings.default,
                    Settings.plugin_id,
                    Settings.type,
                    Settings.separator,
                    Settings.case_insensitive,
                )
                .filter_by(id=key)
                .limit(1)
            ).first()

            if not setting:
                continue

            options = None
            if setting.type in ("select", "multiselect"):
                options = self._sc_load_select_options(session, {key}).get(key)

            value = _canonicalize_stored_value(
                setting.type,
                value,
                setting.separator,
                options,
                setting.case_insensitive,
            )

            global_value = session.execute(
                select(Global_values.value, Global_values.file_name, Global_values.method).filter_by(setting_id=key, suffix=suffix).limit(1)
            ).first()
            current_file_name = self._empty_if_none(global_value.file_name) if global_value else ""
            value_changed = bool(global_value and global_value.value != value)
            should_update_value = bool(
                global_value
                and self._methods_are_compatible(
                    ctx.method,
                    global_value.method,
                    allow_scheduler_override=_scheduler_can_override(ctx, original_key, value),
                )
                and value_changed
            )
            target_file_name, file_name_changed = _get_setting_file_name(ctx, setting.type, original_key, value_changed, current_file_name)

            template_setting = None
            if ctx.template:
                template_setting = session.execute(
                    select(Template_settings.default).filter_by(template_id=ctx.template, setting_id=key, suffix=suffix).limit(1)
                ).first()
                service_template_change = True

            nm_mult = nm_multiple.get(key, (None, None))[1]
            nm_is_anchorless = suffix > 0 and nm_mult is not None and (nm_mult, suffix) not in nm_anchored_slots and (nm_mult, suffix) not in nm_template_slots
            nm_default = template_setting.default if template_setting is not None else setting.default

            if not global_value:
                # An anchorless slot's default member must be persisted, else the whole slot vanishes.
                if value == nm_default and not nm_is_anchorless:
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

                if should_update_value and value == nm_default and not nm_is_anchorless:
                    self.logger.debug(f"Removing global setting {key}")
                    to_delete.append(
                        {
                            "model": Global_values,
                            "filter": {"setting_id": key, "suffix": suffix},
                        }
                    )
                    continue

                self.logger.debug(f"Updating global setting {key}")
                setting_values = {
                    "value": self._empty_if_none(value),
                    "method": ctx.method,
                }
                if setting.type == "file" and (file_name_changed or value_changed):
                    setting_values["file_name"] = target_file_name
                to_update.append(
                    {
                        "model": Global_values,
                        "filter": {"setting_id": key, "suffix": suffix},
                        "values": setting_values,
                    }
                )
            elif value_changed:
                # Same ownership refusal as in the multisite passes — see _log_ownership_refusal.
                # This is the pass PATCH /global_settings lands in (skip_service_management=True),
                # so it is the one that backs that endpoint's 409.
                _log_ownership_refusal(self.logger, ctx, f"global setting {key}", global_value.method)

        return changed_services, service_template_change
