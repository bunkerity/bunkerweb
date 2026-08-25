#!/usr/bin/env python3
from copy import deepcopy
from re import DOTALL, error as RegexError, escape, search
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from model import Global_values, Services, Services_settings, Settings, Template_settings  # type: ignore

from common_utils import split_templates  # type: ignore

from resource_group_resolver import value_for_validation  # type: ignore

from ports import port_list_setting  # type: ignore

from sqlalchemy import join, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import scoped_session

from .common import DatabaseMixinBase, canonicalize_setting_value, retry_on_transient_db_errors


class DatabaseConfigReadMixin(DatabaseMixinBase):
    """Configuration reads and setting validation."""

    def is_valid_setting(
        self,
        setting: str,
        *,
        value: Optional[str] = None,
        multisite: bool = False,
        session: Optional[scoped_session] = None,
        extra_services: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Check if the setting exists in the database, if it's valid and if the value is valid"""

        def check_setting(session: scoped_session, setting: str, value: Optional[str], multisite: bool = False) -> Tuple[bool, str]:
            try:
                multiple = False
                if self.SUFFIX_RX.search(setting):
                    setting = setting.rsplit("_", 1)[0]
                    multiple = True

                db_setting = session.scalars(select(Settings).filter_by(id=setting).limit(1)).first()

                if not db_setting:
                    for service in extra_services or []:
                        if setting.startswith(f"{service}_"):
                            db_setting = session.scalars(select(Settings).filter_by(id=setting.replace(f"{service}_", "")).limit(1)).first()
                            break

                    if not db_setting:
                        for service in session.execute(select(Services.id)):
                            if setting.startswith(f"{service.id}_"):
                                db_setting = session.scalars(select(Settings).filter_by(id=setting.replace(f"{service.id}_", "")).limit(1)).first()
                                multisite = True
                                break

                if not db_setting:
                    return False, "missing"

                if multisite and db_setting.context != "multisite":
                    return False, "not multisite"
                elif multiple and db_setting.multiple is None:
                    return False, "not multiple"

                if value is not None:
                    # Only select/multiselect consume options, and both relationships are lazy —
                    # loading them for every setting type cost one extra query per validated key.
                    options: List[str] = []
                    if db_setting.type == "select":
                        options = [option.value or "" for option in db_setting.selects]
                    elif db_setting.type == "multiselect":
                        options = [option.value or "" for option in db_setting.multiselects]
                    canonical = canonicalize_setting_value(db_setting.type, value, db_setting.separator, options, db_setting.case_insensitive)
                    if canonical is None and db_setting.type in ("size", "duration"):
                        if not self._ignore_regex_check:
                            return False, f"not a valid {db_setting.type}"
                    else:
                        value = canonical
                    try:
                        regex_flags = DOTALL if db_setting.type == "file" else 0
                        if not self._ignore_regex_check and search(db_setting.regex, value_for_validation(db_setting.id, value), regex_flags) is None:
                            return False, f"not matching regex: {db_setting.regex!r}"
                    except RegexError:
                        return False, f"invalid regex: {db_setting.regex!r}"

                return True, ""
            except (ProgrammingError, OperationalError) as e:
                return False, str(e)

        if session:
            return check_setting(session, setting, value, multisite)

        with self._db_session() as session:
            return check_setting(session, setting, value, multisite)

    @retry_on_transient_db_errors
    def get_non_default_settings(
        self,
        global_only: bool = False,
        methods: bool = False,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
        *,
        service: Optional[str] = None,
        original_config: Optional[Dict[str, Any]] = None,
        original_multisite: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get the config from the database"""
        filtered_settings = set(filtered_settings or [])

        if filtered_settings and not global_only:
            filtered_settings.update(("SERVER_NAME", "MULTISITE"))

        with self._db_session() as session:
            config = original_config or {}
            multisite = original_multisite or set()

            # Define the join operation
            j = join(Settings, Global_values, Settings.id == Global_values.setting_id)

            # Define the select statement.
            #
            # `suffix` is a tiebreak, not decoration: `Settings.order` carries the same value for
            # every repetition of one `multiple` setting, so without it the relative position of
            # `HTTP_PORT` and `HTTP_PORT_1` in the returned dict is whatever the engine happens to
            # give back. `collect_ports` and `list_moved` both read that dict order and
            # compare ORDERED sequences, and the per-service templates render their `listen` lines
            # straight from it -- so the same database answered differently on PostgreSQL than on
            # SQLite. `db_methods/services.py:60-70` and Lua's `port_list` already order by suffix;
            # this is the same rule applied at the source.
            stmt = (
                select(
                    Settings.id.label("setting_id"),
                    Settings.context,
                    Settings.type,
                    Settings.default,
                    Settings.multiple,
                    Global_values.value,
                    Global_values.file_name,
                    Global_values.suffix,
                    Global_values.method,
                )
                .select_from(j)
                .order_by(Settings.order, Global_values.suffix)
            )

            if filtered_settings:
                stmt = stmt.where(Settings.id.in_(filtered_settings))

            # Execute the query and fetch all results
            results = session.execute(stmt).fetchall()

            for global_value in results:
                setting_id = global_value.setting_id + (f"_{global_value.suffix}" if global_value.multiple and global_value.suffix > 0 else "")
                config[setting_id] = {
                    "value": self._empty_if_none(global_value.value),
                    "file_name": self._empty_if_none(global_value.file_name) if global_value.type == "file" else "",
                    "global": True,
                    "method": global_value.method,
                    "default": self._empty_if_none(global_value.default),
                    "template": None,
                }

                if global_value.context == "multisite":
                    multisite.add(setting_id)

            is_multisite = config.get("MULTISITE", {"value": "no"})["value"] == "yes"

            services = select(Services.id, Services.is_draft)

            if not with_drafts:
                services = services.filter_by(is_draft=False)

            if not global_only and is_multisite:
                # Build list of service IDs and their draft status efficiently
                service_list = []
                is_draft_default = self._empty_if_none(config.get("IS_DRAFT", {"value": "no"})["value"])
                for db_service in session.execute(services):
                    if service and db_service.id != service:
                        continue
                    service_list.append((db_service.id, db_service.is_draft))
                    config[f"{db_service.id}_IS_DRAFT"] = {
                        "value": "yes" if db_service.is_draft else "no",
                        "global": False,
                        "method": "default",
                        "default": is_draft_default,
                        "template": None,
                    }

                servers = " ".join(s[0] for s in service_list)

                # Pre-build multisite defaults mapping for efficient lookup
                # Share the same dictionary objects instead of creating copies
                multisite_defaults = {key: config[key] for key in multisite if key in config}

                # The port lists are the one family this materialisation must NOT copy when the
                # caller asked for the non-default settings alone. A service REPLACES the global
                # port list rather than extending it (`ports.drop_inherited_ports`), and the only
                # thing that can say "this service declared a port" is the presence of its row.
                # An inherited copy makes every service look like it declared the whole global
                # list, so a service that declares `HTTP_PORT=9000` beside a global
                # `HTTP_PORT_1=8081` keeps listening on 8081, and one that declares only
                # `HTTP_PORT_1=9081` keeps listening on the global `HTTP_PORT` too.
                #
                # `get_config` (original_config is not None) DOES need the copies: it strips the
                # `<service>_` prefix on the way out (:443-447), so dropping them would remove the
                # port settings from the per-service editor entirely. Its consumers merge the
                # globals themselves (`Templator._get_server_config`, `ports.services_from_config`),
                # so the full view stays the inherited one and the non-default view stays factual.
                skip_port_lists = original_config is None

                # Populate service-specific entries using shared references
                # This is still O(services * multisite_settings) but avoids deepcopy overhead
                for service_id, _ in service_list:
                    for key, value in multisite_defaults.items():
                        if skip_port_lists and port_list_setting(key) is not None:
                            continue
                        # Keep already-materialized service values (notably *_IS_DRAFT from bw_services).
                        config.setdefault(f"{service_id}_{key}", value)

                # Define the join operation
                j = join(Services, Services_settings, Services.id == Services_settings.service_id)
                j = j.join(Settings, Settings.id == Services_settings.setting_id)

                # Define the select statement. Same `suffix` tiebreak as the global query above,
                # for the same reason.
                stmt = (
                    select(
                        Services.id.label("service_id"),
                        Settings.id.label("setting_id"),
                        Settings.type,
                        Settings.default,
                        Settings.multiple,
                        Services_settings.value,
                        Services_settings.file_name,
                        Services_settings.suffix,
                        Services_settings.method,
                    )
                    .select_from(j)
                    .order_by(Services.id, Settings.order, Services_settings.suffix)
                )

                if not with_drafts:
                    stmt = stmt.where(Services.is_draft == False)  # noqa: E712

                if filtered_settings:
                    stmt = stmt.where(Settings.id.in_(filtered_settings))

                # Execute the query and fetch all results
                results = session.execute(stmt).fetchall()

                for result in results:
                    if service and result.service_id != service:
                        continue
                    value = self._empty_if_none(result.value)

                    if result.setting_id == "SERVER_NAME" and search(r"^" + escape(result.service_id) + r"( |$)", value) is None:
                        split = set(value.split())
                        split.discard(result.service_id)
                        value = result.service_id + " " + " ".join(split)

                    config[f"{result.service_id}_{result.setting_id}" + (f"_{result.suffix}" if result.multiple and result.suffix else "")] = {
                        "value": self._empty_if_none(value),
                        "file_name": self._empty_if_none(result.file_name) if result.type == "file" else "",
                        "global": False,
                        "method": result.method,
                        "default": self._empty_if_none(config.get(result.setting_id, {"value": self._empty_if_none(result.default)})["value"]),
                        "template": None,
                    }
            else:
                servers = " ".join(db_service.id for db_service in session.execute(services))

            config["SERVER_NAME"] = {
                "value": servers,
                "global": True,
                "method": "scheduler",
                "default": "",
                "template": None,
            }

            if service:
                # Use list() to avoid modifying dict during iteration, more efficient than copy()
                for key in list(config.keys()):
                    if (original_config is None or key not in ("SERVER_NAME", "MULTISITE", "USE_TEMPLATE")) and not key.startswith(f"{service}_"):
                        del config[key]
                        continue
                    if original_config is None:
                        config[key.replace(f"{service}_", "")] = config.pop(key)

            if not methods:
                # Avoid full dictionary copy - iterate over keys and update in place
                for key in list(config.keys()):
                    config[key] = config[key]["value"]

            return config

    @retry_on_transient_db_errors
    def get_config(
        self,
        global_only: bool = False,
        methods: bool = False,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
        *,
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the config from the database"""
        filtered_settings = set(filtered_settings or [])

        if filtered_settings and not global_only:
            filtered_settings.update(("SERVER_NAME", "MULTISITE", "USE_TEMPLATE"))

        config = {}
        multisite = set()
        multiple_groups = {}
        with self._db_session() as session:
            query = select(
                Settings.id,
                Settings.context,
                Settings.default,
                Settings.multiple,
            ).order_by(Settings.order)

            if filtered_settings:
                query = query.filter(Settings.id.in_(filtered_settings))

            for setting in session.execute(query):
                config[setting.id] = {
                    "value": self._empty_if_none(setting.default),
                    "global": True,
                    "method": "default",
                    "default": self._empty_if_none(setting.default),
                    "template": None,
                }
                if setting.context == "multisite":
                    multisite.add(setting.id)
                if setting.multiple:
                    multiple_groups[setting.id] = setting.multiple

        config = self.get_non_default_settings(
            global_only=global_only,
            methods=True,
            with_drafts=with_drafts,
            filtered_settings=filtered_settings,
            service=service,
            original_config=config,
            original_multisite=multisite,
        )

        template_used = config.get("USE_TEMPLATE", {"value": ""})["value"]
        # USE_TEMPLATE is an ORDERED LIST (multivalue, separator " "): layers apply left to
        # right and a later one overrides an earlier one. The skip-guards below are what make
        # last-wins free -- a key written by an earlier layer carries method "default", so the
        # guard does not trip and the next layer overwrites it. Only a non-default method (a
        # real row the user or a component owns) stops a layer.
        global_template_ids = split_templates(template_used)
        templates = {"global": template_used} if template_used else {}
        with self._db_session() as session:
            if global_template_ids:
                query = (
                    select(Template_settings.template_id, Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                    .filter(Template_settings.template_id.in_(set(global_template_ids)))
                    .order_by(Template_settings.order)
                )

                if filtered_settings:
                    query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                # Grouped first, then replayed in DECLARED order: the query returns the layers
                # interleaved by Template_settings.order, which carries no precedence at all.
                global_template_settings = {}
                for template_setting in session.execute(query):
                    global_template_settings.setdefault(template_setting.template_id, []).append(template_setting)

                for template_id in global_template_ids:
                    for template_setting in global_template_settings.get(template_id, []):
                        key = template_setting.setting_id + (f"_{template_setting.suffix}" if template_setting.suffix > 0 else "")
                        if key in config and config[key]["method"] != "default":
                            continue

                        config[key] = {
                            "value": self._empty_if_none(template_setting.default),
                            "global": True,
                            "method": "default",
                            "default": self._empty_if_none(template_setting.default),
                            # The LAYER this value came from, never the whole list: the UI's
                            # provenance checks and the save layer's "drop the outgoing
                            # template's defaults" rule both need the single owning template.
                            "template": template_id,
                        }

            if not global_only and config["MULTISITE"]["value"] == "yes":
                server_names = config["SERVER_NAME"]["value"].split()

                # Collect the ORDERED layer list of every service, and the flat set of ids to
                # fetch. Two services may share the same layers in a DIFFERENT order, so the
                # per-service order is kept per service and never collapsed into the id set.
                service_template_ids = {}
                used_template_ids = set()
                for service_id in server_names:
                    service_template_used = config.get(f"{service_id}_USE_TEMPLATE", {"value": self._empty_if_none(template_used)})["value"]
                    if service_template_used:
                        templates[service_id] = service_template_used
                        layer_ids = split_templates(service_template_used)
                        if layer_ids:
                            service_template_ids[service_id] = layer_ids
                            used_template_ids.update(layer_ids)

                # Batch query: fetch all template settings for all used templates at once
                if used_template_ids:
                    query = (
                        select(Template_settings.template_id, Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                        .filter(Template_settings.template_id.in_(used_template_ids))
                        .order_by(Template_settings.order)
                    )

                    if filtered_settings:
                        query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                    # Group template settings by template_id for efficient lookup
                    template_settings_map = {}
                    for setting in session.execute(query):
                        template_settings_map.setdefault(setting.template_id, []).append(setting)

                    # Apply each service's OWN layers in its OWN order. Iterating per template
                    # (as this did while one service meant one template) cannot express that:
                    # two services sharing "low high" and "high low" would both get whichever
                    # order the outer loop happened to visit.
                    for service_id, layer_ids in service_template_ids.items():
                        for tmpl_id in layer_ids:
                            for setting in template_settings_map.get(tmpl_id, []):
                                key = f"{service_id}_{setting.setting_id}" + (f"_{setting.suffix}" if setting.suffix > 0 else "")
                                if key in config and config[key]["method"] != "default" and not config[key]["global"]:
                                    continue

                                config[key] = {
                                    "value": self._empty_if_none(setting.default),
                                    "global": False,
                                    "method": "default",
                                    "default": self._empty_if_none(setting.default),
                                    # The owning LAYER, not the list -- see the global branch.
                                    "template": tmpl_id,
                                }

        multiple = {}
        services = config["SERVER_NAME"]["value"].split()
        services_set = set(services)  # O(1) lookup for service prefix matching

        # Process config items - use list(items()) which is more memory efficient than copy().items()
        # for large dicts since it creates a list of tuples, not a full dict copy
        for key, data in list(config.items()):
            new_value = None
            if service:
                data = config.pop(key)
                if not key.startswith(f"{service}_"):
                    continue
                key = key.replace(f"{service}_", "")
                new_value = data

            if not methods:
                new_value = data["value"]

            match = self.SUFFIX_RX.search(key)
            if match:
                window = "global"
                matched_group = multiple_groups.get(match.group("setting"), None)
                if matched_group is None:
                    # Use set lookup and underscore scanning instead of O(n) service iteration
                    underscore_pos = 0
                    while True:
                        underscore_pos = key.find("_", underscore_pos)
                        if underscore_pos == -1:
                            break
                        potential_service = key[:underscore_pos]
                        if potential_service in services_set:
                            window = potential_service
                            matched_group = multiple_groups.get(match.group("setting").replace(f"{potential_service}_", ""), None)
                            break
                        underscore_pos += 1

                if matched_group is not None:
                    multiple.setdefault(matched_group, {}).setdefault(window, set()).add(int(match.group("suffix")))

            if new_value is not None:
                config[key] = new_value

        if multiple:
            with self._db_session() as session:
                group_settings = session.execute(select(Settings.id, Settings.default).filter(Settings.multiple.in_(multiple.keys()))).all()

                # USE_TEMPLATE is an ORDERED LIST here too. This block used to pass the window's
                # RAW value straight to `filter_by(template_id=...)`, which matches no row at all
                # once it names more than one layer -- so every re-materialised group member fell
                # back to its plugin default -- and then wrote that whole list into the per-key
                # `template` provenance (`HOST_1` carrying `'template': 'base hard'`), which the
                # UI's provenance checks and the save layer's outgoing-template rule both read as
                # a single template id.
                window_layers = {}
                for windows in multiple.values():
                    for window in windows:
                        if window not in window_layers:
                            window_layers[window] = split_templates(templates.get(window, "") or templates.get("global", ""))

                # ONE query for every (layer, setting, suffix) in play, instead of the per-suffix
                # `scalars()` the old block issued from inside a triple loop. Deliberately NOT
                # reusing the overlay's `template_settings_map` above: that one is narrowed by
                # `filtered_settings`, while this block legitimately re-materialises SIBLING
                # members of a group that the filter never asked for.
                referenced_layers = {layer for layers in window_layers.values() for layer in layers}
                layer_defaults = {}
                if referenced_layers:
                    for row in session.execute(
                        select(
                            Template_settings.template_id,
                            Template_settings.setting_id,
                            Template_settings.suffix,
                            Template_settings.default,
                        ).filter(
                            Template_settings.template_id.in_(referenced_layers),
                            Template_settings.setting_id.in_({group_setting.id for group_setting in group_settings}),
                        )
                    ):
                        layer_defaults[(row.template_id, row.setting_id, row.suffix or 0)] = self._empty_if_none(row.default)

                for setting in group_settings:
                    group_key = multiple_groups.get(setting.id)
                    if group_key is None or group_key not in multiple:
                        continue

                    for window, suffixes in multiple[group_key].items():
                        layers = window_layers.get(window, [])
                        for suffix in map(int, suffixes):
                            if window == "global" or service:
                                key = f"{setting.id}_{suffix}"
                            else:
                                key = f"{window}_{setting.id}_{suffix}"

                            default = self._empty_if_none(setting.default)
                            value = deepcopy(default)
                            # LAST-WINS, resolved per layer: walk the list backwards and stop at
                            # the first layer that actually supplies this member. `owning_template`
                            # stays None when no layer does -- a plugin default is NOT
                            # template-provided, and claiming otherwise makes save_scope treat it
                            # as an outgoing template value and drop it on a template change.
                            #
                            # This resolution is LIVE, not defensive. The overlay above usually
                            # pre-empts it (it has already written every member a layer declares,
                            # and `filtered_settings` -- the one thing that makes it skip one --
                            # narrows the base query at `:294` too, so the setting would not reach
                            # `multiple_groups` either). But the `service=` route reaches it: the
                            # loop above POPS every key and re-adds only the `{service}_`-prefixed
                            # ones, so a member the GLOBAL overlay wrote is gone from `config` by
                            # the time this block runs, and this block re-materialises it.
                            # Pinned by test_config_read.py.
                            #
                            # For the record, a pre-existing shape this does not change: under
                            # `service=` the key reaching the window scan has ALREADY had its
                            # service prefix stripped, so `multiple_groups` hits on the first try
                            # and `window` stays "global". This block therefore resolves against
                            # the GLOBAL layer list even for a service that carries its own.
                            owning_template = None
                            for template_id in reversed(layers):
                                layer_value = layer_defaults.get((template_id, setting.id, suffix))
                                if layer_value is not None:
                                    value = layer_value
                                    owning_template = template_id
                                    break

                            if key not in config:
                                config[key] = (
                                    {
                                        "value": value,
                                        "global": True,
                                        "method": "default",
                                        "default": default,
                                        "template": owning_template,
                                    }
                                    if methods
                                    else value
                                )

        return config

    def get_services_settings(self, methods: bool = False, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        config = self.get_config(methods=methods, with_drafts=with_drafts)
        service_names = config["SERVER_NAME"]["value"].split() if methods else config["SERVER_NAME"].split()
        for service in service_names:
            service_settings = []
            tmp_config = config.copy()

            for key, value in tmp_config.copy().items():
                if key.startswith(f"{service}_"):
                    setting = key.replace(f"{service}_", "")
                    service_settings.append(setting)
                    tmp_config[setting] = tmp_config.pop(key)
                elif any(key.startswith(f"{s}_") for s in service_names):
                    tmp_config.pop(key)
                elif key not in service_settings:
                    tmp_config[key] = (
                        {
                            "value": self._empty_if_none(value["value"]),
                            "global": value["global"],
                            "method": value["method"],
                            "default": self._empty_if_none(value["default"]),
                            "template": value["template"],
                        }
                        if methods
                        else value
                    )

            services.append(tmp_config)

        return services
