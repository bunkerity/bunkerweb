#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime
from json import JSONDecodeError, loads
from os import sep
from pathlib import Path
from typing import Any, Dict, List, Literal, Set, Tuple

from model import Bw_cli_commands, Global_values, Jobs, Jobs_cache, Jobs_runs, Metadata, Multiselects, Plugin_pages, Plugins, Selects, Services_settings, Settings, Template_custom_configs, Template_settings, Template_steps, Templates  # type: ignore

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore

from sqlalchemy import delete, select, update

from sqlalchemy.exc import OperationalError, ProgrammingError

from .common import DatabaseMixinBase, bulk_add_in_fk_order


class DatabasePluginsUpdateMixin(DatabaseMixinBase):
    """External/UI/pro plugin synchronisation (update_external_plugins)."""

    def update_external_plugins(
        self,
        plugins: List[Dict[str, Any]],
        *,
        _type: Literal["external", "ui", "pro"] = "external",
        delete_missing: bool = True,
        only_clear_metadata: bool = False,
        per_plugin_commit: bool = True,
    ) -> str:
        """Update external plugins from the database"""
        to_put = []
        changes = False
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            deleted, abort = self._uep_delete_missing_plugins(session, plugins, _type, delete_missing, only_clear_metadata)
            if abort:
                return ""
            if deleted:
                changes = True
                if per_plugin_commit:
                    try:
                        session.commit()
                    except BaseException as e:
                        return str(e)

            db_settings = [setting.id for setting in session.execute(select(Settings.id))]

            for plugin in plugins:
                local_to_put = []
                settings = plugin.pop("settings", {})
                jobs = plugin.pop("jobs", [])
                page = plugin.pop("page", False)
                commands = plugin.pop("bwcli", {})
                if not isinstance(commands, dict):
                    commands = {}
                plugin["type"] = _type
                db_plugin = session.execute(
                    select(
                        Plugins.name,
                        Plugins.stream,
                        Plugins.description,
                        Plugins.version,
                        Plugins.method,
                        Plugins.checksum,
                        Plugins.type,
                    )
                    .filter_by(id=plugin["id"])
                    .limit(1)
                ).first()

                if db_plugin:
                    skip_plugin, row_changed = self._uep_sync_plugin_row(session, plugin, db_plugin, _type)
                    if skip_plugin:
                        continue
                    changes = row_changed or changes

                    db_ids, prune_changed = self._uep_prune_removed_settings(session, plugin, db_plugin, settings)
                    changes = prune_changed or changes

                    settings_changed, plugin_settings = self._uep_sync_settings(session, plugin, settings, db_ids, local_to_put)
                    changes = settings_changed or changes

                    changes = self._uep_sync_jobs(session, plugin, jobs, local_to_put) or changes

                    plugin_path = self._uep_resolve_plugin_dir(plugin["id"], _type)

                    page_changed, abort_plugin = self._uep_sync_plugin_page(session, plugin, plugin_path, local_to_put)
                    changes = page_changed or changes
                    if abort_plugin:
                        continue

                    changes = self._uep_sync_cli_commands(session, plugin, commands, plugin_path, local_to_put) or changes

                    changes = self._uep_sync_templates(session, plugin, plugin_path, plugin_settings, db_settings, local_to_put) or changes

                    try:
                        if per_plugin_commit:
                            if local_to_put:
                                bulk_add_in_fk_order(session, local_to_put)
                            # Commit also captures any .update() / .delete() executed above.
                            session.commit()
                        else:
                            to_put.extend(local_to_put)
                    except BaseException as e:
                        session.rollback()
                        return str(e)

                    continue

                changes = True
                plugin_path, plugin_settings = self._uep_insert_plugin(session, plugin, settings, jobs, page, commands, _type, local_to_put)
                self._uep_insert_templates(session, plugin, plugin_path, plugin_settings, db_settings, local_to_put)

                try:
                    if per_plugin_commit:
                        if local_to_put:
                            bulk_add_in_fk_order(session, local_to_put)
                        # Commit also captures any .update() / .delete() executed above.
                        session.commit()
                    else:
                        to_put.extend(local_to_put)
                except BaseException as e:
                    session.rollback()
                    return str(e)

            if changes:
                self._uep_mark_metadata_changes(session, _type)

            try:
                if not per_plugin_commit and to_put:
                    bulk_add_in_fk_order(session, to_put)
                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)

        return ""

    def _uep_delete_missing_plugins(
        self, session, plugins: List[Dict[str, Any]], _type: str, delete_missing: bool, only_clear_metadata: bool
    ) -> Tuple[bool, bool]:
        """Remove (or metadata-clear) plugins of ``_type`` that are absent from ``plugins``.

        Returns ``(deleted, abort)``: ``deleted`` is True when missing plugins were
        processed (the caller flips ``changes`` and owns the commit); ``abort`` is True
        when the empty-list data-loss guard fired (the caller must return "").
        Never commits.
        """
        db_plugins = session.execute(select(Plugins.id).filter_by(type=_type)).all()

        db_ids = []
        if delete_missing and db_plugins:
            db_ids = [plugin.id for plugin in db_plugins]
            ids = [plugin["id"] for plugin in plugins]
            missing_ids = [plugin for plugin in db_ids if plugin not in ids]

            if missing_ids:
                # Data-loss guard: refuse the destructive plugin-wide cascade (Settings +
                # Global_values + Services_settings + Jobs + Templates + Plugin_pages) when
                # the incoming plugins list is entirely empty. An empty list almost always
                # signals a transient failure at the caller — a filesystem glob race during
                # `check_plugin_changes`, a read-only database window that returned no data,
                # a download job that failed after a `clean_pro_plugins` call — rather than a
                # legitimate mass-uninstall. Callers that genuinely want to wipe everything
                # should use `only_clear_metadata=True`, which is the explicit clean-up path
                # and is not affected by this guard.
                if not only_clear_metadata and not ids:
                    self.logger.warning(
                        f"Refusing to cascade-delete {len(missing_ids)} {_type} plugin(s) via "
                        f"delete_missing=True because the incoming plugins list is empty. "
                        f"Aborting update_external_plugins to prevent catastrophic data loss. "
                        f"Use only_clear_metadata=True for explicit wipe operations. "
                        f"missing_ids={sorted(missing_ids)}"
                    )
                    return False, True

                # Remove plugins that are no longer in the list
                if not only_clear_metadata:
                    session.execute(delete(Plugins).where(Plugins.id.in_(missing_ids)))

                    session.execute(delete(Plugin_pages).where(Plugin_pages.plugin_id.in_(missing_ids)))
                    session.execute(delete(Bw_cli_commands).where(Bw_cli_commands.plugin_id.in_(missing_ids)))

                    # Per-child bulk deletes: gather the child ids/names of every missing
                    # plugin once, then issue one ``in_()`` delete per child table instead
                    # of N per-row deletes. The parent ``Plugins`` rows are deleted first
                    # (above): on FK-enforced engines (MariaDB/MySQL/PostgreSQL) the
                    # ON DELETE CASCADE foreign keys remove the child rows automatically and
                    # the selects below return empty sets, so these become no-ops; on SQLite
                    # (foreign_keys pragma left off) the parent delete touches no children, so
                    # these explicit deletes by FK id do the cleanup. Either way the final
                    # state — every row of every missing plugin removed — is identical to the
                    # original per-row loop (verified differentially on SQLite + MariaDB).
                    job_names = [plugin_job.name for plugin_job in session.execute(select(Jobs.name).where(Jobs.plugin_id.in_(missing_ids)))]
                    if job_names:
                        session.execute(delete(Jobs_runs).where(Jobs_runs.job_name.in_(job_names)))
                        session.execute(delete(Jobs_cache).where(Jobs_cache.job_name.in_(job_names)))
                        session.execute(delete(Jobs).where(Jobs.name.in_(job_names)))

                    setting_ids = [plugin_setting.id for plugin_setting in session.execute(select(Settings.id).where(Settings.plugin_id.in_(missing_ids)))]
                    if setting_ids:
                        session.execute(delete(Selects).where(Selects.setting_id.in_(setting_ids)))
                        session.execute(delete(Services_settings).where(Services_settings.setting_id.in_(setting_ids)))
                        session.execute(delete(Global_values).where(Global_values.setting_id.in_(setting_ids)))
                        session.execute(delete(Settings).where(Settings.id.in_(setting_ids)))

                    template_ids = [plugin_template.id for plugin_template in session.execute(select(Templates.id).where(Templates.plugin_id.in_(missing_ids)))]
                    if template_ids:
                        session.execute(delete(Template_steps).where(Template_steps.template_id.in_(template_ids)))
                        session.execute(delete(Template_settings).where(Template_settings.template_id.in_(template_ids)))
                        session.execute(delete(Template_custom_configs).where(Template_custom_configs.template_id.in_(template_ids)))
                        session.execute(delete(Templates).where(Templates.id.in_(template_ids)))
                else:
                    session.execute(update(Plugins).where(Plugins.id.in_(missing_ids)).values({Plugins.data: None, Plugins.checksum: None}))

                return True, False

        return False, False

    def _uep_sync_plugin_row(self, session, plugin: Dict[str, Any], db_plugin: Any, _type: str) -> Tuple[bool, bool]:
        """Sync the Plugins row of an existing plugin.

        Returns ``(skip, changed)``: ``skip`` is True when the plugin must be skipped
        entirely (method mismatch or forbidden type — the caller ``continue``s).
        Never commits.
        """
        if plugin["method"] not in (db_plugin.method, "autoconf"):
            self.logger.warning(f'Plugin "{plugin["id"]}" already exists, but the method is different, skipping update')
            return True, False

        if db_plugin.type not in ("external", "ui", "pro"):
            self.logger.warning(
                f"Plugin \"{plugin['id']}\" is not {_type}, skipping update (updating a non-external, non-ui or non-pro plugin is forbidden for security reasons)",  # noqa: E501
            )
            return True, False

        updates = {}

        if plugin["stream"] != db_plugin.stream:
            updates[Plugins.stream] = plugin["stream"]

        if plugin["name"] != db_plugin.name:
            updates[Plugins.name] = plugin["name"]

        if plugin["description"] != db_plugin.description:
            updates[Plugins.description] = plugin["description"]

        if plugin["version"] != db_plugin.version:
            updates[Plugins.version] = plugin["version"]

        if plugin["method"] != db_plugin.method:
            updates[Plugins.method] = plugin["method"]

        if plugin.get("checksum") != db_plugin.checksum:
            updates[Plugins.checksum] = plugin.get("checksum")
            updates[Plugins.data] = plugin.get("data")

        if plugin.get("type") != db_plugin.type:
            updates[Plugins.type] = plugin.get("type")

        if updates:
            session.execute(update(Plugins).where(Plugins.id == plugin["id"]).values(updates))
            return False, True

        return False, False

    def _uep_prune_removed_settings(self, session, plugin: Dict[str, Any], db_plugin: Any, settings: Dict[str, Any]) -> Tuple[List[str], bool]:
        """Delete settings rows that disappeared from an existing plugin's plugin.json.

        Returns ``(db_ids, changed)`` where ``db_ids`` is the list of setting ids
        currently stored for this plugin (needed by the settings sync). Never commits.
        """
        db_ids = [setting.id for setting in session.execute(select(Settings.id).filter_by(plugin_id=plugin["id"]))]
        setting_ids = [setting for setting in settings]
        missing_ids = [setting for setting in db_ids if setting not in setting_ids]

        changed = False
        if missing_ids:
            # Data-loss guard: same-content reinstalls must never wipe user-set values.
            # We detect them by comparing the freshly-computed plugin checksum against
            # the one currently stored in the database. Identical checksums mean the
            # plugin archive is byte-for-byte the same as what we already have — i.e. a
            # spurious re-ingest (non-deterministic tar false positive, idempotent
            # re-upload, download-plugins re-run, etc.). A genuine plugin update always
            # changes the archive bytes, which flips the checksum and lets the cleanup
            # proceed to prune settings that have been truly removed from plugin.json.
            # The check is method-agnostic on purpose: checksum equality is a stronger
            # signal than any caller-supplied method/version string.
            incoming_checksum = plugin.get("checksum")
            db_checksum = db_plugin.checksum
            preserve_missing = bool(incoming_checksum) and bool(db_checksum) and incoming_checksum == db_checksum

            if preserve_missing:
                missing_preview = sorted(missing_ids)[:10]
                overflow = f" ... (+{len(missing_ids) - 10} more)" if len(missing_ids) > 10 else ""
                self.logger.info(
                    f"Plugin {plugin['id']!r} re-ingested with an identical checksum; "
                    f"preserving {len(missing_ids)} existing setting(s) to avoid data loss "
                    f"(missing from plugin.json: {missing_preview}{overflow})"
                )
            else:
                changed = True
                # Remove settings that are no longer in the list
                session.execute(delete(Settings).where(Settings.id.in_(missing_ids)))
                session.execute(delete(Selects).where(Selects.setting_id.in_(missing_ids)))
                session.execute(delete(Multiselects).where(Multiselects.setting_id.in_(missing_ids)))
                session.execute(delete(Services_settings).where(Services_settings.setting_id.in_(missing_ids)))
                session.execute(delete(Global_values).where(Global_values.setting_id.in_(missing_ids)))
                session.execute(delete(Template_settings).where(Template_settings.setting_id.in_(missing_ids)))

        return db_ids, changed

    def _uep_sync_settings(
        self, session, plugin: Dict[str, Any], settings: Dict[str, Any], db_ids: List[str], local_to_put: List[Any]
    ) -> Tuple[bool, Set[str]]:
        """Sync settings (and their selects/multiselects) of an existing plugin.

        Appends new ORM objects to ``local_to_put``. Returns ``(changed, plugin_settings)``
        where ``plugin_settings`` is the set of setting ids declared by the plugin
        (needed by the templates sync). Never commits.
        """
        changed = False
        order = 0
        plugin_settings = set()
        for setting, value in settings.items():
            value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})
            plugin_settings.add(setting)

            db_setting = session.execute(
                select(
                    Settings.name,
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
                    Settings.case_insensitive,
                )
                .filter_by(id=setting)
                .limit(1)
            ).first()

            if setting not in db_ids or not db_setting:
                changed = True
                for sel_order, sel_val in enumerate(value.pop("select", []), start=1):
                    local_to_put.append(Selects(setting_id=value["id"], value=self._empty_if_none(sel_val), order=sel_order))

                for msel_order, multiselect in enumerate(value.pop("multiselect", []), start=1):
                    if isinstance(multiselect, dict):
                        local_to_put.append(
                            Multiselects(
                                setting_id=setting,
                                option_id=multiselect.get("id", ""),
                                label=multiselect.get("label", ""),
                                value=self._empty_if_none(multiselect.get("value", "")),
                                order=msel_order,
                            )
                        )

                local_to_put.append(Settings(**value | {"order": order}))
            else:
                updates = {}

                if value["name"] != db_setting.name:
                    updates[Settings.name] = value["name"]

                if value["context"] != db_setting.context:
                    updates[Settings.context] = value["context"]

                if value["default"] != db_setting.default:
                    updates[Settings.default] = value["default"]

                if value["help"] != db_setting.help:
                    updates[Settings.help] = value["help"]

                if value["label"] != db_setting.label:
                    updates[Settings.label] = value["label"]

                if value["regex"] != db_setting.regex:
                    updates[Settings.regex] = value["regex"]

                if value["type"] != db_setting.type:
                    updates[Settings.type] = value["type"]

                if value.get("multiple") != db_setting.multiple:
                    updates[Settings.multiple] = value.get("multiple")

                if value.get("separator") != db_setting.separator:
                    updates[Settings.separator] = value.get("separator")

                if value.get("accept") != db_setting.accept:
                    updates[Settings.accept] = value.get("accept")

                if value.get("case_insensitive", False) != db_setting.case_insensitive:
                    updates[Settings.case_insensitive] = value.get("case_insensitive", False)

                if order != db_setting.order:
                    updates[Settings.order] = order

                if updates:
                    changed = True
                    session.execute(update(Settings).where(Settings.id == setting).values(updates))

                db_values = [
                    (self._empty_if_none(sel_val.value), sel_val.order)
                    for sel_val in session.execute(select(Selects.value, Selects.order).filter_by(setting_id=setting))
                ]
                select_values = enumerate(value.get("select", []), start=1)
                different_values = any(db_value != (value, order) for db_value, (value, order) in zip(db_values, select_values))

                if different_values:
                    changed = True
                    # Remove old selects
                    session.execute(delete(Selects).where(Selects.setting_id == setting))
                    # Add new selects with the new values
                    for sel_order, sel_val in enumerate(value.get("select", []), start=1):
                        local_to_put.append(Selects(setting_id=setting, value=self._empty_if_none(sel_val), order=sel_order))

                # Handle multiselects
                db_multiselect_values = [
                    (msel.option_id, msel.label, self._empty_if_none(msel.value), msel.order)
                    for msel in session.execute(
                        select(Multiselects.option_id, Multiselects.label, Multiselects.value, Multiselects.order).filter_by(setting_id=setting)
                    )
                ]
                multiselect_values = [
                    (msel.get("id", ""), msel.get("label", ""), self._empty_if_none(msel.get("value", "")), order)
                    for order, msel in enumerate(value.get("multiselect", []), start=1)
                    if isinstance(msel, dict)
                ]
                different_multiselect_values = db_multiselect_values != multiselect_values

                if different_multiselect_values:
                    changed = True
                    # Remove old multiselects
                    session.execute(delete(Multiselects).where(Multiselects.setting_id == setting))
                    # Add new multiselects with the new values
                    for msel_order, multiselect in enumerate(value.get("multiselect", []), start=1):
                        if isinstance(multiselect, dict):
                            local_to_put.append(
                                Multiselects(
                                    setting_id=setting,
                                    option_id=multiselect.get("id", ""),
                                    label=multiselect.get("label", ""),
                                    value=self._empty_if_none(multiselect.get("value", "")),
                                    order=msel_order,
                                )
                            )

            order += 1

        return changed, plugin_settings

    def _uep_sync_jobs(self, session, plugin: Dict[str, Any], jobs: List[Dict[str, Any]], local_to_put: List[Any]) -> bool:
        """Sync jobs of an existing plugin (prune removed ones, add/update the rest).

        Appends new ORM objects to ``local_to_put``. Returns the changed flag.
        Never commits.
        """
        changed = False
        db_names = [job.name for job in session.execute(select(Jobs.name).filter_by(plugin_id=plugin["id"]))]
        job_names = [job["name"] for job in jobs]
        missing_names = [job for job in db_names if job not in job_names]

        if missing_names:
            changed = True
            # Remove jobs that are no longer in the list
            session.execute(delete(Jobs).where(Jobs.name.in_(missing_names)))
            session.execute(delete(Jobs_cache).where(Jobs_cache.job_name.in_(missing_names)))
            session.execute(delete(Jobs_runs).where(Jobs_runs.job_name.in_(missing_names)))

        for job in jobs:
            db_job = session.execute(
                select(Jobs.file_name, Jobs.every, Jobs.reload, Jobs.run_async).filter_by(name=job["name"], plugin_id=plugin["id"]).limit(1)
            ).first()

            if job["name"] not in db_names or not db_job:
                changed = True
                job["file_name"] = job.pop("file")
                job["reload"] = job.get("reload", False)
                job["run_async"] = job.pop("async", False)
                local_to_put.append(Jobs(plugin_id=plugin["id"], **job))
            else:
                updates = {}

                if job["file"] != db_job.file_name:
                    updates[Jobs.file_name] = job["file"]

                if job["every"] != db_job.every:
                    updates[Jobs.every] = job["every"]

                if job.get("reload", False) != db_job.reload:
                    updates[Jobs.reload] = job.get("reload", False)

                if job.get("async", False) != db_job.run_async:
                    updates[Jobs.run_async] = job.get("async", False)

                if updates:
                    changed = True
                    updates[Jobs.last_run] = None
                    session.execute(delete(Jobs_runs).where(Jobs_runs.job_name == job["name"]))
                    session.execute(delete(Jobs_cache).where(Jobs_cache.job_name == job["name"]))
                    session.execute(update(Jobs).where(Jobs.name == job["name"]).values(updates))

        return changed

    def _uep_resolve_plugin_dir(self, plugin_id: str, _type: str) -> Path:
        """Resolve the on-disk plugin directory: the UI upload tmp dir when present,
        otherwise the external or pro plugins directory depending on ``_type``."""
        plugin_path = Path(sep, "var", "tmp", "bunkerweb", "ui", plugin_id)
        return (
            plugin_path
            if plugin_path.is_dir()
            else (Path(sep, "etc", "bunkerweb", "plugins", plugin_id) if _type == "external" else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin_id))
        )

    def _uep_sync_plugin_page(self, session, plugin: Dict[str, Any], plugin_path: Path, local_to_put: List[Any]) -> Tuple[bool, bool]:
        """Sync the plugin page (ui dir tarball) of an existing plugin.

        Appends new ORM objects to ``local_to_put``. Returns ``(changed, abort_plugin)``:
        ``abort_plugin`` is True when archiving failed — the caller must ``continue``,
        skipping the rest of this plugin (cli commands, templates and the per-plugin
        commit), exactly like the original inline ``continue``. Never commits.
        """
        changed = False
        path_ui = plugin_path.joinpath("ui")

        db_plugin_page = session.execute(select(Plugin_pages.checksum).filter_by(plugin_id=plugin["id"]).limit(1)).first()
        remove = not path_ui.is_dir() and db_plugin_page

        if path_ui.is_dir():
            remove = True
            try:
                plugin_page_content = create_plugin_tar_gz(path_ui)
                checksum = bytes_hash(plugin_page_content, algorithm="sha256")
                content = plugin_page_content.getvalue()
            except (FileNotFoundError, OSError) as e:
                self.logger.warning(f"Some files in {path_ui} could not be archived: {e}")
                remove = False
                return changed, True

            if not db_plugin_page:
                changed = True
                local_to_put.append(Plugin_pages(plugin_id=plugin["id"], data=content, checksum=checksum))
                remove = False
            elif checksum != db_plugin_page.checksum:
                changed = True
                session.execute(
                    update(Plugin_pages).where(Plugin_pages.plugin_id == plugin["id"]).values({Plugin_pages.data: content, Plugin_pages.checksum: checksum})
                )
                remove = False

        if db_plugin_page and remove:
            changed = True
            session.execute(delete(Plugin_pages).where(Plugin_pages.plugin_id == plugin["id"]))

        return changed, False

    def _uep_sync_cli_commands(self, session, plugin: Dict[str, Any], commands: Dict[str, Any], plugin_path: Path, local_to_put: List[Any]) -> bool:
        """Sync bwcli commands of an existing plugin.

        Appends new ORM objects to ``local_to_put``. Returns the changed flag.
        Never commits.
        """
        changed = False
        db_names = [command.name for command in session.execute(select(Bw_cli_commands.name).filter_by(plugin_id=plugin["id"]))]
        missing_names = [command for command in db_names if command not in commands]

        if missing_names:
            # Remove commands that are no longer in the list
            session.execute(delete(Bw_cli_commands).where(Bw_cli_commands.name.in_(missing_names), Bw_cli_commands.plugin_id == plugin["id"]))

        for command, file_name in commands.items():
            db_command = session.execute(select(Bw_cli_commands.file_name).filter_by(name=command, plugin_id=plugin["id"]).limit(1)).first()
            command_path = plugin_path.joinpath("bwcli", file_name)

            if command not in db_names or not db_command:
                if not command_path.is_file():
                    self.logger.warning(
                        f'Plugin "{plugin["id"]}"\'s Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it'
                    )
                    continue

                changed = True
                local_to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))
            else:
                updates = {}

                if file_name != db_command.file_name:
                    updates[Bw_cli_commands.file_name] = file_name

                if updates:
                    changed = True
                    if not command_path.is_file():
                        session.execute(delete(Bw_cli_commands).filter_by(name=command, plugin_id=plugin["id"]))
                        continue
                    session.execute(update(Bw_cli_commands).filter_by(name=command, plugin_id=plugin["id"]).values(updates))

        return changed

    def _uep_sync_templates(
        self, session, plugin: Dict[str, Any], plugin_path: Path, plugin_settings: Set[str], db_settings: List[str], local_to_put: List[Any]
    ) -> bool:
        """Sync templates (steps, settings, custom configs) of an existing plugin.

        Appends new ORM objects to ``local_to_put``. Returns the changed flag.
        Never commits.
        """
        changed = False
        db_names = [template.id for template in session.execute(select(Templates.id).filter_by(plugin_id=plugin["id"]))]
        templates_path = plugin_path.joinpath("templates")

        if templates_path.is_dir():
            saved_templates = set()
            for template_file in templates_path.iterdir():
                if template_file.is_dir():
                    continue

                try:
                    template_data = loads(template_file.read_text())
                except JSONDecodeError:
                    self.logger.error(
                        f"{plugin.get('type', 'core').title()} Plugin \"{plugin['id']}\"'s Template file \"{template_file}\" is not a valid JSON file"
                    )
                    continue

                template_id = template_file.stem

                db_template = session.execute(select(Templates.id).filter_by(id=template_id, plugin_id=plugin["id"]).limit(1)).first()

                if not db_template:
                    changed = True
                    current_time = datetime.now().astimezone()
                    local_to_put.append(
                        Templates(
                            id=template_id,
                            plugin_id=plugin["id"],
                            name=template_data.get("name", template_id),
                            method=plugin["method"],
                            creation_date=current_time,
                            last_update=current_time,
                        )
                    )

                saved_templates.add(template_id)

                db_ids = [step.id for step in session.execute(select(Template_steps.id).filter_by(template_id=template_id))]
                missing_ids = [x for x in range(1, len(template_data.get("steps", [])) + 1) if x not in db_ids]

                if missing_ids:
                    changed = True
                    session.execute(delete(Template_settings).where(Template_settings.step_id.in_(missing_ids)))
                    session.execute(delete(Template_custom_configs).where(Template_custom_configs.step_id.in_(missing_ids)))
                    session.execute(delete(Template_steps).where(Template_steps.id.in_(missing_ids)))

                steps_settings = {}
                steps_configs = {}
                for step_id, step in enumerate(template_data.get("steps", []), start=1):
                    db_step = session.execute(
                        select(Template_steps.id, Template_steps.title, Template_steps.subtitle).filter_by(id=step_id, template_id=template_id).limit(1)
                    ).first()
                    if not db_step:
                        changed = True
                        local_to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))
                    else:
                        updates = {}

                        if step["title"] != db_step.title:
                            updates[Template_steps.title] = step["title"]

                        if step["subtitle"] != db_step.subtitle:
                            updates[Template_steps.subtitle] = step["subtitle"]

                        if updates:
                            changed = True
                            session.execute(update(Template_steps).where(Template_steps.id == db_step.id).values(updates))

                    for setting in step.get("settings", []):
                        if step_id not in steps_settings:
                            steps_settings[step_id] = []
                        steps_settings[step_id].append(setting)

                    for config in step.get("configs", []):
                        if step_id not in steps_configs:
                            steps_configs[step_id] = []
                        steps_configs[step_id].append(config)

                db_template_settings = [
                    f"{template_setting.setting_id}_{template_setting.suffix}" if template_setting.suffix else template_setting.setting_id
                    for template_setting in session.execute(
                        select(Template_settings.id, Template_settings.setting_id, Template_settings.suffix)
                        .filter_by(template_id=template_id)
                        .order_by(Template_settings.order)
                    )
                ]
                missing_ids = [setting for setting in template_data.get("settings", {}) if setting not in db_template_settings]

                if missing_ids:
                    changed = True
                    session.execute(delete(Template_settings).where(Template_settings.id.in_(missing_ids)))

                order = 0
                for setting, default in template_data.get("settings", {}).items():
                    setting_id, suffix = setting.rsplit("_", 1) if self.SUFFIX_RX.search(setting) else (setting, None)
                    if suffix is not None:
                        suffix = int(suffix)
                    else:
                        suffix = 0

                    if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is restricted, skipping it'
                        )
                        session.execute(delete(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix))
                        continue
                    elif setting_id not in plugin_settings and setting_id not in db_settings:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" does not exist, skipping it'
                        )
                        session.execute(delete(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix))
                        continue

                    success, err = self.is_valid_setting(setting_id, value=default, multisite=True, session=session)
                    if not success:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is not a valid template setting ({err}), skipping it'
                        )
                        session.execute(delete(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix))
                        continue

                    step_id = None
                    for step, settings in steps_settings.items():
                        if setting in settings:
                            step_id = step
                            break

                    if not step_id:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" doesn\'t belong to a step, skipping it'
                        )
                        continue

                    template_setting = session.execute(
                        select(
                            Template_settings.id,
                            Template_settings.step_id,
                            Template_settings.default,
                            Template_settings.order,
                        )
                        .filter_by(template_id=template_id, setting_id=setting_id, step_id=step_id, suffix=suffix)
                        .limit(1)
                    ).first()

                    if not template_setting:
                        changed = True
                        local_to_put.append(
                            Template_settings(
                                template_id=template_id,
                                setting_id=setting_id,
                                step_id=step_id,
                                suffix=suffix,
                                default=default,
                                order=order,
                            )
                        )
                    elif step_id != template_setting.step_id or default != template_setting.default or order != template_setting.order:
                        changed = True
                        session.execute(
                            update(Template_settings)
                            .filter_by(id=template_setting.id)
                            .values(
                                {
                                    Template_settings.step_id: step_id,
                                    Template_settings.default: default,
                                    Template_settings.order: order,
                                }
                            )
                        )

                    order += 1

                db_template_configs = [
                    f"{config.type.replace('_', '-')}/{config.name}.conf"
                    for config in session.execute(
                        select(Template_custom_configs.type, Template_custom_configs.name)
                        .filter_by(template_id=template_id)
                        .order_by(Template_custom_configs.order)
                    )
                ]
                missing_ids = [config for config in template_data.get("configs", {}) if config not in db_template_configs]

                if missing_ids:
                    changed = True
                    session.execute(delete(Template_custom_configs).where(Template_custom_configs.name.in_(missing_ids)))

                order = 0
                for config in template_data.get("configs", []):
                    try:
                        config_type, config_name = config.split("/", 1)
                    except ValueError:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                        )
                        continue

                    if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is not a valid type, skipping it'
                        )
                        continue

                    if not templates_path.joinpath(template_id, "configs", config_type, config_name).is_file():
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" does not exist, skipping it'
                        )
                        continue

                    content = templates_path.joinpath(template_id, "configs", config_type, config_name).read_bytes()
                    config_type = config_type.strip().replace("-", "_").lower()
                    checksum = bytes_hash(content, algorithm="sha256")
                    config_name = config_name.removesuffix(".conf")

                    step_id = None
                    for step, configs in steps_configs.items():
                        if config in configs:
                            step_id = step
                            break

                    if not step_id:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" doesn\'t belong to a step, skipping it'
                        )
                        continue

                    template_config = session.execute(
                        select(
                            Template_custom_configs.id,
                            Template_custom_configs.step_id,
                            Template_custom_configs.checksum,
                            Template_custom_configs.order,
                        )
                        .filter_by(template_id=template_id, step_id=step_id, type=config_type, name=config_name)
                        .limit(1)
                    ).first()

                    if not template_config:
                        changed = True
                        local_to_put.append(
                            Template_custom_configs(
                                template_id=template_id,
                                step_id=step_id,
                                type=config_type,
                                name=config_name,
                                data=content,
                                checksum=checksum,
                                order=order,
                            )
                        )
                    elif step_id != template_config.step_id or checksum != template_config.checksum or order != template_config.order:
                        changed = True
                        session.execute(
                            update(Template_custom_configs)
                            .filter_by(id=template_config.id)
                            .values(
                                {
                                    Template_custom_configs.step_id: step_id,
                                    Template_custom_configs.data: content,
                                    Template_custom_configs.checksum: checksum,
                                    Template_custom_configs.order: order,
                                }
                            )
                        )

                    order += 1

            stale_templates = [template for template in db_names if template not in saved_templates]
            if stale_templates:
                changed = True
                # One bulk in_() delete per child table (children before parent — order
                # preserved from the original per-template loop). Net rows deleted identical.
                session.execute(delete(Template_steps).where(Template_steps.template_id.in_(stale_templates)))
                session.execute(delete(Template_settings).where(Template_settings.template_id.in_(stale_templates)))
                session.execute(delete(Template_custom_configs).where(Template_custom_configs.template_id.in_(stale_templates)))
                session.execute(delete(Templates).where(Templates.id.in_(stale_templates), Templates.plugin_id == plugin["id"]))

        elif db_names:
            self.logger.warning(f'Plugin "{plugin["id"]}"\'s templates directory does not exist, removing all templates')
            # One bulk in_() delete per table (parent-first order preserved from the
            # original per-template loop). The single warning above is emitted once.
            session.execute(delete(Templates).where(Templates.id.in_(db_names), Templates.plugin_id == plugin["id"]))
            session.execute(delete(Template_steps).where(Template_steps.template_id.in_(db_names)))
            session.execute(delete(Template_settings).where(Template_settings.template_id.in_(db_names)))
            session.execute(delete(Template_custom_configs).where(Template_custom_configs.template_id.in_(db_names)))

        return changed

    def _uep_insert_plugin(
        self,
        session,
        plugin: Dict[str, Any],
        settings: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        page: bool,
        commands: Dict[str, Any],
        _type: str,
        local_to_put: List[Any],
    ) -> Tuple[Path, Set[str]]:
        """Stage a brand-new plugin: row, settings (+selects/multiselects), jobs,
        plugin page and bwcli commands.

        Appends new ORM objects to ``local_to_put``. Returns ``(plugin_path,
        plugin_settings)`` for the templates insertion. Never commits.
        """
        local_to_put.append(
            Plugins(
                id=plugin["id"],
                name=plugin["name"],
                description=plugin["description"],
                version=plugin["version"],
                stream=plugin["stream"],
                type=_type,
                method=plugin["method"],
                data=plugin.get("data"),
                checksum=plugin.get("checksum"),
            )
        )

        order = 0
        plugin_settings = set()
        for setting, value in settings.items():
            db_setting = session.scalars(select(Settings).filter_by(id=setting).limit(1)).first()

            if db_setting is not None:
                self.logger.warning(f"A setting with id {setting} already exists, therefore it will not be added.")
                continue

            value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})

            for sel_order, sel_val in enumerate(value.pop("select", []), start=1):
                local_to_put.append(Selects(setting_id=value["id"], value=self._empty_if_none(sel_val), order=sel_order))

            for msel_order, multiselect in enumerate(value.pop("multiselect", []), start=1):
                if isinstance(multiselect, dict):
                    local_to_put.append(
                        Multiselects(
                            setting_id=value["id"],
                            option_id=multiselect.get("id", ""),
                            label=multiselect.get("label", ""),
                            value=self._empty_if_none(multiselect.get("value", "")),
                            order=msel_order,
                        )
                    )

            local_to_put.append(Settings(**value | {"order": order}))
            order += 1
            plugin_settings.add(setting)

        for job in jobs:
            db_job = session.scalars(select(Jobs).filter_by(name=job["name"], plugin_id=plugin["id"]).limit(1)).first()

            if db_job is not None:
                self.logger.warning(f"A job with the name {job['name']} already exists in the database, therefore it will not be added.")
                continue

            job["file_name"] = job.pop("file")
            job["reload"] = job.get("reload", False)
            job["run_async"] = job.pop("async", False)
            local_to_put.append(Jobs(plugin_id=plugin["id"], **job))

        plugin_path = self._uep_resolve_plugin_dir(plugin["id"], _type)

        if page:
            path_ui = plugin_path.joinpath("ui")
            if path_ui.is_dir():
                try:
                    plugin_page_content = create_plugin_tar_gz(path_ui)
                    checksum = bytes_hash(plugin_page_content, algorithm="sha256")
                    local_to_put.append(Plugin_pages(plugin_id=plugin["id"], data=plugin_page_content.getvalue(), checksum=checksum))
                except (FileNotFoundError, OSError) as e:
                    self.logger.warning(f"Some files in {path_ui} could not be archived: {e}")

        for command, file_name in commands.items():
            if not plugin_path.joinpath("bwcli", file_name).is_file():
                self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                continue

            local_to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))

        return plugin_path, plugin_settings

    def _uep_insert_templates(
        self, session, plugin: Dict[str, Any], plugin_path: Path, plugin_settings: Set[str], db_settings: List[str], local_to_put: List[Any]
    ) -> None:
        """Stage templates (steps, settings, custom configs) of a brand-new plugin.

        Appends new ORM objects to ``local_to_put``. Never commits.
        """
        templates_path = plugin_path.joinpath("templates")

        if templates_path.is_dir():
            for template_file in plugin_path.joinpath("templates").iterdir():
                if template_file.is_dir():
                    continue

                try:
                    template_data = loads(template_file.read_text())
                except JSONDecodeError:
                    self.logger.error(f'Template file "{template_file}" is not a valid JSON file')
                    continue

                template_id = template_file.stem
                current_time = datetime.now().astimezone()

                local_to_put.append(
                    Templates(
                        id=template_id,
                        plugin_id=plugin["id"],
                        name=template_data.get("name", template_id),
                        method=plugin["method"],
                        creation_date=current_time,
                        last_update=current_time,
                    )
                )

                steps_settings = {}
                steps_configs = {}
                for step_id, step in enumerate(template_data.get("steps", []), start=1):
                    local_to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))

                    for setting in step.get("settings", []):
                        if step_id not in steps_settings:
                            steps_settings[step_id] = []
                        steps_settings[step_id].append(setting)

                    for config in step.get("configs", []):
                        if step_id not in steps_configs:
                            steps_configs[step_id] = []
                        steps_configs[step_id].append(config)

                order = 0
                for setting, default in template_data.get("settings", {}).items():
                    setting_id, suffix = setting.rsplit("_", 1) if self.SUFFIX_RX.search(setting) else (setting, None)
                    if suffix is not None:
                        suffix = int(suffix)
                    else:
                        suffix = 0

                    if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is restricted, skipping it'
                        )
                        continue
                    elif setting_id not in plugin_settings and setting_id not in db_settings:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" does not exist, skipping it'
                        )
                        continue

                    success, err = self.is_valid_setting(setting_id, value=default, multisite=True, session=session)
                    if not success:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is not a valid template setting ({err}), skipping it'
                        )
                        continue

                    step_id = None
                    for step, settings in steps_settings.items():
                        if setting in settings:
                            step_id = step
                            break

                    if not step_id:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" doesn\'t belong to a step, skipping it'
                        )
                        continue

                    local_to_put.append(
                        Template_settings(
                            template_id=template_id,
                            setting_id=setting_id,
                            step_id=step_id,
                            default=default,
                            suffix=suffix,
                            order=order,
                        )
                    )
                    order += 1

                order = 0
                for config in template_data.get("configs", []):
                    try:
                        config_type, config_name = config.split("/", 1)
                    except ValueError:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                        )
                        continue

                    if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is not a valid type, skipping it'
                        )
                        continue

                    if not templates_path.joinpath(template_id, "configs", config_type, config_name).is_file():
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" does not exist, skipping it'
                        )
                        continue

                    content = templates_path.joinpath(template_id, "configs", config_type, config_name).read_bytes()
                    config_type = config_type.strip().replace("-", "_").lower()
                    checksum = bytes_hash(content, algorithm="sha256")
                    config_name = config_name.removesuffix(".conf")

                    step_id = None
                    for step, configs in steps_configs.items():
                        if config in configs:
                            step_id = step
                            break

                    if not step_id:
                        self.logger.error(
                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" doesn\'t belong to a step, skipping it'
                        )
                        continue

                    local_to_put.append(
                        Template_custom_configs(
                            template_id=template_id,
                            step_id=step_id,
                            type=config_type,
                            name=config_name,
                            data=content,
                            checksum=checksum,
                            order=order,
                        )
                    )
                    order += 1

    def _uep_mark_metadata_changes(self, session, _type: str) -> None:
        """Flag the Metadata row so other components reload the changed plugins.
        Never commits."""
        with suppress(ProgrammingError, OperationalError):
            metadata = session.get(Metadata, 1)
            if metadata is not None:
                if _type in ("external", "ui"):
                    metadata.external_plugins_changed = True
                    metadata.last_external_plugins_change = datetime.now().astimezone()
                    metadata.reload_ui_plugins = True
                elif _type == "pro":
                    metadata.pro_plugins_changed = True
                    metadata.last_pro_plugins_change = datetime.now().astimezone()
                    metadata.reload_ui_plugins = True
