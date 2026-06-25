#!/usr/bin/env python3
from copy import deepcopy
from re import DOTALL, error as RegexError, escape, search
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from model import Global_values, Services, Services_settings, Settings, Template_settings  # type: ignore

from common_utils import normalize_check_value, normalize_list_value  # type: ignore
from unit_parser import normalize_unit  # type: ignore
from resource_group_resolver import value_for_validation  # type: ignore

from sqlalchemy import join, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import scoped_session

from .common import DatabaseMixinBase, retry_on_transient_db_errors


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
                    if db_setting.type == "check":
                        value = normalize_check_value(value)
                    elif db_setting.type in ("size", "duration"):
                        # The parser is authoritative for size/duration: the regex cannot
                        # encode NGINX's unit-order rule, so an unparseable value is invalid.
                        canonical = normalize_unit(db_setting.type, value)
                        if canonical is None:
                            if not self._ignore_regex_check:
                                return False, f"not a valid {db_setting.type}"
                        else:
                            value = canonical
                    elif db_setting.type in ("multiselect", "multivalue"):
                        value = normalize_list_value(value, db_setting.separator or " ")
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

            # Define the select statement
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
                .order_by(Settings.order)
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

                # Populate service-specific entries using shared references
                # This is still O(services * multisite_settings) but avoids deepcopy overhead
                for service_id, _ in service_list:
                    for key, value in multisite_defaults.items():
                        # Keep already-materialized service values (notably *_IS_DRAFT from bw_services).
                        config.setdefault(f"{service_id}_{key}", value)

                # Define the join operation
                j = join(Services, Services_settings, Services.id == Services_settings.service_id)
                j = j.join(Settings, Settings.id == Services_settings.setting_id)

                # Define the select statement
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
                    .order_by(Services.id, Settings.order)
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
        templates = {"global": template_used} if template_used else {}
        with self._db_session() as session:
            if template_used:
                query = (
                    select(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template_used)
                    .order_by(Template_settings.order)
                )

                if filtered_settings:
                    query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                for template_setting in session.execute(query):
                    key = template_setting.setting_id + (f"_{template_setting.suffix}" if template_setting.suffix > 0 else "")
                    if key in config and config[key]["method"] != "default":
                        continue

                    config[key] = {
                        "value": self._empty_if_none(template_setting.default),
                        "global": True,
                        "method": "default",
                        "default": self._empty_if_none(template_setting.default),
                        "template": template_used,
                    }

            if not global_only and config["MULTISITE"]["value"] == "yes":
                server_names = config["SERVER_NAME"]["value"].split()

                # Collect all unique templates used by services
                service_templates = {}
                for service_id in server_names:
                    service_template_used = config.get(f"{service_id}_USE_TEMPLATE", {"value": self._empty_if_none(template_used)})["value"]
                    if service_template_used:
                        templates[service_id] = service_template_used
                        service_templates.setdefault(service_template_used, []).append(service_id)

                # Batch query: fetch all template settings for all used templates at once
                if service_templates:
                    template_ids = list(service_templates.keys())
                    query = (
                        select(Template_settings.template_id, Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                        .filter(Template_settings.template_id.in_(template_ids))
                        .order_by(Template_settings.order)
                    )

                    if filtered_settings:
                        query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                    # Group template settings by template_id for efficient lookup
                    template_settings_map = {}
                    for setting in session.execute(query):
                        template_settings_map.setdefault(setting.template_id, []).append(setting)

                    # Apply template settings to each service that uses them
                    for tmpl_id, service_ids in service_templates.items():
                        tmpl_settings = template_settings_map.get(tmpl_id, [])
                        for service_id in service_ids:
                            for setting in tmpl_settings:
                                key = f"{service_id}_{setting.setting_id}" + (f"_{setting.suffix}" if setting.suffix > 0 else "")
                                if key in config and config[key]["method"] != "default" and not config[key]["global"]:
                                    continue

                                config[key] = {
                                    "value": self._empty_if_none(setting.default),
                                    "global": False,
                                    "method": "default",
                                    "default": self._empty_if_none(setting.default),
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
                query = select(Settings.id, Settings.default).filter(Settings.multiple.in_(multiple.keys()))

                for setting in session.execute(query):
                    group_key = multiple_groups.get(setting.id)
                    if group_key is None or group_key not in multiple:
                        continue

                    for window, suffixes in multiple[group_key].items():
                        template = templates.get(window, "") or templates.get("global", "")
                        for suffix in map(int, suffixes):
                            if window == "global" or service:
                                key = f"{setting.id}_{suffix}"
                            else:
                                key = f"{window}_{setting.id}_{suffix}"

                            default = self._empty_if_none(setting.default)
                            value = deepcopy(default)
                            if template:
                                template_setting = session.scalars(
                                    select(Template_settings).filter_by(template_id=template, setting_id=setting.id, suffix=suffix).limit(1)
                                ).first()
                                if template_setting is not None:
                                    value = self._empty_if_none(template_setting.default)

                            if key not in config:
                                config[key] = (
                                    {
                                        "value": value,
                                        "global": True,
                                        "method": "default",
                                        "default": default,
                                        "template": template,
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
