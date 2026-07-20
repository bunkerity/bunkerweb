#!/usr/bin/env python3
"""Resource group management (DB layer).

A *resource group* is a named, reusable collection of typed security primitives
(IP/CIDR, country, ASN, rDNS, user-agent, URI) with an optional per-entry
comment, referenced from list settings via an ``@name`` token. Modeled on the
Templates feature: ``method``/``plugin_id`` mark core (immutable, seeded) vs
user-owned (editable) groups. Phase 1 only creates user groups (``method="ui"``);
core seeding lands later, hence the immutability guard here already refuses to
mutate non-editable groups.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from model import (
    Global_values,
    Plugins,
    ResourceGroup_entries,
    ResourceGroups,
    Services_settings,
    Settings,
    Template_settings,
    Templates,
)  # type: ignore

from resource_group_resolver import RESOURCE_LIST_SETTINGS  # type: ignore
from resource_validation import (  # type: ignore
    RESOURCE_GROUP_MAX_COMMENT_LENGTH,
    RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH,
    RESOURCE_GROUP_MAX_ENTRIES,
    RESOURCE_GROUP_MAX_VALUE_LENGTH,
    RESOURCE_KINDS,
    validate_resource_group_alias,
    validate_resource_value,
)

from sqlalchemy import delete, select

from .common import DatabaseMixinBase

# Methods whose rows the UI/API may freely edit (mirrors is_editable_method in the UI layer).
_EDITABLE_METHODS = ("ui", "api", "wizard")


class DatabaseResourceGroupsMixin(DatabaseMixinBase):
    """Reusable resource group management."""

    @staticmethod
    def _get_resource_group_index(session) -> Dict[str, Dict[str, List[str]]]:
        """Build the live alias/kind index inside the caller's transaction."""
        index: Dict[str, Dict[str, List[str]]] = {}
        for row in session.execute(
            select(
                ResourceGroups.name,
                ResourceGroup_entries.kind,
                ResourceGroup_entries.value,
            )
            .outerjoin(
                ResourceGroup_entries,
                ResourceGroup_entries.group_id == ResourceGroups.id,
            )
            .order_by(ResourceGroups.name, ResourceGroup_entries.order)
        ):
            group = index.setdefault(row.name, {})
            if row.kind is not None:
                group.setdefault(row.kind, []).append(row.value)
        return index

    def get_resource_groups(self, plugin: Optional[str] = None) -> Dict[str, dict]:
        """Get all resource groups keyed by id, each with its ordered entries."""
        with self._db_session() as session:
            query = select(
                ResourceGroups.id,
                ResourceGroups.name,
                ResourceGroups.description,
                ResourceGroups.method,
                ResourceGroups.plugin_id,
                ResourceGroups.creation_date,
                ResourceGroups.last_update,
            ).order_by(ResourceGroups.name)
            if plugin:
                query = query.filter_by(plugin_id=plugin)

            groups: Dict[str, dict] = {}
            for group in session.execute(query):
                groups[group.id] = {
                    "name": group.name,
                    "description": self._empty_if_none(group.description),
                    "method": group.method,
                    "plugin_id": group.plugin_id,
                    "creation_date": group.creation_date,
                    "last_update": group.last_update,
                    "entries": [],
                }

            if groups:
                for entry in session.execute(
                    select(
                        ResourceGroup_entries.group_id,
                        ResourceGroup_entries.kind,
                        ResourceGroup_entries.value,
                        ResourceGroup_entries.comment,
                        ResourceGroup_entries.order,
                    ).order_by(ResourceGroup_entries.group_id, ResourceGroup_entries.order)
                ):
                    if entry.group_id in groups:
                        groups[entry.group_id]["entries"].append(
                            {
                                "kind": entry.kind,
                                "value": entry.value,
                                "comment": self._empty_if_none(entry.comment),
                                "order": entry.order,
                            }
                        )

            return groups

    def get_resource_group_details(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single resource group with its ordered entries, or None."""
        with self._db_session() as session:
            group = session.scalars(select(ResourceGroups).filter_by(id=group_id).limit(1)).first()
            if not group:
                return None

            entries: List[Dict[str, Any]] = [
                {
                    "kind": entry.kind,
                    "value": entry.value,
                    "comment": self._empty_if_none(entry.comment),
                    "order": entry.order,
                }
                for entry in session.execute(
                    select(
                        ResourceGroup_entries.kind,
                        ResourceGroup_entries.value,
                        ResourceGroup_entries.comment,
                        ResourceGroup_entries.order,
                    )
                    .filter_by(group_id=group_id)
                    .order_by(ResourceGroup_entries.order)
                )
            ]

            return {
                "id": group.id,
                "name": group.name,
                "description": self._empty_if_none(group.description),
                "method": group.method,
                "plugin_id": group.plugin_id,
                "creation_date": group.creation_date,
                "last_update": group.last_update,
                "entries": entries,
            }

    @staticmethod
    def _get_resource_group_references(session, groups: Dict[str, str]) -> Dict[str, List[Dict[str, Any]]]:
        """Return setting rows that reference the supplied ``{id: name}`` groups."""
        references: Dict[str, List[Dict[str, Any]]] = {group_id: [] for group_id in groups}
        if not groups:
            return references
        tokens = {group_id: f"@{name}" for group_id, name in groups.items()}
        compatible_settings = tuple(RESOURCE_LIST_SETTINGS)

        global_rows = session.execute(
            select(
                Global_values.value,
                Global_values.setting_id,
                Global_values.suffix,
                Global_values.method,
                Settings.plugin_id,
            )
            .join(Settings, Settings.id == Global_values.setting_id)
            .where(Global_values.value.like("%@%"), Settings.id.in_(compatible_settings))
        )
        service_rows = session.execute(
            select(
                Services_settings.value,
                Services_settings.setting_id,
                Services_settings.suffix,
                Services_settings.method,
                Settings.plugin_id,
                Services_settings.service_id,
            )
            .join(Settings, Settings.id == Services_settings.setting_id)
            .where(
                Services_settings.value.like("%@%"),
                Settings.id.in_(compatible_settings),
            )
        )
        template_rows = session.execute(
            select(
                Template_settings.default,
                Template_settings.setting_id,
                Template_settings.suffix,
                Settings.plugin_id,
                Templates.id.label("template_id"),
                Templates.name.label("template_name"),
                Templates.method,
            )
            .join(Settings, Settings.id == Template_settings.setting_id)
            .join(Templates, Templates.id == Template_settings.template_id)
            .where(
                Template_settings.default.like("%@%"),
                Settings.id.in_(compatible_settings),
            )
        )

        for row in global_rows:
            row_tokens = row.value.split() if row.value else ()
            for group_id, token in tokens.items():
                if token in row_tokens:
                    references[group_id].append(
                        {
                            "scope": "global",
                            "service_id": None,
                            "setting_id": row.setting_id,
                            "suffix": row.suffix or 0,
                            "method": row.method,
                            "plugin_id": row.plugin_id,
                        }
                    )
        for row in service_rows:
            row_tokens = row.value.split() if row.value else ()
            for group_id, token in tokens.items():
                if token in row_tokens:
                    references[group_id].append(
                        {
                            "scope": "service",
                            "service_id": row.service_id,
                            "setting_id": row.setting_id,
                            "suffix": row.suffix or 0,
                            "method": row.method,
                            "plugin_id": row.plugin_id,
                        }
                    )
        for row in template_rows:
            row_tokens = row.default.split() if row.default else ()
            for group_id, token in tokens.items():
                if token in row_tokens:
                    references[group_id].append(
                        {
                            "scope": "template",
                            "service_id": None,
                            "template_id": row.template_id,
                            "template_name": row.template_name,
                            "setting_id": row.setting_id,
                            "suffix": row.suffix or 0,
                            "method": row.method,
                            "plugin_id": row.plugin_id,
                        }
                    )

        for group_references in references.values():
            group_references.sort(
                key=lambda ref: (
                    ref["scope"],
                    ref.get("service_id") or ref.get("template_id") or "",
                    ref["setting_id"],
                    ref["suffix"],
                )
            )
        return references

    def get_resource_group_references(self, group_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Return references for one group, or for every group when no id is supplied."""
        with self._db_session() as session:
            query = select(ResourceGroups.id, ResourceGroups.name)
            if group_id is not None:
                query = query.filter_by(id=group_id)
            groups = {group.id: group.name for group in session.execute(query)}
            return self._get_resource_group_references(session, groups)

    def _prepare_group_entries(self, entries: Optional[List[Dict[str, Any]]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Validate/normalize the incoming entries, dedupe on (kind, value), assign order."""
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            return "Resource group entries must be a list", []
        if len(entries) > RESOURCE_GROUP_MAX_ENTRIES:
            return (
                f"A resource group cannot contain more than {RESOURCE_GROUP_MAX_ENTRIES} entries",
                [],
            )

        seen: set = set()
        prepared: List[Dict[str, Any]] = []
        order = 0
        for raw in entries:
            if not isinstance(raw, dict):
                return "Each resource group entry must be an object", []
            kind = str(raw.get("kind", "")).strip().lower()
            if kind not in RESOURCE_KINDS:
                return f"Invalid entry kind: {kind!r}", []
            raw_value = raw.get("value")
            value = "" if raw_value is None else str(raw_value)
            if len(value) > RESOURCE_GROUP_MAX_VALUE_LENGTH:
                return (
                    f"Resource group entry values cannot exceed {RESOURCE_GROUP_MAX_VALUE_LENGTH} characters",
                    [],
                )
            ok, normalized = validate_resource_value(kind, value)
            if not ok:
                return f"Invalid {kind} value: {value.strip()!r}", []
            dedupe_key = (kind, normalized)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            comment_raw = raw.get("comment")
            comment = None
            if comment_raw is not None:
                comment_value = str(comment_raw)
                if len(comment_value) > RESOURCE_GROUP_MAX_COMMENT_LENGTH:
                    return (
                        f"Resource group entry comments cannot exceed {RESOURCE_GROUP_MAX_COMMENT_LENGTH} characters",
                        [],
                    )
                comment = comment_value.strip() or None
            order += 1
            prepared.append({"kind": kind, "value": normalized, "comment": comment, "order": order})

        return None, prepared

    def create_resource_group(
        self,
        group_id: str,
        *,
        name: str,
        description: Optional[str] = "",
        entries: Optional[List[Dict[str, Any]]] = None,
        method: str = "ui",
        plugin_id: Optional[str] = None,
    ) -> str:
        """Create a new resource group. Returns an error string ("" on success)."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            group_id = group_id.strip()
            if not group_id:
                return "Resource group id is required"
            if alias_error := validate_resource_group_alias(group_id, allow_reserved=method not in _EDITABLE_METHODS):
                return f"Resource group id {alias_error}"

            normalized_name = name.strip()
            if not normalized_name:
                return "Resource group name cannot be empty"
            if alias_error := validate_resource_group_alias(normalized_name, allow_reserved=method not in _EDITABLE_METHODS):
                return f"Resource group alias {alias_error}"

            normalized_description = "" if description is None else str(description)
            if len(normalized_description) > RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH:
                return f"Resource group descriptions cannot exceed {RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH} characters"

            normalized_plugin = None
            if isinstance(plugin_id, str):
                normalized_plugin = plugin_id.strip() or None

            if session.execute(select(ResourceGroups.id).filter_by(id=group_id).limit(1)).first():
                return f"Resource group {group_id} already exists"

            if session.execute(select(ResourceGroups.id).filter(ResourceGroups.name == normalized_name).limit(1)).first():
                return f"Resource group name {normalized_name} already exists"

            if normalized_plugin and session.execute(select(Plugins.id).filter_by(id=normalized_plugin).limit(1)).first() is None:
                return f"Plugin {normalized_plugin} does not exist"

            error, entry_entities = self._prepare_group_entries(entries)
            if error:
                return error

            current_time = datetime.now().astimezone()
            session.add(
                ResourceGroups(
                    id=group_id,
                    name=normalized_name,
                    description=normalized_description,
                    method=method or "ui",
                    plugin_id=normalized_plugin,
                    creation_date=current_time,
                    last_update=current_time,
                )
            )
            for entry in entry_entities:
                session.add(ResourceGroup_entries(group_id=group_id, **entry))

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while creating resource group {group_id}.\n{e}"

        return ""

    def update_resource_group(
        self,
        group_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        entries: Optional[List[Dict[str, Any]]] = None,
        plugin_id: Optional[str] = None,
    ) -> str:
        """Update an existing (editable) resource group. Returns an error string ("" on success)."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            group = session.scalars(select(ResourceGroups).filter_by(id=group_id).limit(1)).first()
            if group is None:
                return "Resource group not found"
            if group.method not in _EDITABLE_METHODS:
                return "This resource group is provided by BunkerWeb and cannot be modified"

            if plugin_id is not None:
                normalized_plugin = (plugin_id.strip() or None) if isinstance(plugin_id, str) else (str(plugin_id) or None)
                if normalized_plugin != group.plugin_id:
                    if normalized_plugin and session.execute(select(Plugins.id).filter_by(id=normalized_plugin).limit(1)).first() is None:
                        return f"Plugin {normalized_plugin} does not exist"
                    group.plugin_id = normalized_plugin

            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    return "Resource group name cannot be empty"
                if normalized_name != group.name:
                    return "Resource group aliases cannot be modified; clone the group with a new alias instead"

            if description is not None:
                normalized_description = str(description)
                if len(normalized_description) > RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH:
                    return f"Resource group descriptions cannot exceed {RESOURCE_GROUP_MAX_DESCRIPTION_LENGTH} characters"
                group.description = normalized_description

            group.method = "ui"
            group.last_update = datetime.now().astimezone()

            if entries is not None:
                error, entry_entities = self._prepare_group_entries(entries)
                if error:
                    return error

                session.execute(delete(ResourceGroup_entries).filter_by(group_id=group_id).execution_options(synchronize_session=False))
                for entry in entry_entities:
                    session.add(ResourceGroup_entries(group_id=group_id, **entry))

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating resource group {group_id}.\n{e}"

        return ""

    def delete_resource_group(self, group_id: str) -> str:
        """Delete an (editable) resource group when no setting references its @name."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            group = session.scalars(select(ResourceGroups).filter_by(id=group_id).limit(1)).first()
            if group is None:
                return "Resource group not found"
            if group.method not in _EDITABLE_METHODS:
                return "This resource group is provided by BunkerWeb and cannot be deleted"

            if self._get_resource_group_references(session, {group.id: group.name})[group.id]:
                return f"Resource group {group.name} is currently referenced by a setting"

            session.delete(group)

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting resource group {group_id}.\n{e}"

        return ""

    def clone_resource_group(self, src_id: str, new_id: str, *, name: str) -> str:
        """Clone any resource group (core or user) into a new editable (method="ui") group.

        This is how a core/immutable group is "adapted": the copy is user-owned, so the
        original stays pristine. Reuses create_resource_group for all validation.
        """
        src = self.get_resource_group_details(src_id)
        if not src:
            return "Resource group not found"
        return self.create_resource_group(
            new_id,
            name=name,
            description=src.get("description", ""),
            entries=src.get("entries", []),
            method="ui",
            plugin_id=None,
        )
