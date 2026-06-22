#!/usr/bin/env python3
from datetime import datetime
from json import JSONDecodeError, loads
from pathlib import Path
from re import DOTALL, error as RegexError, search
from traceback import format_exc
from typing import List, Tuple

from model import Base, Bw_cli_commands, Global_values, Jobs, Jobs_cache, Jobs_runs, Multiselects, Plugin_pages, Plugins, ResourceGroup_entries, ResourceGroups, Selects, Services, Services_settings, Settings, Template_custom_configs, Template_settings, Template_steps, Templates  # type: ignore

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore
from resource_validation import validate_resource_value  # type: ignore

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from .common import DatabaseMixinBase, bulk_add_in_fk_order


class DatabaseInitTablesMixin(DatabaseMixinBase):
    """Schema creation and core plugin/settings/template seeding (init_tables)."""

    def init_tables(self, default_plugins: List[dict]) -> Tuple[bool, str]:
        """Initialize the database tables and return the result"""

        if self.readonly:
            return False, "The database is read-only, the changes will not be saved"

        assert self.sql_engine is not None, "The database engine is not initialized"

        created, create_error = self._it_create_tables()
        if not created:
            return False, create_error

        # Fetch old data (only the tables/columns the diff pass consumes — avoids
        # dragging every LargeBinary blob into memory on each scheduler boot)
        with self._db_session() as session:
            old_data = self._it_fetch_old_data(session)

        # Prepare structures to track changes
        to_put = []
        to_update = []
        to_delete = []

        with self._db_session() as session:
            old = self._it_index_old_data(old_data)

            # Build desired data from default_plugins
            desired = self._it_build_desired_plugins(default_plugins, old["plugins"])
            desired.update(self._it_build_desired_templates(default_plugins, desired["saved_settings"]))
            desired.update(self._it_build_desired_resource_groups(default_plugins))

            # Compute differences between old and desired data
            self._it_diff_plugins(old, desired, to_put, to_update, to_delete)
            self._it_diff_settings(old, desired, to_put, to_update, to_delete)
            self._it_diff_selects_multiselects(old, desired, to_put, to_update, to_delete)
            self._it_diff_jobs(old, desired, to_put, to_update, to_delete)
            self._it_diff_plugin_pages(old, desired, to_put, to_update, to_delete)
            self._it_diff_cli_commands(old, desired, to_put, to_update, to_delete)
            self._it_diff_templates(old, desired, to_put, to_update, to_delete)
            self._it_diff_template_steps(old, desired, to_put, to_update, to_delete)
            self._it_diff_template_settings(old, desired, to_put, to_update, to_delete)
            self._it_diff_template_configs(old, desired, to_put, to_update, to_delete)
            self._it_diff_resource_groups(old, desired, to_put, to_update, to_delete)
            self._it_diff_resource_group_entries(old, desired, to_put, to_update, to_delete)

            # APPLY CHANGES
            try:
                self._it_apply_deletes(session, to_delete)
                # Insert parents before children to avoid FK errors on some DBs.
                bulk_add_in_fk_order(session, to_put)
                self._it_apply_updates(session, to_update)
                session.commit()
            except SQLAlchemyError as e:
                self.logger.debug(format_exc())
                session.rollback()
                return False, str(e)

        # ? Check if all templates settings are valid
        with self._db_session() as session:
            self._it_validate_template_settings(session)

            try:
                session.commit()
            except BaseException as e:
                return False, str(e)

        if not to_put and not to_update and not to_delete:
            return False, ""
        return True, ""

    def _it_create_tables(self) -> Tuple[bool, str]:
        """Create the tables; returns (False, error) when table creation fails.

        Reflection was removed: the diff/apply pass reads old data through targeted
        ORM-model column selects (see ``_it_fetch_old_data``) and mutates rows through
        the ORM models in ``_it_apply_deletes``/``_it_apply_updates`` only. No reflected
        ``MetaData`` is consumed anywhere downstream, so reflecting the whole schema —
        and the retry loop guarding it — is dead weight.
        """
        # Register plugin-shipped DB models on Base.metadata before create_all so a
        # plugin's tables are created alongside the core schema (security-gated +
        # checksum-verified for pro/external). Never let a misbehaving plugin block
        # core table creation.
        try:
            from plugin_extensions import register_plugin_models  # type: ignore

            register_plugin_models(self.logger, db=self)
        except Exception as e:
            self.logger.error(f"Failed to register plugin DB models: {e}")

        try:
            Base.metadata.create_all(self.sql_engine, checkfirst=True)
        except Exception as e:
            return False, str(e)
        return True, ""

    def _it_fetch_old_data(self, session) -> dict:
        """Fetch only the tables/columns the diff pass consumes.

        The previous implementation reflected the whole DB and SELECTed every table,
        dragging every LargeBinary blob (job caches, custom configs, services
        settings, plugin/template binaries, ...) into memory on each scheduler boot.
        ``_it_index_old_data`` and the ``_it_diff_*`` helpers only ever touch ~11
        tables, and never the binary ``data`` columns except ``bw_plugins.data``
        (compared in ``_it_diff_plugins``). The selects below fetch exactly those
        columns; rows keep the same named attribute access (``row.id`` etc.) and the
        old_data dict keeps the same table-name keys, so the downstream consumption
        shape is unchanged.
        """
        return {
            # bw_plugins: full row including the binary ``data`` column (diff compares it).
            "bw_plugins": session.execute(
                select(
                    Plugins.id,
                    Plugins.name,
                    Plugins.description,
                    Plugins.version,
                    Plugins.stream,
                    Plugins.type,
                    Plugins.method,
                    Plugins.data,
                    Plugins.checksum,
                    Plugins.config_changed,
                    Plugins.last_config_change,
                )
            ).all(),
            # bw_settings: full column set (small table).
            "bw_settings": session.execute(
                select(
                    Settings.id,
                    Settings.name,
                    Settings.plugin_id,
                    Settings.context,
                    Settings.default,
                    Settings.help,
                    Settings.label,
                    Settings.regex,
                    Settings.type,
                    Settings.multiple,
                    Settings.separator,
                    Settings.accept,
                    Settings.order,
                )
            ).all(),
            "bw_selects": session.execute(select(Selects.setting_id, Selects.value, Selects.order)).all(),
            "bw_multiselects": session.execute(
                select(Multiselects.setting_id, Multiselects.option_id, Multiselects.label, Multiselects.value, Multiselects.order)
            ).all(),
            # bw_jobs: full column set (small table).
            "bw_jobs": session.execute(select(Jobs.name, Jobs.plugin_id, Jobs.file_name, Jobs.every, Jobs.reload, Jobs.run_async)).all(),
            # bw_plugin_pages: already column-limited (skip the LargeBinary ``data`` column).
            "bw_plugin_pages": session.execute(select(Plugin_pages.plugin_id, Plugin_pages.checksum)).all(),
            "bw_cli_commands": session.execute(select(Bw_cli_commands.plugin_id, Bw_cli_commands.name, Bw_cli_commands.file_name)).all(),
            "bw_templates": session.execute(select(Templates.id, Templates.plugin_id, Templates.name)).all(),
            "bw_template_steps": session.execute(select(Template_steps.id, Template_steps.template_id, Template_steps.title, Template_steps.subtitle)).all(),
            "bw_template_settings": session.execute(
                select(
                    Template_settings.template_id,
                    Template_settings.setting_id,
                    Template_settings.suffix,
                    Template_settings.step_id,
                    Template_settings.order,
                    Template_settings.default,
                )
            ).all(),
            # bw_template_custom_configs: every column EXCEPT the LargeBinary ``data``
            # column (the diff compares ``checksum`` only — verified in _it_diff_template_configs).
            "bw_template_custom_configs": session.execute(
                select(
                    Template_custom_configs.template_id,
                    Template_custom_configs.type,
                    Template_custom_configs.name,
                    Template_custom_configs.step_id,
                    Template_custom_configs.order,
                    Template_custom_configs.checksum,
                )
            ).all(),
            "bw_resource_groups": session.execute(
                select(ResourceGroups.id, ResourceGroups.plugin_id, ResourceGroups.name, ResourceGroups.method, ResourceGroups.description)
            ).all(),
            "bw_resource_group_entries": session.execute(
                select(
                    ResourceGroup_entries.group_id,
                    ResourceGroup_entries.kind,
                    ResourceGroup_entries.value,
                    ResourceGroup_entries.order,
                    ResourceGroup_entries.comment,
                )
            ).all(),
        }

    def _it_index_old_data(self, old_data: dict) -> dict:
        """Convert old_data into dicts keyed by IDs or relevant unique keys."""
        # For plugins:
        old_plugins = {p.id: p for p in old_data.get("bw_plugins", [])}

        # For settings:
        old_settings = {}
        for s in old_data.get("bw_settings", []):
            old_settings[(s.plugin_id, s.id)] = s

        # For selects:
        old_selects = {}
        for sel in old_data.get("bw_selects", []):
            old_selects[(sel.setting_id, self._empty_if_none(sel.value), sel.order)] = sel

        # For multiselects:
        old_multiselects = {}
        for msel in old_data.get("bw_multiselects", []):
            old_multiselects[(msel.setting_id, msel.option_id, msel.label, self._empty_if_none(msel.value), msel.order)] = msel

        # For jobs:
        old_jobs = {}
        for j in old_data.get("bw_jobs", []):
            old_jobs[(j.plugin_id, j.name)] = j

        # For plugin pages:
        old_plugin_pages = {pp.plugin_id: pp for pp in old_data.get("bw_plugin_pages", [])}

        # For CLI commands:
        old_cli_commands = {}
        for c in old_data.get("bw_cli_commands", []):
            old_cli_commands[(c.plugin_id, c.name)] = c

        # For templates:
        managed_template_ids = {t.id for t in old_data.get("bw_templates", []) if t.plugin_id}
        old_templates = {(t.plugin_id, t.id): t for t in old_data.get("bw_templates", []) if t.plugin_id}
        old_template_steps = {}
        for st in old_data.get("bw_template_steps", []):
            if st.template_id in managed_template_ids:
                old_template_steps[(st.template_id, st.id)] = st

        old_template_settings = {}
        for ts in old_data.get("bw_template_settings", []):
            if ts.template_id in managed_template_ids:
                old_template_settings[(ts.template_id, ts.setting_id, ts.suffix, ts.step_id, ts.order)] = ts.default

        old_template_configs = {}
        for tc in old_data.get("bw_template_custom_configs", []):
            if tc.template_id in managed_template_ids:
                old_template_configs[(tc.template_id, tc.type, tc.name, tc.step_id, tc.order)] = tc

        # For resource groups: index only managed/core groups (those with a plugin_id).
        # User groups (plugin_id=None, method="ui") are never indexed, so the diff pass
        # never updates or deletes them — that is the immutability/delete guard.
        managed_rg_ids = {g.id for g in old_data.get("bw_resource_groups", []) if g.plugin_id}
        old_resource_groups = {(g.plugin_id, g.id): g for g in old_data.get("bw_resource_groups", []) if g.plugin_id}
        old_resource_group_entries = {}
        for e in old_data.get("bw_resource_group_entries", []):
            if e.group_id in managed_rg_ids:
                old_resource_group_entries[(e.group_id, e.kind, e.value, e.order)] = e.comment

        return {
            "plugins": old_plugins,
            "settings": old_settings,
            "selects": old_selects,
            "multiselects": old_multiselects,
            "jobs": old_jobs,
            "plugin_pages": old_plugin_pages,
            "cli_commands": old_cli_commands,
            "templates": old_templates,
            "template_steps": old_template_steps,
            "template_settings": old_template_settings,
            "template_configs": old_template_configs,
            "resource_groups": old_resource_groups,
            "resource_group_entries": old_resource_group_entries,
        }

    def _it_build_desired_plugins(self, default_plugins: List[dict], old_plugins: dict) -> dict:
        """Build desired plugins, settings, selects, multiselects, jobs, pages and CLI commands from default_plugins."""
        # Build desired data from default_plugins
        # The following logic is similar to the original code but uses dicts/sets for comparisons.

        # Desired plugins, settings, jobs, pages, etc.
        desired_plugins = {}
        desired_settings = {}
        desired_selects = set()
        desired_multiselects = set()
        desired_jobs = {}
        desired_plugin_pages = {}
        desired_cli_commands = {}

        saved_settings = set()

        # Process default plugins
        for plugins in default_plugins:
            if not isinstance(plugins, list):
                plugins = [plugins]

            for plugin in plugins:
                if "id" not in plugin:
                    # General plugin
                    base_plugin = {
                        "id": "general",
                        "name": "General",
                        "description": "The general settings for the server",
                        "version": "0.1",
                        "stream": "partial",
                        "type": "core",
                        "method": "manual",
                        "data": None,
                        "checksum": None,
                    }
                    settings = plugin
                    jobs = []
                    commands = {}
                else:
                    # Extract plugin details
                    settings = plugin.pop("settings", {})
                    jobs = plugin.pop("jobs", [])
                    plugin.pop("page", False)
                    commands = plugin.pop("bwcli", {})
                    if not isinstance(commands, dict):
                        commands = {}

                    base_plugin = {
                        "id": plugin["id"],
                        "name": plugin["name"],
                        "description": plugin["description"],
                        "version": plugin["version"],
                        "stream": plugin["stream"],
                        "type": plugin.get("type", "core"),
                        "method": plugin.get("method", "manual"),
                        "data": plugin.get("data"),
                        "checksum": plugin.get("checksum"),
                    }

                # Skip unsupported plugin
                if base_plugin["id"] == "letsencrypt_dns":
                    self.logger.warning(f'Plugin {base_plugin["id"]} is no longer supported, skipping it')
                    continue

                # Track desired plugin
                desired_plugins[base_plugin["id"]] = base_plugin

                # Identify if this plugin existed before
                plugin_found = base_plugin["id"] in old_plugins
                if not plugin_found and old_plugins:
                    self.logger.warning(f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}" does not exist, creating it')

                # SETTINGS
                order = 0
                plugin_saved_settings = set()
                for setting_key, value in settings.items():
                    # setting_key is e.g. "my_setting"
                    # value should contain "id", "select", "multiselect", etc.
                    select_values = value.pop("select", [])
                    multiselect_values = value.pop("multiselect", [])
                    # The main setting id:
                    setting_id = setting_key
                    # Ensure plugin_id and name in the value
                    value["plugin_id"] = base_plugin["id"]
                    value["name"] = value["id"]
                    value["id"] = setting_id
                    value["order"] = order

                    desired_settings[(base_plugin["id"], setting_id)] = value
                    desired_selects.update((setting_id, self._empty_if_none(sel_val), sel_order) for sel_order, sel_val in enumerate(select_values, start=1))
                    desired_multiselects.update(
                        (setting_id, msel_val.get("id", ""), msel_val.get("label", ""), self._empty_if_none(msel_val.get("value", "")), msel_order)
                        for msel_order, msel_val in enumerate(multiselect_values, start=1)
                        if isinstance(msel_val, dict)
                    )
                    plugin_saved_settings.add(setting_id)
                    order += 1

                saved_settings |= plugin_saved_settings

                # JOBS
                for job in jobs:
                    job["file_name"] = job.pop("file")
                    job["reload"] = job.get("reload", False)
                    job["run_async"] = job.pop("async", False)
                    desired_jobs[(base_plugin["id"], job["name"])] = job

                # COMMANDS
                for command, file_name in commands.items():
                    desired_cli_commands[(base_plugin["id"], command)] = file_name

                # PAGES
                plugin_path = (
                    Path("/", "usr", "share", "bunkerweb", "core", base_plugin["id"])
                    if base_plugin.get("type", "core") == "core"
                    else (
                        Path("/", "etc", "bunkerweb", "plugins", base_plugin["id"])
                        if base_plugin.get("type", "core") == "external"
                        else Path("/", "etc", "bunkerweb", "pro", "plugins", base_plugin["id"])
                    )
                )
                path_ui = plugin_path.joinpath("ui")
                if path_ui.is_dir():
                    try:
                        plugin_page_content = create_plugin_tar_gz(path_ui)
                        checksum = bytes_hash(plugin_page_content, algorithm="sha256")
                        desired_plugin_pages[base_plugin["id"]] = {
                            "data": plugin_page_content.getvalue(),
                            "checksum": checksum,
                        }
                    except (FileNotFoundError, OSError) as e:
                        self.logger.warning(f"Some files in {path_ui} could not be archived: {e}")

        return {
            "plugins": desired_plugins,
            "settings": desired_settings,
            "selects": desired_selects,
            "multiselects": desired_multiselects,
            "jobs": desired_jobs,
            "plugin_pages": desired_plugin_pages,
            "cli_commands": desired_cli_commands,
            "saved_settings": saved_settings,
        }

    def _it_build_desired_templates(self, default_plugins: List[dict], saved_settings: set) -> dict:
        """Build desired templates, steps, template settings and template configs from default_plugins."""
        desired_templates = {}
        desired_template_steps = {}
        desired_template_settings = {}
        desired_template_configs = {}

        for plugins in default_plugins:
            if not isinstance(plugins, list):
                plugins = [plugins]

            for plugin in plugins:
                if "id" not in plugin:
                    # General plugin
                    base_plugin = {"id": "general", "type": "core"}
                else:
                    base_plugin = {"id": plugin["id"], "type": plugin.get("type", "core")}

                # Skip unsupported plugin
                if base_plugin["id"] == "letsencrypt_dns":
                    continue

                # TEMPLATES
                plugin_path = (
                    Path("/", "usr", "share", "bunkerweb", "core", base_plugin["id"])
                    if base_plugin.get("type", "core") == "core"
                    else (
                        Path("/", "etc", "bunkerweb", "plugins", base_plugin["id"])
                        if base_plugin.get("type", "core") == "external"
                        else Path("/", "etc", "bunkerweb", "pro", "plugins", base_plugin["id"])
                    )
                )
                templates_path = plugin_path.joinpath("templates")
                if templates_path.is_dir():
                    for template_file in templates_path.iterdir():
                        if template_file.is_dir():
                            continue
                        try:
                            template_data = loads(template_file.read_text())
                        except JSONDecodeError:
                            self.logger.error(
                                f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template file "{template_file}" is not valid JSON'
                            )
                            continue

                        template_id = template_file.stem
                        desired_templates[(base_plugin["id"], template_id)] = {
                            "name": template_data.get("name", template_id),
                            "method": plugin.get("method", "manual"),
                        }

                        # Steps
                        found_steps = set()
                        steps_settings = {}
                        steps_configs = {}
                        for step_id, step in enumerate(template_data.get("steps", []), start=1):
                            desired_template_steps[(template_id, step_id)] = {"title": step["title"], "subtitle": step["subtitle"]}
                            found_steps.add(step_id)
                            for sett in step.get("settings", []):
                                if step_id not in steps_settings:
                                    steps_settings[step_id] = []
                                steps_settings[step_id].append(sett)
                            for conf in step.get("configs", []):
                                if step_id not in steps_configs:
                                    steps_configs[step_id] = []
                                steps_configs[step_id].append(conf)

                        # Template-level settings
                        order = 0
                        for setting, default in template_data.get("settings", {}).items():
                            # Check restrictions and existence
                            if setting in getattr(self, "RESTRICTED_TEMPLATE_SETTINGS", []):
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has restricted setting "{setting}", skipping'
                                )
                                continue
                            # Check if setting exists globally
                            setting_id = setting
                            suffix = 0
                            if self.SUFFIX_RX.search(setting):
                                setting_id, suffix = setting.rsplit("_", 1)
                                suffix = int(suffix)  # noqa: FURB123
                            if setting_id not in saved_settings:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid setting "{setting}", skipping'
                                )
                                continue

                            # Check if belongs to a step
                            step_id = None
                            for sid, step_set_list in steps_settings.items():
                                if setting in step_set_list:
                                    step_id = sid
                                    break

                            if not step_id:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id}`s setting "{setting}" doesn\'t belong to a step, skipping'
                                )
                                continue

                            desired_template_settings[(template_id, setting_id, suffix, step_id, order)] = default
                            order += 1

                        # Template-level configs
                        order = 0
                        for config in template_data.get("configs", []):
                            try:
                                config_type, config_name = config.split("/", 1)
                            except ValueError:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid config "{config}"'
                                )
                                continue
                            if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid config type "{config_type}"'
                                )
                                continue

                            config_file = templates_path.joinpath(template_id, "configs", config_type, config_name)
                            if not config_file.is_file():
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} missing config "{config}"'
                                )
                                continue

                            content = config_file.read_bytes()
                            config_type = config_type.strip().replace("-", "_").lower()
                            checksum = bytes_hash(content, algorithm="sha256")
                            config_name_clean = config_name.removesuffix(".conf")

                            # Check if belongs to a step
                            step_id = None
                            for sid, step_conf_list in steps_configs.items():
                                if config in step_conf_list:
                                    step_id = sid
                                    break

                            if not step_id:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id}`s config "{config}" doesn\'t belong to a step, skipping'
                                )
                                continue

                            desired_template_configs[(template_id, config_type, config_name_clean, step_id, order)] = {
                                "data": content,
                                "checksum": checksum,
                            }
                            order += 1

        return {
            "templates": desired_templates,
            "template_steps": desired_template_steps,
            "template_settings": desired_template_settings,
            "template_configs": desired_template_configs,
        }

    def _it_build_desired_resource_groups(self, default_plugins: List[dict]) -> dict:
        """Build desired core resource groups + entries from on-disk ``<plugin>/resource-groups/*.json``.

        Same disk-scan pattern as ``_it_build_desired_templates``. Each JSON file is one
        group (``id`` = file stem); entries are validated/normalized through the shared
        ``validate_resource_value`` and de-duplicated on ``(kind, value)``. Groups carry the
        plugin's ``method`` (``"manual"`` for core) so they are immutable + managed by init.
        """
        desired_groups = {}
        desired_entries = {}

        for plugins in default_plugins:
            if not isinstance(plugins, list):
                plugins = [plugins]

            for plugin in plugins:
                if "id" not in plugin:
                    base_plugin = {"id": "general", "type": "core"}
                else:
                    base_plugin = {"id": plugin["id"], "type": plugin.get("type", "core")}

                if base_plugin["id"] == "letsencrypt_dns":
                    continue

                plugin_path = (
                    Path("/", "usr", "share", "bunkerweb", "core", base_plugin["id"])
                    if base_plugin.get("type", "core") == "core"
                    else (
                        Path("/", "etc", "bunkerweb", "plugins", base_plugin["id"])
                        if base_plugin.get("type", "core") == "external"
                        else Path("/", "etc", "bunkerweb", "pro", "plugins", base_plugin["id"])
                    )
                )
                groups_path = plugin_path.joinpath("resource-groups")
                if not groups_path.is_dir():
                    continue

                for group_file in groups_path.iterdir():
                    if group_file.is_dir():
                        continue
                    try:
                        group_data = loads(group_file.read_text())
                    except JSONDecodeError:
                        self.logger.error(
                            f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s resource group file "{group_file}" is not valid JSON'
                        )
                        continue

                    group_id = group_file.stem
                    desired_groups[(base_plugin["id"], group_id)] = {
                        "name": group_data.get("name", group_id),
                        "description": self._empty_if_none(group_data.get("description", "")),
                        "method": plugin.get("method", "manual"),
                    }

                    order = 0
                    seen = set()
                    for entry in group_data.get("entries", []):
                        if not isinstance(entry, dict):
                            continue
                        kind = str(entry.get("kind", "")).strip().lower()
                        raw_value = entry.get("value")
                        ok, value = validate_resource_value(kind, "" if raw_value is None else str(raw_value))
                        if not ok:
                            self.logger.error(
                                f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s resource group {group_id} has invalid {kind!r} entry {raw_value!r}, skipping'
                            )
                            continue
                        dedupe_key = (kind, value)
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        comment_raw = entry.get("comment")
                        comment = None
                        if comment_raw is not None:
                            comment = str(comment_raw).strip() or None
                        desired_entries[(group_id, kind, value, order)] = comment
                        order += 1

        return {"resource_groups": desired_groups, "resource_group_entries": desired_entries}

    def _it_diff_plugins(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for PLUGINS."""
        old_plugins = old["plugins"]
        desired_plugins = desired["plugins"]

        old_plugin_ids = set(old_plugins.keys())
        new_plugin_ids = set(desired_plugins.keys())

        # Plugins to create
        for pid in new_plugin_ids - old_plugin_ids:
            p = desired_plugins[pid]
            to_put.append(Plugins(**p))

        # Plugins to update
        for pid in old_plugin_ids & new_plugin_ids:
            old_p = old_plugins[pid]
            new_p = desired_plugins[pid]
            attrs_to_check = ("name", "description", "version", "stream", "type", "method", "data", "checksum")
            if any(getattr(old_p, attr, None) != new_p.get(attr) for attr in attrs_to_check) and old_p.method == new_p.get("method", "manual"):
                to_update.append({"type": "plugin", "filter": {"id": pid}, "data": {k: new_p[k] for k in attrs_to_check if k in new_p}})

        # Plugins to delete
        for pid in old_plugin_ids - new_plugin_ids:
            old_p = old_plugins[pid]
            if old_p.method == "manual":
                self.logger.warning(f'{old_p.type.title()} plugin "{pid}" has been removed, deleting it')
                to_delete.append({"type": "plugin", "filter": {"id": pid}})

    def _it_diff_settings(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for SETTINGS (including the MODSECURITY_CRS_PLUGIN_URLS rename migration)."""
        old_settings = old["settings"]
        desired_settings = desired["settings"]

        old_setting_keys = set(old_settings.keys())
        new_setting_keys = set(desired_settings.keys())
        for sk in new_setting_keys - old_setting_keys:
            to_put.append(Settings(**desired_settings[sk]))

        for sk in old_setting_keys & new_setting_keys:
            old_s = old_settings[sk]
            new_s = desired_settings[sk]
            # Check changes excluding order since we always set order
            changed = any(getattr(old_s, k, None) != new_s.get(k) for k in new_s.keys())
            if changed:
                to_update.append({"type": "setting", "filter": {"plugin_id": sk[0], "id": sk[1]}, "data": new_s})

        # Settings to delete
        for sk in old_setting_keys - new_setting_keys:
            to_delete.append({"type": "setting", "filter": {"plugin_id": sk[0], "id": sk[1]}})
            if sk[1] == "MODSECURITY_CRS_PLUGIN_URLS":
                self.logger.warning("MODSECURITY_CRS_PLUGIN_URLS setting has been renamed to MODSECURITY_CRS_PLUGINS, migrating data")
                to_update.extend(
                    [
                        {
                            "type": "global_value",
                            "filter": {"setting_id": "MODSECURITY_CRS_PLUGIN_URLS"},
                            "data": {"setting_id": "MODSECURITY_CRS_PLUGINS"},
                        },
                        {
                            "type": "service_setting",
                            "filter": {"setting_id": "MODSECURITY_CRS_PLUGIN_URLS"},
                            "data": {"setting_id": "MODSECURITY_CRS_PLUGINS"},
                        },
                    ]
                )

    def _it_diff_selects_multiselects(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for SELECTS and MULTISELECTS."""
        old_selects = old["selects"]
        desired_selects = desired["selects"]
        desired_multiselects = desired["multiselects"]

        old_select_keys = set(old_selects.keys())
        # desired_selects is a set of (setting_id, value, order)
        # We must correlate with known settings. If setting_id belongs to a plugin_id?
        # Original code just handled removing selects not present. We'll trust that logic:

        # First delete all selects for setting_ids that are being updated
        settings_being_updated = set()
        settings_being_updated.update({sel[0] for sel in desired_selects})

        for setting_id in settings_being_updated:
            to_delete.append({"type": "select", "filter": {"setting_id": setting_id}})

        # Now insert all new selects
        for sel in desired_selects:
            to_put.append(Selects(setting_id=sel[0], value=self._empty_if_none(sel[1]), order=sel[2]))

        # Handle multiselects similar to selects
        settings_being_updated_multiselects = set()
        settings_being_updated_multiselects.update({msel[0] for msel in desired_multiselects})

        for setting_id in settings_being_updated_multiselects:
            to_delete.append({"type": "multiselect", "filter": {"setting_id": setting_id}})

        # Now insert all new multiselects
        for msel in desired_multiselects:
            to_put.append(Multiselects(setting_id=msel[0], option_id=msel[1], label=msel[2], value=self._empty_if_none(msel[3]), order=msel[4]))

        # Delete old selects not needed (for settings not in our updated list)
        for sel in old_select_keys - desired_selects:
            if sel[0] not in settings_being_updated:  # Only delete if not already handled above
                to_delete.append({"type": "select", "filter": {"setting_id": sel[0], "value": self._empty_if_none(sel[1]), "order": sel[2]}})

    def _it_diff_jobs(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for JOBS."""
        old_jobs = old["jobs"]
        desired_jobs = desired["jobs"]

        old_job_keys = set(old_jobs.keys())
        new_job_keys = set(desired_jobs.keys())

        for jk in new_job_keys - old_job_keys:
            job = desired_jobs[jk]
            to_put.append(Jobs(plugin_id=jk[0], **job))

        for jk in old_job_keys & new_job_keys:
            old_j = old_jobs[jk]
            new_j = desired_jobs[jk]
            changed = any(getattr(old_j, k, None) != new_j.get(k) for k in new_j.keys())
            if changed:
                to_update.append({"type": "job", "filter": {"plugin_id": jk[0], "name": jk[1]}, "data": new_j})

        for jk in old_job_keys - new_job_keys:
            to_delete.append({"type": "job", "filter": {"plugin_id": jk[0], "name": jk[1]}})

    def _it_diff_plugin_pages(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for PLUGIN PAGES."""
        old_plugin_pages = old["plugin_pages"]
        desired_plugin_pages = desired["plugin_pages"]

        old_page_ids = set(old_plugin_pages.keys())
        new_page_ids = set(desired_plugin_pages.keys())

        for pid in new_page_ids - old_page_ids:
            pp = desired_plugin_pages[pid]
            to_put.append(Plugin_pages(plugin_id=pid, data=pp["data"], checksum=pp["checksum"]))

        for pid in old_page_ids & new_page_ids:
            old_pp = old_plugin_pages[pid]
            new_pp = desired_plugin_pages[pid]
            if old_pp.checksum != new_pp["checksum"]:
                to_update.append({"type": "plugin_page", "filter": {"plugin_id": pid}, "data": {"data": new_pp["data"], "checksum": new_pp["checksum"]}})

        for pid in old_page_ids - new_page_ids:
            to_delete.append({"type": "plugin_page", "filter": {"plugin_id": pid}})

    def _it_diff_cli_commands(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for CLI COMMANDS."""
        old_cli_commands = old["cli_commands"]
        desired_cli_commands = desired["cli_commands"]

        old_command_keys = set(old_cli_commands.keys())
        new_command_keys = set(desired_cli_commands.keys())

        for ck in new_command_keys - old_command_keys:
            to_put.append(Bw_cli_commands(name=ck[1], plugin_id=ck[0], file_name=desired_cli_commands[ck]))

        for ck in old_command_keys & new_command_keys:
            old_c = old_cli_commands[ck]
            new_file = desired_cli_commands[ck]
            if old_c.file_name != new_file:
                to_update.append({"type": "cli_command", "filter": {"plugin_id": ck[0], "name": ck[1]}, "data": {"file_name": new_file}})

        for ck in old_command_keys - new_command_keys:
            to_delete.append({"type": "cli_command", "filter": {"plugin_id": ck[0], "name": ck[1]}})

    def _it_diff_templates(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for TEMPLATES."""
        old_templates = old["templates"]
        desired_templates = desired["templates"]

        old_tmpl_keys = set(old_templates.keys())
        new_tmpl_keys = set(desired_templates.keys())

        for tk in new_tmpl_keys - old_tmpl_keys:
            current_time = datetime.now().astimezone()
            to_put.append(
                Templates(
                    id=tk[1],
                    plugin_id=tk[0],
                    name=desired_templates[tk]["name"],
                    method=desired_templates[tk]["method"],
                    creation_date=current_time,
                    last_update=current_time,
                )
            )

        for tk in old_tmpl_keys & new_tmpl_keys:
            old_t = old_templates[tk]
            new_t = desired_templates[tk]
            if old_t.name != new_t["name"]:
                to_update.append(
                    {
                        "type": "template",
                        "filter": {"plugin_id": tk[0], "id": tk[1]},
                        "data": {"name": new_t["name"], "method": new_t["method"], "last_update": datetime.now().astimezone()},
                    }
                )

        for tk in old_tmpl_keys - new_tmpl_keys:
            to_delete.append({"type": "template", "filter": {"plugin_id": tk[0], "id": tk[1]}})

    def _it_diff_template_steps(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for TEMPLATE STEPS."""
        old_template_steps = old["template_steps"]
        desired_template_steps = desired["template_steps"]

        old_step_keys = set(old_template_steps.keys())
        new_step_keys = set(desired_template_steps.keys())

        for st in new_step_keys - old_step_keys:
            to_put.append(Template_steps(id=st[1], template_id=st[0], **desired_template_steps[st]))

        for st in old_step_keys & new_step_keys:
            old_stp = old_template_steps[st]
            new_stp = desired_template_steps[st]
            if old_stp.title != new_stp["title"] or old_stp.subtitle != new_stp["subtitle"]:
                to_update.append(
                    {
                        "type": "template_step",
                        "filter": {"template_id": st[0], "id": st[1]},
                        "data": {"title": new_stp["title"], "subtitle": new_stp["subtitle"]},
                    }
                )

        for st in old_step_keys - new_step_keys:
            to_delete.append({"type": "template_step", "filter": {"template_id": st[0], "id": st[1]}})

    def _it_diff_template_settings(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for TEMPLATE SETTINGS."""
        old_template_settings = old["template_settings"]
        desired_template_settings = desired["template_settings"]

        old_ts_keys = set(old_template_settings.keys())
        new_ts_keys = set(desired_template_settings.keys())

        for tsk in new_ts_keys - old_ts_keys:
            template_id, setting_id, suffix, step_id, order = tsk
            default = desired_template_settings[tsk]
            to_put.append(
                Template_settings(
                    template_id=template_id,
                    setting_id=setting_id,
                    suffix=suffix,
                    step_id=step_id,
                    default=default,
                    order=order,
                )
            )

        for tsk in old_ts_keys & new_ts_keys:
            old_ts_val = old_template_settings[tsk]
            new_default = desired_template_settings[tsk]
            if old_ts_val != new_default:
                template_id, setting_id, suffix, step_id, order = tsk
                filter_data = {"template_id": template_id, "setting_id": setting_id, "step_id": step_id}
                if suffix is not None:
                    # Not all queries handle suffix well. If suffix is defined, add to filter:
                    filter_data["suffix"] = suffix
                to_update.append(
                    {
                        "type": "template_setting",
                        "filter": filter_data,
                        "data": {"default": self._empty_if_none(new_default), "suffix": suffix},
                    }
                )

        for tsk in old_ts_keys - new_ts_keys:
            template_id, setting_id, suffix, step_id, order = tsk
            filter_data = {"template_id": template_id, "setting_id": setting_id, "step_id": step_id}
            if suffix is not None:
                filter_data["suffix"] = suffix
            to_delete.append({"type": "template_setting", "filter": filter_data})

    def _it_diff_template_configs(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for TEMPLATE CONFIGS."""
        old_template_configs = old["template_configs"]
        desired_template_configs = desired["template_configs"]

        old_tc_keys = set(old_template_configs.keys())
        new_tc_keys = set(desired_template_configs.keys())

        for tck in new_tc_keys - old_tc_keys:
            template_id, ctype, cname, step_id, order = tck
            conf_data = desired_template_configs[tck]
            to_put.append(
                Template_custom_configs(
                    template_id=template_id,
                    type=ctype,
                    name=cname,
                    data=conf_data["data"],
                    checksum=conf_data["checksum"],
                    step_id=step_id,
                    order=order,
                )
            )

        for tck in old_tc_keys & new_tc_keys:
            old_tc_obj = old_template_configs[tck]
            new_tc_obj = desired_template_configs[tck]
            if old_tc_obj.checksum != new_tc_obj["checksum"]:
                template_id, ctype, cname, step_id, order = tck
                filter_data = {"template_id": template_id, "name": cname, "type": ctype, "step_id": step_id}
                to_update.append(
                    {
                        "type": "template_config",
                        "filter": filter_data,
                        "data": {"data": new_tc_obj["data"], "checksum": new_tc_obj["checksum"]},
                    }
                )

        for tck in old_tc_keys - new_tc_keys:
            template_id, ctype, cname, step_id, order = tck
            filter_data = {"template_id": template_id, "name": cname, "type": ctype, "step_id": step_id}
            to_delete.append({"type": "template_config", "filter": filter_data})

    def _it_diff_resource_groups(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for RESOURCE GROUPS (managed/core only — see _it_index_old_data)."""
        old_groups = old["resource_groups"]
        desired_groups = desired["resource_groups"]

        old_keys = set(old_groups.keys())
        new_keys = set(desired_groups.keys())

        for gk in new_keys - old_keys:
            current_time = datetime.now().astimezone()
            to_put.append(
                ResourceGroups(
                    id=gk[1],
                    plugin_id=gk[0],
                    name=desired_groups[gk]["name"],
                    description=desired_groups[gk]["description"],
                    method=desired_groups[gk]["method"],
                    creation_date=current_time,
                    last_update=current_time,
                )
            )

        for gk in old_keys & new_keys:
            old_g = old_groups[gk]
            new_g = desired_groups[gk]
            if old_g.name != new_g["name"] or self._empty_if_none(old_g.description) != self._empty_if_none(new_g["description"]):
                to_update.append(
                    {
                        "type": "resource_group",
                        "filter": {"plugin_id": gk[0], "id": gk[1]},
                        "data": {
                            "name": new_g["name"],
                            "description": new_g["description"],
                            "method": new_g["method"],
                            "last_update": datetime.now().astimezone(),
                        },
                    }
                )

        for gk in old_keys - new_keys:
            to_delete.append({"type": "resource_group", "filter": {"plugin_id": gk[0], "id": gk[1]}})

    def _it_diff_resource_group_entries(self, old: dict, desired: dict, to_put: list, to_update: list, to_delete: list) -> None:
        """Compute differences for RESOURCE GROUP ENTRIES (children of managed groups).

        Keyed by ``(group_id, kind, value, order)`` like template settings: a moved/changed
        entry is a delete+put, and ``_it_apply_deletes`` runs before the bulk insert, so the
        ``UNIQUE(group_id, order)`` constraint never collides mid-transaction.
        """
        old_entries = old["resource_group_entries"]
        desired_entries = desired["resource_group_entries"]

        old_keys = set(old_entries.keys())
        new_keys = set(desired_entries.keys())

        for ek in new_keys - old_keys:
            group_id, kind, value, order = ek
            to_put.append(ResourceGroup_entries(group_id=group_id, kind=kind, value=value, comment=desired_entries[ek], order=order))

        for ek in old_keys & new_keys:
            if self._empty_if_none(old_entries[ek]) != self._empty_if_none(desired_entries[ek]):
                group_id, kind, value, order = ek
                to_update.append(
                    {
                        "type": "resource_group_entry",
                        "filter": {"group_id": group_id, "kind": kind, "value": value, "order": order},
                        "data": {"comment": desired_entries[ek]},
                    }
                )

        for ek in old_keys - new_keys:
            group_id, kind, value, order = ek
            to_delete.append({"type": "resource_group_entry", "filter": {"group_id": group_id, "kind": kind, "value": value, "order": order}})

    def _it_apply_deletes(self, session, to_delete: list) -> None:
        """Apply the queued deletes on the given session."""
        for delete_op in to_delete:
            t = delete_op["type"]
            if t == "setting":
                session.execute(delete(Settings).filter_by(**delete_op["filter"]))
            elif t == "global_value":
                session.execute(delete(Global_values).filter_by(**delete_op["filter"]))
            elif t == "service_setting":
                session.execute(delete(Services_settings).filter_by(**delete_op["filter"]))
            elif t == "job":
                session.execute(delete(Jobs).filter_by(**delete_op["filter"]))
            elif t == "job_cache":
                session.execute(delete(Jobs_cache).filter_by(**delete_op["filter"]))
            elif t == "job_run":
                session.execute(delete(Jobs_runs).filter_by(**delete_op["filter"]))
            elif t == "plugin_page":
                session.execute(delete(Plugin_pages).filter_by(**delete_op["filter"]))
            elif t == "cli_command":
                session.execute(delete(Bw_cli_commands).filter_by(**delete_op["filter"]))
            elif t == "template":
                session.execute(delete(Templates).filter_by(**delete_op["filter"]))
            elif t == "template_step":
                session.execute(delete(Template_steps).filter_by(**delete_op["filter"]))
            elif t == "template_setting":
                session.execute(delete(Template_settings).filter_by(**delete_op["filter"]))
            elif t == "template_config":
                session.execute(delete(Template_custom_configs).filter_by(**delete_op["filter"]))
            elif t == "resource_group":
                session.execute(delete(ResourceGroups).filter_by(**delete_op["filter"]))
            elif t == "resource_group_entry":
                session.execute(delete(ResourceGroup_entries).filter_by(**delete_op["filter"]))
            elif t == "select":
                session.execute(delete(Selects).filter_by(**delete_op["filter"]))
            elif t == "multiselect":
                session.execute(delete(Multiselects).filter_by(**delete_op["filter"]))
            elif t == "plugin":
                session.execute(delete(Plugins).filter_by(**delete_op["filter"]))

    def _it_apply_updates(self, session, to_update: list) -> None:
        """Apply the queued updates on the given session."""
        for update_op in to_update:
            t = update_op["type"]
            if t == "setting":
                session.execute(update(Settings).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "job":
                session.execute(update(Jobs).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "plugin_page":
                session.execute(update(Plugin_pages).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "cli_command":
                session.execute(update(Bw_cli_commands).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "template_step":
                session.execute(update(Template_steps).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "template_setting":
                session.execute(update(Template_settings).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "template_config":
                session.execute(update(Template_custom_configs).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "resource_group":
                session.execute(update(ResourceGroups).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "resource_group_entry":
                session.execute(update(ResourceGroup_entries).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "plugin":
                session.execute(update(Plugins).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "template":
                session.execute(update(Templates).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "global_value":
                session.execute(update(Global_values).filter_by(**update_op["filter"]).values(update_op["data"]))
            elif t == "service_setting":
                session.execute(update(Services_settings).filter_by(**update_op["filter"]).values(update_op["data"]))

    def _it_validate_template_settings(self, session) -> None:
        """Delete template settings that fail is_valid_setting validation.

        Replaces the per-row ``self.is_valid_setting`` N+1 (1-3 SELECTs per template
        setting) with a single prefetch of the Settings columns it reads plus the
        Services.id list, then validates in pure Python — replicating the exact
        decision branches that this specific call pattern exercises
        (setting=key, value=default, multisite=True, session=<this session>,
        extra_services=None). The original ``is_valid_setting`` itself is untouched.
        Invalid row ids are collected and removed with a single bulk ``delete(... in_)``.
        Per-row ``logger.warning`` calls keep the same message strings and order
        (rows iterated by ``Template_settings.id``, matching the original PK-order scan).
        """
        # Prefetch exactly the Settings columns is_valid_setting reads for this call
        # pattern: id (lookup key), context (multisite check), multiple (multiple check),
        # regex + type (value regex check). Keyed by id for O(1) lookup.
        settings_by_id = {row.id: row for row in session.execute(select(Settings.id, Settings.context, Settings.multiple, Settings.regex, Settings.type))}
        # Services.id list for the service-prefix fallback lookup (deterministic order
        # is irrelevant: the first matching prefix wins exactly as in the original loop,
        # but service ids are disjoint prefixes so at most one can match).
        service_ids = [service.id for service in session.execute(select(Services.id))]

        invalid_ids = []
        for template_setting in session.execute(
            select(
                Template_settings.id,
                Template_settings.template_id,
                Template_settings.setting_id,
                Template_settings.suffix,
                Template_settings.default,
            ).order_by(Template_settings.id)
        ):
            setting_key = f"{template_setting.setting_id}_{template_setting.suffix}" if template_setting.suffix else template_setting.setting_id
            success, err = self._it_check_template_setting(setting_key, template_setting.default, settings_by_id, service_ids)

            if not success:
                self.logger.warning(
                    f'Template "{template_setting.template_id}"\'s Setting "{template_setting.setting_id}" isn\'t a valid template setting ({err}), deleting it'
                )
                invalid_ids.append(template_setting.id)

        if invalid_ids:
            session.execute(delete(Template_settings).where(Template_settings.id.in_(invalid_ids)))

    def _it_check_template_setting(self, setting: str, value, settings_by_id: dict, service_ids: List[str]) -> Tuple[bool, str]:
        """Pure-Python replica of ``is_valid_setting`` for the template-validation call
        pattern (multisite=True, value=default, extra_services=None). Returns the exact
        ``(success, err)`` tuple the original would produce, using prefetched data only.

        Branch map (mirrors ``check_setting`` in config_read.py):
          - SUFFIX_RX → strip suffix, set ``multiple=True``;
          - lookup by id, else service-prefix fallback (forces multisite=True);
          - missing → (False, "missing"); context != multisite → (False, "not multisite");
          - multiple & db.multiple is None → (False, "not multiple");
          - value regex check (DOTALL for type=="file", honouring _ignore_regex_check).
        ``multisite`` starts True (the caller always passes multisite=True).
        """
        multisite = True
        multiple = False
        if self.SUFFIX_RX.search(setting):
            setting = setting.rsplit("_", 1)[0]
            multiple = True

        db_setting = settings_by_id.get(setting)

        if db_setting is None:
            # extra_services is None here, so the original's first fallback loop is empty.
            for service_id in service_ids:
                if setting.startswith(f"{service_id}_"):
                    db_setting = settings_by_id.get(setting.replace(f"{service_id}_", ""))
                    multisite = True
                    break

        if db_setting is None:
            return False, "missing"

        if multisite and db_setting.context != "multisite":
            return False, "not multisite"
        elif multiple and db_setting.multiple is None:
            return False, "not multiple"

        if value is not None:
            try:
                regex_flags = DOTALL if db_setting.type == "file" else 0
                if not self._ignore_regex_check and search(db_setting.regex, value, regex_flags) is None:
                    return False, f"not matching regex: {db_setting.regex!r}"
            except RegexError:
                return False, f"invalid regex: {db_setting.regex!r}"

        return True, ""
