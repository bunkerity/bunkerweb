#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from model import Bw_cli_commands, Global_values, Jobs, Jobs_cache, Jobs_runs, Metadata, Multiselects, Plugin_pages, Plugins, Selects, Services_settings, Settings, Template_custom_configs, Template_settings, Template_steps, Templates  # type: ignore

from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase, retry_on_transient_db_errors


class DatabasePluginsMixin(DatabaseMixinBase):
    """Plugin reads, deletion and plugin pages."""

    def delete_plugin(self, plugin_id: str, method: str, *, changes: bool = True) -> str:
        """Delete a plugin from the database."""
        with self._db_session() as session:
            plugin = session.scalars(select(Plugins).filter_by(id=plugin_id, method=method).limit(1)).first()
            if not plugin:
                return f"Plugin with id {plugin_id} and method {method} not found"

            session.execute(delete(Plugins).filter_by(id=plugin_id, method=method))
            for db_setting in session.scalars(select(Settings).filter_by(plugin_id=plugin_id)).all():
                session.execute(delete(Selects).filter_by(setting_id=db_setting.id))
                session.execute(delete(Multiselects).filter_by(setting_id=db_setting.id))
                session.execute(delete(Services_settings).filter_by(setting_id=db_setting.id))
                session.execute(delete(Global_values).filter_by(setting_id=db_setting.id))
                session.execute(delete(Template_settings).filter_by(setting_id=db_setting.id))
                session.execute(delete(Settings).filter_by(id=db_setting.id))

            for db_job in session.scalars(select(Jobs).filter_by(plugin_id=plugin_id)).all():
                session.execute(delete(Jobs_cache).filter_by(job_name=db_job.name))
                session.execute(delete(Jobs_runs).filter_by(job_name=db_job.name))
                session.execute(delete(Jobs).filter_by(name=db_job.name))

            session.execute(delete(Plugin_pages).filter_by(plugin_id=plugin_id))
            session.execute(delete(Bw_cli_commands).filter_by(plugin_id=plugin_id))

            for db_template in session.scalars(select(Templates).filter_by(plugin_id=plugin_id)).all():
                session.execute(delete(Template_steps).filter_by(template_id=db_template.id))
                session.execute(delete(Template_settings).filter_by(template_id=db_template.id))
                session.execute(delete(Template_custom_configs).filter_by(template_id=db_template.id))
                session.execute(delete(Templates).filter_by(id=db_template.id))

            if changes:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.get(Metadata, 1)
                    if metadata is not None:
                        if method in ("external", "ui"):
                            metadata.external_plugins_changed = True
                            metadata.last_external_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True
                        elif method == "pro":
                            metadata.pro_plugins_changed = True
                            metadata.last_pro_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    @retry_on_transient_db_errors
    def get_plugins(self, *, _type: Literal["all", "external", "ui", "pro"] = "all", with_data: bool = False) -> List[Dict[str, Any]]:
        """Get all plugins from the database using batched queries to avoid N+1 issues."""
        with self._db_session() as session:
            # Build the base query.
            entities = [
                Plugins.id,
                Plugins.stream,
                Plugins.name,
                Plugins.description,
                Plugins.version,
                Plugins.type,
                Plugins.method,
                Plugins.checksum,
            ]
            if with_data:
                entities.append(Plugins.data)

            query = select(*entities)
            if _type == "external":
                query = query.filter(Plugins.type.in_(["external", "ui"]))
            elif _type != "all":
                query = query.filter_by(type=_type)
            query = query.order_by(Plugins.id.asc())

            plugins = session.execute(query).all()

            plugin_ids = [plugin.id for plugin in plugins]

            # Pre-fetch plugin pages.
            pages = session.execute(select(Plugin_pages.plugin_id).filter(Plugin_pages.plugin_id.in_(plugin_ids))).all()
            pages_map = {page.plugin_id: True for page in pages}

            # Pre-fetch settings.
            settings_rows = session.scalars(select(Settings).filter(Settings.plugin_id.in_(plugin_ids)).order_by(Settings.order)).all()
            settings_map = {}
            # Also, collect setting IDs for select-type settings.
            select_setting_ids = [s.id for s in settings_rows if s.type == "select"]

            for setting in settings_rows:
                settings_map.setdefault(setting.plugin_id, []).append(setting)

            # Pre-fetch selects for settings of type "select".
            selects_map: Dict[str, List[Any]] = {}
            if select_setting_ids:
                selects = session.scalars(select(Selects).filter(Selects.setting_id.in_(select_setting_ids)).order_by(Selects.order)).all()
                for sel in selects:
                    selects_map.setdefault(sel.setting_id, []).append(self._empty_if_none(sel.value))

            # Pre-fetch multiselects for settings of type "multiselect".
            multiselect_setting_ids = [s.id for s in settings_rows if s.type == "multiselect"]
            multiselects_map: Dict[str, List[Dict[str, Any]]] = {}
            if multiselect_setting_ids:
                multiselects = session.scalars(
                    select(Multiselects).filter(Multiselects.setting_id.in_(multiselect_setting_ids)).order_by(Multiselects.order)
                ).all()
                for msel in multiselects:
                    multiselects_map.setdefault(msel.setting_id, []).append(
                        {"id": msel.option_id, "label": msel.label, "value": self._empty_if_none(msel.value)}
                    )

            # Pre-fetch bw_cli commands.
            commands_rows = session.scalars(select(Bw_cli_commands).filter(Bw_cli_commands.plugin_id.in_(plugin_ids))).all()
            commands_map: Dict[str, Dict[str, Any]] = {}
            for cmd in commands_rows:
                commands_map.setdefault(cmd.plugin_id, {})[cmd.name] = cmd.file_name

            # Assemble the plugin data.
            result = []
            for plugin in plugins:
                plugin_data: Dict[str, Any] = {
                    "id": plugin.id,
                    "stream": plugin.stream,
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "type": plugin.type,
                    "method": plugin.method,
                    "page": pages_map.get(plugin.id, False),
                    "settings": {},
                    "checksum": plugin.checksum,
                }
                if with_data:
                    plugin_data["data"] = plugin.data

                for setting in settings_map.get(plugin.id, []):
                    setting_data = {
                        "context": setting.context,
                        "default": self._empty_if_none(setting.default),
                        "help": setting.help,
                        "id": setting.name,
                        "label": setting.label,
                        "regex": setting.regex,
                        "type": setting.type,
                    }
                    if setting.multiple:
                        setting_data["multiple"] = setting.multiple
                    if setting.type == "select":
                        setting_data["select"] = selects_map.get(setting.id, [])
                        setting_data["case_insensitive"] = setting.case_insensitive
                    elif setting.type == "multiselect":
                        setting_data["multiselect"] = multiselects_map.get(setting.id, [])
                        setting_data["case_insensitive"] = setting.case_insensitive
                        sep_value = getattr(setting, "separator", None)
                        setting_data["separator"] = sep_value if sep_value is not None else " "
                    elif setting.type == "multivalue":
                        sep_value = getattr(setting, "separator", None)
                        setting_data["separator"] = sep_value if sep_value is not None else " "
                    elif setting.type == "file":
                        setting_data["accept"] = getattr(setting, "accept", "")
                    plugin_data["settings"][setting.id] = setting_data

                if plugin.id in commands_map:
                    plugin_data["bwcli"] = commands_map[plugin.id]

                result.append(plugin_data)

            return result

    def get_plugins_errors(self) -> int:
        """Get plugins errors."""
        with self._db_session() as session:
            # Subquery to get the latest run for each job
            latest_runs_subquery = select(Jobs_runs.job_name, func.max(Jobs_runs.end_date).label("latest_end_date")).group_by(Jobs_runs.job_name).subquery()

            # Main query to fetch latest job runs and count errors
            latest_job_runs = session.execute(
                select(Jobs_runs.job_name, Jobs_runs.success).join(
                    latest_runs_subquery,
                    (Jobs_runs.job_name == latest_runs_subquery.c.job_name) & (Jobs_runs.end_date == latest_runs_subquery.c.latest_end_date),
                )
            ).all()

            return sum(1 for job_run in latest_job_runs if not job_run.success)

    def get_plugin_page(self, plugin_id: str) -> Optional[bytes]:
        """Get plugin page."""
        with self._db_session() as session:
            page = session.execute(select(Plugin_pages.data).filter_by(plugin_id=plugin_id).limit(1)).first()

            if not page:
                return None

            return page.data
