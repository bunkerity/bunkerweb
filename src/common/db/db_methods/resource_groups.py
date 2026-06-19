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
from re import compile as re_compile, escape as re_escape
from typing import Any, Dict, List, Optional, Tuple

from model import Global_values, Plugins, ResourceGroup_entries, ResourceGroups, Services_settings  # type: ignore

from resource_validation import RESOURCE_KINDS, validate_resource_value  # type: ignore

from sqlalchemy import delete, select

from .common import DatabaseMixinBase

# Methods whose rows the UI/API may freely edit (mirrors is_editable_method in the UI layer).
_EDITABLE_METHODS = ("ui", "api", "wizard")


class DatabaseResourceGroupsMixin(DatabaseMixinBase):
    """Reusable resource group management."""

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
                            {"kind": entry.kind, "value": entry.value, "comment": self._empty_if_none(entry.comment), "order": entry.order}
                        )

            return groups

    def get_resource_group_details(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single resource group with its ordered entries, or None."""
        with self._db_session() as session:
            group = session.scalars(select(ResourceGroups).filter_by(id=group_id).limit(1)).first()
            if not group:
                return None

            entries: List[Dict[str, Any]] = []
            for entry in session.execute(
                select(
                    ResourceGroup_entries.kind,
                    ResourceGroup_entries.value,
                    ResourceGroup_entries.comment,
                    ResourceGroup_entries.order,
                )
                .filter_by(group_id=group_id)
                .order_by(ResourceGroup_entries.order)
            ):
                entries.append({"kind": entry.kind, "value": entry.value, "comment": self._empty_if_none(entry.comment), "order": entry.order})

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

    def _prepare_group_entries(self, entries: Optional[List[Dict[str, Any]]]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Validate/normalize the incoming entries, dedupe on (kind, value), assign order."""
        if entries is None:
            entries = []
        if not isinstance(entries, list):
            return "Resource group entries must be a list", []

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
                comment = str(comment_raw).strip() or None
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

            normalized_name = (name or "").strip()
            if not normalized_name:
                return "Resource group name cannot be empty"

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
                    description=self._empty_if_none(description),
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
        current = self.get_resource_group_details(group_id)
        if not current:
            return "Resource group not found"
        if current["method"] not in _EDITABLE_METHODS:
            return "This resource group is provided by BunkerWeb and cannot be modified"

        effective_entries = entries if entries is not None else current["entries"]

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
                conflict = session.execute(
                    select(ResourceGroups.id).filter(ResourceGroups.name == normalized_name, ResourceGroups.id != group_id).limit(1)
                ).first()
                if conflict:
                    return f"Resource group name {normalized_name} already exists"
                group.name = normalized_name

            if description is not None:
                group.description = self._empty_if_none(description)

            group.method = "ui"
            group.last_update = datetime.now().astimezone()

            error, entry_entities = self._prepare_group_entries(effective_entries)
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

            # Best-effort reference check: refuse deletion while a setting value still
            # references the @name token (LIKE narrows, the regex enforces the token boundary).
            token_rx = re_compile(r"@" + re_escape(group.name) + r"(?![A-Za-z0-9_-])")
            like_pattern = f"%@{group.name}%"
            for table in (Global_values, Services_settings):
                for row in session.execute(select(table.value).filter(table.value.like(like_pattern))):
                    value = row[0]
                    if value and token_rx.search(value):
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
