#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from model import Global_values, Metadata, Plugins, Services_settings, Settings, Template_custom_configs, Template_settings, Template_steps, Templates  # type: ignore

from common_utils import bytes_hash, normalize_check_value, normalize_list_value  # type: ignore
from unit_parser import normalize_unit  # type: ignore

from sqlalchemy import case, delete, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase


class DatabaseTemplatesMixin(DatabaseMixinBase):
    """Service template management."""

    def get_templates(self, plugin: Optional[str] = None) -> Dict[str, dict]:
        """Get templates."""
        with self._db_session() as session:
            query = select(Templates.id, Templates.plugin_id, Templates.name, Templates.method, Templates.creation_date, Templates.last_update).order_by(
                case((Templates.id == "low", 1), (Templates.id == "medium", 2), (Templates.id == "high", 3), else_=4), Templates.name
            )

            if plugin:
                query = query.filter_by(plugin_id=plugin)

            templates = {}
            for template in session.execute(query).all():
                templates[template.id] = {
                    "plugin_id": template.plugin_id,
                    "name": template.name,
                    "method": template.method,
                    "creation_date": template.creation_date,
                    "last_update": template.last_update,
                    "settings": {},
                    "configs": {},
                    "steps": [],
                }

                steps_settings = {}
                for setting in session.execute(
                    select(Template_settings.setting_id, Template_settings.step_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template.id)
                    .order_by(Template_settings.order)
                ):
                    key = f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                    templates[template.id]["settings"][key] = self._empty_if_none(setting.default)

                    if setting.step_id:
                        if setting.step_id not in steps_settings:
                            steps_settings[setting.step_id] = []
                        steps_settings[setting.step_id].append(key)

                steps_configs = {}
                for config in session.execute(
                    select(Template_custom_configs.step_id, Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.data)
                    .filter_by(template_id=template.id)
                    .order_by(Template_custom_configs.order)
                ):
                    key = f"{config.type}/{config.name}.conf"
                    templates[template.id]["configs"][key] = config.data.decode("utf-8")

                    if config.step_id:
                        if config.step_id not in steps_configs:
                            steps_configs[config.step_id] = []
                        steps_configs[config.step_id].append(key)

                for step in session.execute(
                    select(Template_steps.id, Template_steps.title, Template_steps.subtitle).filter_by(template_id=template.id).order_by(Template_steps.id)
                ):
                    step_data = {"title": step.title, "subtitle": self._empty_if_none(step.subtitle)}
                    if step.id in steps_settings:
                        step_data["settings"] = steps_settings[step.id]
                    if step.id in steps_configs:
                        step_data["configs"] = steps_configs[step.id]
                    templates[template.id]["steps"].append(step_data)

            return templates

    def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a template with full metadata for edition."""
        with self._db_session() as session:
            template = session.scalars(select(Templates).filter_by(id=template_id).limit(1)).first()
            if not template:
                return None

            steps: List[Dict[str, Any]] = []
            step_lookup: Dict[int, Dict[str, Any]] = {}
            for step in session.execute(
                select(Template_steps.id, Template_steps.title, Template_steps.subtitle).filter_by(template_id=template_id).order_by(Template_steps.id)
            ):
                data = {
                    "id": step.id,
                    "title": step.title,
                    "subtitle": self._empty_if_none(step.subtitle),
                    "settings": [],
                    "configs": [],
                }
                steps.append(data)
                step_lookup[step.id] = data

            settings_payload: List[Dict[str, Any]] = []
            for setting in session.execute(
                select(
                    Template_settings.setting_id,
                    Template_settings.step_id,
                    Template_settings.default,
                    Template_settings.suffix,
                    Template_settings.order,
                )
                .filter_by(template_id=template_id)
                .order_by(Template_settings.order)
            ):
                key = f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                payload = {
                    "key": key,
                    "setting_id": setting.setting_id,
                    "suffix": setting.suffix or 0,
                    "default": self._empty_if_none(setting.default),
                    "step_id": setting.step_id,
                    "order": setting.order,
                }
                settings_payload.append(payload)
                if setting.step_id in step_lookup:
                    step_lookup[setting.step_id]["settings"].append(key)

            configs_payload: List[Dict[str, Any]] = []
            for config in session.execute(
                select(
                    Template_custom_configs.type,
                    Template_custom_configs.name,
                    Template_custom_configs.step_id,
                    Template_custom_configs.data,
                    Template_custom_configs.order,
                )
                .filter_by(template_id=template_id)
                .order_by(Template_custom_configs.order)
            ):
                key = f"{config.type}/{config.name}.conf"
                payload = {
                    "key": key,
                    "type": config.type,
                    "name": config.name,
                    "step_id": config.step_id,
                    "data": config.data.decode("utf-8", errors="replace"),
                    "order": config.order,
                }
                configs_payload.append(payload)
                if config.step_id in step_lookup:
                    step_lookup[config.step_id]["configs"].append(key)

            return {
                "id": template.id,
                "name": template.name,
                "plugin_id": template.plugin_id,
                "method": template.method,
                "creation_date": template.creation_date,
                "last_update": template.last_update,
                "steps": steps,
                "settings": settings_payload,
                "configs": configs_payload,
            }

    def get_template_settings(self, template_id: str) -> Dict[str, Any]:
        """Get templates settings."""
        with self._db_session() as session:
            settings = {}
            for setting in session.execute(
                select(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                .filter_by(template_id=template_id)
                .order_by(Template_settings.order)
            ):
                settings[f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id] = self._empty_if_none(setting.default)
            return settings

    def _prepare_template_entities(
        self,
        session,
        template_id: str,
        settings: Dict[str, Any],
        steps: List[Dict[str, Any]],
        configs: Optional[List[Dict[str, Any]]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate the incoming template payload and prepare ORM-ready entity dictionaries."""

        if not steps:
            return "A template must contain at least one step", [], [], []

        normalized_settings: Dict[str, str] = {}
        for raw_key, raw_value in settings.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                return "Template settings keys must be non-empty strings", [], [], []
            normalized_settings[raw_key.strip()] = "" if raw_value is None else str(raw_value)

        step_entities: List[Dict[str, Any]] = []
        step_assignments: Dict[str, int] = {}
        ordered_setting_keys: List[str] = []
        config_step_map: Dict[str, int] = {}

        for index, step in enumerate(steps, start=1):
            title = str(step.get("title", "")).strip()
            if not title:
                return f"Step {index} must have a title", [], [], []

            subtitle_value = step.get("subtitle")
            subtitle = None
            if subtitle_value is not None:
                subtitle = str(subtitle_value).strip() or None

            step_entities.append(
                {
                    "id": index,
                    "template_id": template_id,
                    "title": title,
                    "subtitle": subtitle,
                }
            )

            step_settings = step.get("settings") or []
            if not isinstance(step_settings, list):
                return f"Step {index} settings must be a list", [], [], []

            for setting_ref_raw in step_settings:
                if not isinstance(setting_ref_raw, str):
                    return f"Step {index} contains an invalid setting reference", [], [], []
                setting_ref = setting_ref_raw.strip()
                if setting_ref not in normalized_settings:
                    return f"Step {index} references unknown setting {setting_ref}", [], [], []
                if setting_ref in step_assignments:
                    return f"Setting {setting_ref} is assigned to multiple steps", [], [], []
                step_assignments[setting_ref] = index
                ordered_setting_keys.append(setting_ref)

            step_configs = step.get("configs") or []
            if step_configs is None:
                step_configs = []
            if not isinstance(step_configs, list):
                return f"Step {index} configs must be a list", [], [], []

            for config_ref_raw in step_configs:
                if not isinstance(config_ref_raw, str):
                    return f"Step {index} contains an invalid config reference", [], [], []
                normalized_ref = self._normalize_template_config_reference(config_ref_raw)
                if not normalized_ref:
                    return f"Step {index} contains an invalid config reference", [], [], []
                if normalized_ref in config_step_map:
                    return f"Config {normalized_ref} is assigned to multiple steps", [], [], []
                config_step_map[normalized_ref] = index

        missing_settings = [key for key in normalized_settings.keys() if key not in step_assignments]
        if missing_settings:
            return f"Settings {', '.join(missing_settings)} are not assigned to any step", [], [], []

        base_setting_ids: Set[str] = set()
        setting_entities: List[Dict[str, Any]] = []
        for order, setting_key in enumerate(ordered_setting_keys, start=1):
            setting_id, suffix = self._split_setting_key(setting_key)
            if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                return f"Setting {setting_id} cannot be part of a template", [], [], []
            base_setting_ids.add(setting_id)
            setting_entities.append(
                {
                    "template_id": template_id,
                    "setting_id": setting_id,
                    "suffix": suffix,
                    "step_id": step_assignments[setting_key],
                    "default": self._empty_if_none(normalized_settings[setting_key]),
                    "order": order,
                }
            )

        if base_setting_ids:
            setting_meta = {
                row[0]: (row[1], row[2])
                for row in session.execute(select(Settings.id, Settings.type, Settings.separator).filter(Settings.id.in_(base_setting_ids)))
            }
            missing_base_ids = sorted(base_setting_ids - set(setting_meta))
            if missing_base_ids:
                return f"Unknown settings: {', '.join(missing_base_ids)}", [], [], []
            # Canonicalize defaults to their stored form (boolean aliases -> yes/no,
            # size/duration -> NGINX unit form, list items trimmed), like every other
            # settings ingestion boundary, so template defaults are stored canonical.
            for entity in setting_entities:
                meta = setting_meta.get(entity["setting_id"])
                if not meta:
                    continue
                stype, separator = meta
                if stype == "check":
                    entity["default"] = normalize_check_value(entity["default"])
                elif stype in ("size", "duration"):
                    canonical = normalize_unit(stype, entity["default"])
                    if canonical is not None:
                        entity["default"] = canonical
                elif stype in ("multiselect", "multivalue"):
                    entity["default"] = normalize_list_value(entity["default"], separator or " ")

        configs = configs or []
        config_map: Dict[str, Tuple[Dict[str, Any], int]] = {}
        for index, config in enumerate(configs):
            if not isinstance(config, dict):
                return "Config entries must be objects", [], [], []
            raw_type = str(config.get("type", "")).strip()
            normalized_type = raw_type.replace("-", "_").lower()
            raw_name = str(config.get("name", "")).strip()
            normalized_ref = self._normalize_template_config_reference(f"{normalized_type}/{raw_name}")
            if not normalized_ref:
                return f"Invalid config definition at index {index + 1}", [], [], []
            ref = normalized_ref
            if ref in config_map:
                return f"Duplicate config {ref}", [], [], []
            data_raw = config.get("data", "")
            data_str = data_raw if isinstance(data_raw, str) else str(data_raw)
            cfg_type, cfg_name_conf = ref.split("/", 1)
            cfg_name = cfg_name_conf.replace(".conf", "")
            config_map[ref] = (config | {"type": cfg_type, "name": cfg_name, "data": data_str}, index)

        for ref in config_step_map:
            if ref not in config_map:
                return f"Step references unknown config {ref}", [], [], []

        for ref in config_map:
            if ref not in config_step_map:
                return f"Config {ref} is not assigned to any step", [], [], []

        ordered_configs: List[Tuple[int, int, str]] = []
        for ref, (config, original_index) in config_map.items():
            provided_order = config.get("order")
            sort_key = provided_order if isinstance(provided_order, int) else original_index
            ordered_configs.append((sort_key, original_index, ref))

        ordered_configs.sort()

        config_entities: List[Dict[str, Any]] = []
        for order, (_, _, ref) in enumerate(ordered_configs, start=1):
            config, _ = config_map[ref]
            data_bytes = config["data"].encode("utf-8")
            checksum = bytes_hash(data_bytes, algorithm="sha256")
            cfg_type, cfg_name_conf = ref.split("/", 1)
            cfg_name = cfg_name_conf.replace(".conf", "")
            config_entities.append(
                {
                    "template_id": template_id,
                    "step_id": config_step_map[ref],
                    "type": cfg_type,
                    "name": cfg_name,
                    "data": data_bytes,
                    "checksum": checksum,
                    "order": order,
                }
            )

        return None, step_entities, setting_entities, config_entities

    def create_template(
        self,
        template_id: str,
        *,
        plugin_id: Optional[str] = None,
        name: str,
        settings: Dict[str, Any],
        steps: List[Dict[str, Any]],
        configs: Optional[List[Dict[str, Any]]] = None,
        method: str = "ui",
    ) -> str:
        """Create a new template."""

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template_id = template_id.strip()
            if not template_id:
                return "Template id is required"

            normalized_name = name.strip()
            if not normalized_name:
                return "Template name cannot be empty"

            normalized_plugin = None
            if isinstance(plugin_id, str):
                normalized_value = plugin_id.strip()
                normalized_plugin = normalized_value or None

            if session.execute(select(Templates.id).filter_by(id=template_id).limit(1)).first():
                return f"Template {template_id} already exists"

            if session.execute(select(Templates.id).filter(Templates.name == normalized_name).limit(1)).first():
                return f"Template name {normalized_name} already exists"

            if normalized_plugin:
                if session.execute(select(Plugins.id).filter_by(id=normalized_plugin).limit(1)).first() is None:
                    return f"Plugin {normalized_plugin} does not exist"

            error, step_entities, setting_entities, config_entities = self._prepare_template_entities(session, template_id, settings, steps, configs)
            if error:
                return error

            current_time = datetime.now().astimezone()
            session.add(
                Templates(
                    id=template_id,
                    plugin_id=normalized_plugin,
                    name=normalized_name,
                    method=method or "ui",
                    creation_date=current_time,
                    last_update=current_time,
                )
            )

            for step in step_entities:
                session.add(Template_steps(**step))

            for setting in setting_entities:
                session.add(Template_settings(**setting))

            for config_row in config_entities:
                config_row["type"] = config_row["type"].strip().replace("-", "_").lower()
                session.add(Template_custom_configs(**config_row))

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while creating template {template_id}.\n{e}"

        return ""

    def update_template(
        self,
        template_id: str,
        *,
        plugin_id: Optional[str] = None,
        name: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        configs: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Update an existing template."""

        current_details = self.get_template_details(template_id)
        if not current_details:
            return "Template not found"

        current_settings = {item["key"]: item.get("default", "") for item in current_details.get("settings", [])}
        current_steps = [
            {
                "title": step.get("title", ""),
                "subtitle": step.get("subtitle"),
                "settings": step.get("settings", []),
                "configs": step.get("configs", []),
            }
            for step in current_details.get("steps", [])
        ]
        current_configs = [
            {
                "type": cfg.get("type", ""),
                "name": cfg.get("name", ""),
                "data": cfg.get("data", ""),
                "order": cfg.get("order"),
            }
            for cfg in current_details.get("configs", [])
        ]

        effective_settings = settings if settings is not None else current_settings
        effective_steps = steps if steps is not None else current_steps
        effective_configs = configs if configs is not None else current_configs

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template = session.scalars(select(Templates).filter_by(id=template_id).limit(1)).first()
            if template is None:
                return "Template not found"

            if plugin_id is not None:
                normalized_plugin = None
                if isinstance(plugin_id, str):
                    normalized_value = plugin_id.strip()
                    normalized_plugin = normalized_value or None
                else:
                    normalized_plugin = str(plugin_id) or None

                if normalized_plugin != template.plugin_id:
                    if normalized_plugin and session.execute(select(Plugins.id).filter_by(id=normalized_plugin).limit(1)).first() is None:
                        return f"Plugin {normalized_plugin} does not exist"
                    template.plugin_id = normalized_plugin

            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    return "Template name cannot be empty"
                conflict = session.execute(select(Templates.id).filter(Templates.name == normalized_name, Templates.id != template_id).limit(1)).first()
                if conflict:
                    return f"Template name {normalized_name} already exists"

                template.name = normalized_name

            template.method = "ui"
            template.last_update = datetime.now().astimezone()

            error, step_entities, setting_entities, config_entities = self._prepare_template_entities(
                session, template_id, effective_settings, effective_steps, effective_configs
            )
            if error:
                return error

            session.execute(delete(Template_custom_configs).filter_by(template_id=template_id).execution_options(synchronize_session=False))
            session.execute(delete(Template_settings).filter_by(template_id=template_id).execution_options(synchronize_session=False))
            session.execute(delete(Template_steps).filter_by(template_id=template_id).execution_options(synchronize_session=False))

            for step in step_entities:
                session.add(Template_steps(**step))

            for setting in setting_entities:
                session.add(Template_settings(**setting))

            for config_row in config_entities:
                config_row["type"] = config_row["type"].strip().replace("-", "_").lower()
                session.add(Template_custom_configs(**config_row))

            session.execute(
                update(Plugins)
                .filter(Plugins.id.in_(set(plugin.id for plugin in session.execute(select(Plugins.id)).all())))
                .values({Plugins.config_changed: True})
                .execution_options(synchronize_session=False)
            )

            with suppress(ProgrammingError, OperationalError):
                metadata = session.get(Metadata, 1)
                if metadata is not None:
                    metadata.custom_configs_changed = True
                    metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating template {template_id}.\n{e}"

        return ""

    def delete_template(self, template_id: str) -> str:
        """Delete a template when it is not referenced by any configuration."""

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template = session.scalars(select(Templates).filter_by(id=template_id).limit(1)).first()
            if template is None:
                return "Template not found"

            global_reference = session.execute(select(Global_values.id).filter_by(setting_id="USE_TEMPLATE", value=template_id).limit(1)).first()
            if global_reference:
                return "Template is currently used by the global settings"

            service_reference = session.execute(select(Services_settings.id).filter_by(setting_id="USE_TEMPLATE", value=template_id).limit(1)).first()
            if service_reference:
                return "Template is currently used by a service"

            session.delete(template)
            session.execute(
                update(Plugins)
                .filter(Plugins.id.in_(set(plugin.id for plugin in session.execute(select(Plugins.id)).all())))
                .values({Plugins.config_changed: True})
                .execution_options(synchronize_session=False)
            )

            with suppress(ProgrammingError, OperationalError):
                metadata = session.get(Metadata, 1)
                if metadata is not None:
                    metadata.custom_configs_changed = True
                    metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting template {template_id}.\n{e}"

        return ""
