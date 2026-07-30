#!/usr/bin/env python3
"""Security workflow resources: CRUD, definition storage and service attachment.

A workflow is the third typed vertical on ``bw_resources`` after redirects and upstreams,
and the first that stores its whole payload as one canonical JSON document rather than
columns: a rule tree is nested and is only ever read as a whole, by the compiler.

Writes are the strict layer. The compiler is fail-closed — a definition it cannot compile
aborts the entire config push, for every plugin — so anything it would reject is rejected
here, where the operator is still looking at the form.
"""

from datetime import datetime, timezone
from json import JSONDecodeError, loads
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from model import Global_values, Plugins, ResourceAttachments, ResourceGroupUsages, Resources, Services, Services_settings, Workflows  # type: ignore
from sqlalchemy import delete, or_, select, update

from workflow_schema import (  # type: ignore
    MAX_ACTIVE_RULES_PER_SERVICE,
    MAX_PCRE_PER_SERVICE,
    MAX_PREDICATES_PER_SERVICE,
    PROVIDER_REQUIREMENTS,
    SCHEMA_VERSION,
    canonical_json,
    challenge_providers,
    collect_group_refs,
    rule_stats,
    validate_definition,
)

from .common import DatabaseMixinBase

WORKFLOW_MAX_NAME_LENGTH = 256
EMPTY_DEFINITION = canonical_json({"schema_version": SCHEMA_VERSION, "rules": []})
WORKFLOW_PLUGIN_ID = "workflows"
WORKFLOW_CONSUMER_TYPE = "workflow"


class DatabaseWorkflowsMixin(DatabaseMixinBase):
    """Workflow resource CRUD, definition validation and service assignment."""

    @staticmethod
    def _flag_workflows_config_changed(session) -> None:
        """Signal the scheduler that the compiled workflow artefact is out of date.

        Same mechanism as redirects: the scheduler already watches per-plugin
        ``config_changed``, and a workflow only ever affects generated configuration.
        """
        session.execute(update(Plugins).where(Plugins.id == "workflows").values(config_changed=True, last_config_change=datetime.now().astimezone()))

    @staticmethod
    def _replace_group_usages(session, resource_id: str, definition: Optional[Dict[str, Any]]) -> None:
        """Re-register which resource groups this workflow references.

        Called inside the mutating method's own session so the rules and the usages they
        imply commit together — a usage row that outlived its rule would refuse a legitimate
        group deletion forever. ``definition`` is ``None`` when the workflow is going away.
        """
        session.execute(
            delete(ResourceGroupUsages).where(ResourceGroupUsages.consumer_type == WORKFLOW_CONSUMER_TYPE, ResourceGroupUsages.consumer_id == resource_id),
            execution_options={"synchronize_session": False},
        )
        if definition is None:
            return
        # ``plugin_id`` is a foreign key. A database without the core plugin registered yet
        # (a bare test fixture) simply records no usage rather than failing the write.
        if session.execute(select(Plugins.id).where(Plugins.id == WORKFLOW_PLUGIN_ID).limit(1)).first() is None:
            return
        for group_id, _kind in sorted(collect_group_refs(definition)):
            # One row per group, not per (group, kind): the question this answers is "may
            # this group be deleted", and the unique constraint would reject the duplicate.
            if session.execute(
                select(ResourceGroupUsages.id)
                .where(
                    ResourceGroupUsages.group_id == group_id,
                    ResourceGroupUsages.plugin_id == WORKFLOW_PLUGIN_ID,
                    ResourceGroupUsages.consumer_type == WORKFLOW_CONSUMER_TYPE,
                    ResourceGroupUsages.consumer_id == resource_id,
                )
                .limit(1)
            ).first():
                continue
            session.add(ResourceGroupUsages(group_id=group_id, plugin_id=WORKFLOW_PLUGIN_ID, consumer_type=WORKFLOW_CONSUMER_TYPE, consumer_id=resource_id))

    @staticmethod
    def _attached_service_ids(session, resource_id: str) -> List[str]:
        return list(session.scalars(select(ResourceAttachments.service_id).where(ResourceAttachments.resource_id == resource_id)).all())

    def _workflow_attachments(self, session, resource_ids: List[str]) -> Dict[str, List[str]]:
        attachments: Dict[str, List[str]] = {resource_id: [] for resource_id in resource_ids}
        if not resource_ids:
            return attachments
        for row in session.execute(
            select(ResourceAttachments.resource_id, ResourceAttachments.service_id)
            .where(ResourceAttachments.resource_id.in_(resource_ids))
            .order_by(ResourceAttachments.service_id)
        ):
            attachments[row.resource_id].append(row.service_id)
        return attachments

    @staticmethod
    def _load_definition(raw: str) -> Dict[str, Any]:
        """Parse a stored definition, degrading to the empty one rather than raising.

        A row can only hold what ``save_workflow_definition`` accepted, so this is a
        belt-and-braces guard for a hand-edited database; the compiler is the layer that
        refuses to ship a broken definition.
        """
        try:
            parsed = loads(raw or EMPTY_DEFINITION)
        except JSONDecodeError:
            return {"schema_version": SCHEMA_VERSION, "rules": []}
        return parsed if isinstance(parsed, dict) else {"schema_version": SCHEMA_VERSION, "rules": []}

    def _workflow_dict(self, resource, workflow, services: List[str], *, with_definition: bool = False) -> dict:
        definition = self._load_definition(workflow.definition)
        stats = rule_stats(definition, enabled_only=False)
        item = {
            "id": resource.id,
            "name": resource.name,
            "description": resource.description or "",
            "schema_version": workflow.schema_version,
            "rules_count": stats["rules"],
            "enabled_rules_count": rule_stats(definition)["rules"],
            "services": services,
            "creation_date": resource.creation_date.isoformat(),
            "last_update": resource.last_update.isoformat(),
        }
        if with_definition:
            item["definition"] = definition
        return item

    def get_workflows(self, *, search: str = "", service_id: str = "", offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        with self._db_session() as session:
            query = select(Resources, Workflows).join(Workflows, Workflows.resource_id == Resources.id).order_by(Resources.name)
            if search:
                pattern = f"%{search.strip()}%"
                query = query.where(or_(Resources.name.ilike(pattern), Resources.description.ilike(pattern)))
            rows = list(session.execute(query))
            attachments = self._workflow_attachments(session, [resource.id for resource, _ in rows])
            items = [self._workflow_dict(resource, workflow, attachments[resource.id]) for resource, workflow in rows]

        if service_id:
            items = [item for item in items if service_id in item["services"]]
        total = len(items)
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return {"items": items[offset : offset + limit], "total": total, "offset": offset, "limit": limit}  # noqa: E203

    def get_workflow_details(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self._db_session() as session:
            row = session.execute(
                select(Resources, Workflows).join(Workflows, Workflows.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return None
            return self._workflow_dict(row[0], row[1], self._workflow_attachments(session, [resource_id])[resource_id], with_definition=True)

    @staticmethod
    def _service_workflows(session) -> Dict[str, List[Dict[str, Any]]]:
        """Session-taking core of :meth:`get_service_workflows`.

        Draft services are excluded. They render nothing, and their settings are absent from
        the generated config — so compiling their workflows would check a challenge provider's
        credentials against the (empty) global fallback and abort the whole push for a service
        that was never going to be served.
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in session.execute(
            select(ResourceAttachments.service_id, Resources.id, Resources.name, Workflows.schema_version, Workflows.definition)
            .join(Resources, Resources.id == ResourceAttachments.resource_id)
            .join(Workflows, Workflows.resource_id == Resources.id)
            .join(Services, Services.id == ResourceAttachments.service_id)
            .where(Services.is_draft.is_(False))
            .order_by(ResourceAttachments.creation_date, Resources.name)
        ):
            result.setdefault(row.service_id, []).append({"id": row.id, "name": row.name, "schema_version": row.schema_version, "definition": row.definition})
        return result

    def get_service_workflows(self) -> Dict[str, List[Dict[str, Any]]]:
        """Every attached workflow, keyed by service id, in evaluation order.

        Ordered by attachment date then resource name: the artefact lists workflows per
        service in this order and the runtime stops at the first effective match, so an
        unstable order would silently change which rule wins between two renders.
        """
        with self._db_session() as session:
            return self._service_workflows(session)

    def _service_budget_error(self, session, resource_id: str, definition: Optional[Dict[str, Any]], service_ids: List[str]) -> str:
        """Refuse a write that would push a service past the aggregate runtime budgets.

        Evaluated per service across *every* workflow attached to it, with ``definition``
        substituted for this resource's stored one (``None`` when the caller is attaching a
        workflow whose definition is unchanged). The per-workflow caps in
        ``workflow_schema`` bound one document; these bound what a request actually pays.
        """
        if not service_ids:
            return ""
        attached = self._service_workflows(session)
        for service_id in service_ids:
            totals = {"rules": 0, "predicates": 0, "pcre": 0}
            entries = {entry["id"]: entry for entry in attached.get(service_id, [])}
            entries.pop(resource_id, None)
            for entry in entries.values():
                for key, value in rule_stats(self._load_definition(entry["definition"])).items():
                    totals[key] += value
            if definition is not None:
                for key, value in rule_stats(definition).items():
                    totals[key] += value
            if totals["rules"] > MAX_ACTIVE_RULES_PER_SERVICE:
                return f"Service {service_id} would hold {totals['rules']} active workflow rules (maximum {MAX_ACTIVE_RULES_PER_SERVICE})"
            if totals["predicates"] > MAX_PREDICATES_PER_SERVICE:
                return f"Service {service_id} would hold {totals['predicates']} workflow predicates (maximum {MAX_PREDICATES_PER_SERVICE})"
            if totals["pcre"] > MAX_PCRE_PER_SERVICE:
                return f"Service {service_id} would hold {totals['pcre']} workflow regular expressions (maximum {MAX_PCRE_PER_SERVICE})"
        return ""

    @staticmethod
    def _provider_prerequisite_error(session, definition: Optional[Dict[str, Any]], service_ids: List[str]) -> str:
        """Refuse a write whose challenge rules the target services could not render.

        The compiler enforces the same rule, but it is fail-closed: reaching it means the whole
        configuration push aborts for *every* service until someone detaches the workflow. This
        check turns that into a 400 in the operator's form, which is the only reason the
        compiler's version should ever be unreachable.

        Only the *presence* of each credential is read, never its value.
        """
        if definition is None or not service_ids:
            return ""
        providers = challenge_providers(definition)
        required = sorted({setting for provider in providers for setting in PROVIDER_REQUIREMENTS.get(provider, ())})
        if not required:
            return ""

        # Multisite settings fall back to the global value, so both scopes are needed.
        fallback = {
            row.setting_id: row.value
            for row in session.execute(select(Global_values.setting_id, Global_values.value).where(Global_values.setting_id.in_(required), Global_values.suffix == 0))
        }
        per_service = {
            (row.service_id, row.setting_id): row.value
            for row in session.execute(
                select(Services_settings.service_id, Services_settings.setting_id, Services_settings.value).where(
                    Services_settings.service_id.in_(service_ids), Services_settings.setting_id.in_(required), Services_settings.suffix == 0
                )
            )
        }

        for service_id in service_ids:
            for provider in sorted(providers):
                for setting in PROVIDER_REQUIREMENTS.get(provider, ()):
                    value = per_service.get((service_id, setting))
                    if value is None:
                        value = fallback.get(setting)
                    if not (value or "").strip():
                        return f"Service {service_id} cannot serve a {provider} challenge: {setting} is not configured"
        return ""

    def _check_name(self, session, name: str, resource_id: str = "") -> Tuple[str, str]:
        normalized = name.strip()
        if not normalized:
            return "", "Workflow name is required"
        if len(normalized) > WORKFLOW_MAX_NAME_LENGTH:
            return "", f"Workflow names cannot exceed {WORKFLOW_MAX_NAME_LENGTH} characters"
        query = select(Resources.id).where(Resources.type == "workflow", Resources.name == normalized)
        if resource_id:
            query = query.where(Resources.id != resource_id)
        if session.execute(query.limit(1)).first():
            return "", f"Workflow name {normalized} already exists"
        return normalized, ""

    def create_workflow(self, *, name: str, description: str = "", definition: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Create a workflow resource. Returns ``(resource_id, error)``."""
        with self._db_session() as session:
            if self.readonly:
                return "", "The database is read-only, the changes will not be saved"

            normalized, error = self._check_name(session, name)
            if error:
                return "", error

            stored = EMPTY_DEFINITION
            canonical = None
            if definition is not None:
                group_index = self._get_resource_group_index(session, by="id")
                canonical, errors = validate_definition(definition, group_index=group_index)
                if canonical is None:
                    return "", errors[0]["message"] if errors else "Invalid workflow definition"
                stored = canonical_json(canonical)

            resource_id = str(uuid4())
            now = datetime.now(timezone.utc)
            session.add(Resources(id=resource_id, type="workflow", name=normalized, description=description, creation_date=now, last_update=now))
            session.add(Workflows(resource_id=resource_id, schema_version=SCHEMA_VERSION, definition=stored))
            if canonical is not None:
                self._replace_group_usages(session, resource_id, canonical)
            try:
                # No config_changed flag: a workflow attached to nothing compiles to nothing,
                # so creation alone must not trigger a generation and a reload.
                session.commit()
            except BaseException as exc:
                return "", f"An error occurred while creating workflow: {exc}"
        return resource_id, ""

    def update_workflow(self, resource_id: str, *, name: Optional[str] = None, description: Optional[str] = None) -> str:
        """Rename or re-describe a workflow. The rules live in :meth:`save_workflow_definition`."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            resource = session.get(Resources, resource_id)
            if resource is None or resource.type != "workflow":
                return "Workflow not found"

            if name is not None:
                normalized, error = self._check_name(session, name, resource_id)
                if error:
                    return error
                resource.name = normalized
            if description is not None:
                resource.description = description

            resource.last_update = datetime.now(timezone.utc)
            try:
                # Renaming changes nothing the runtime reads (rules reference ids), so no
                # config_changed flag: it would cost every instance a needless reload.
                session.commit()
            except BaseException as exc:
                return f"An error occurred while updating workflow: {exc}"
        return ""

    def save_workflow_definition(self, resource_id: str, definition: Any) -> Tuple[str, List[Dict[str, str]]]:
        """Replace a workflow's rules atomically. Returns ``(error, field_errors)``.

        ``field_errors`` carry the ``path``/``code``/``message`` triplet the editor anchors
        inline; ``error`` is the single message for callers that only surface one.
        """
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved", []
            workflow = session.get(Workflows, resource_id)
            if workflow is None:
                return "Workflow not found", []

            group_index = self._get_resource_group_index(session, by="id")
            canonical, errors = validate_definition(definition, group_index=group_index)
            if canonical is None:
                return (errors[0]["message"] if errors else "Invalid workflow definition"), errors

            attached = self._attached_service_ids(session, resource_id)
            if attached:
                # Lock the target services for the rest of the transaction. Without it two
                # concurrent saves on two workflows of the same service each read a budget that
                # is still under the cap, both commit, and the sum blows it — which the
                # fail-closed compiler then turns into a deployment-wide push failure.
                session.execute(select(Services.id).where(Services.id.in_(attached)).with_for_update())
            if error := self._service_budget_error(session, resource_id, canonical, attached):
                return error, []
            if error := self._provider_prerequisite_error(session, canonical, attached):
                return error, []

            workflow.schema_version = SCHEMA_VERSION
            workflow.definition = canonical_json(canonical)
            self._replace_group_usages(session, resource_id, canonical)
            resource = session.get(Resources, resource_id)
            if resource is not None:
                resource.last_update = datetime.now(timezone.utc)
            try:
                if attached:
                    self._flag_workflows_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while saving workflow definition: {exc}", []
        return "", []

    def validate_workflow_definition(
        self, definition: Any, *, resource_id: str = "", service_ids: Optional[List[str]] = None
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, str]], str]:
        """Check a draft definition without storing it. Returns ``(canonical, errors, budget_error)``.

        What the editor calls on every change: same validator, same live group index and
        same aggregate budgets as :meth:`save_workflow_definition`, so "it validates" here
        means "it will save" — and, because the compiler shares the validator, "it will
        compile" too. ``service_ids`` projects the budgets onto the services the operator
        intends to attach, which is the only check a not-yet-attached draft cannot infer.
        """
        with self._db_session() as session:
            canonical, errors = validate_definition(definition, group_index=self._get_resource_group_index(session, by="id"))
            if canonical is None:
                return None, errors, ""
            targets = list(service_ids) if service_ids is not None else self._attached_service_ids(session, resource_id)
            return canonical, [], self._service_budget_error(session, resource_id, canonical, targets)

    def clone_workflow(self, resource_id: str, *, name: str) -> Tuple[str, str]:
        """Copy a workflow's rules under a new name. Attachments are not copied."""
        with self._db_session() as session:
            if self.readonly:
                return "", "The database is read-only, the changes will not be saved"
            row = session.execute(
                select(Resources, Workflows).join(Workflows, Workflows.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return "", "Workflow not found"
            source, workflow = row

            normalized, error = self._check_name(session, name)
            if error:
                return "", error

            new_id = str(uuid4())
            now = datetime.now(timezone.utc)
            session.add(Resources(id=new_id, type="workflow", name=normalized, description=source.description or "", creation_date=now, last_update=now))
            # Rule ids are copied as-is: they are unique inside a workflow, and the runtime
            # counter key is scoped by workflow id, so two clones never share a bucket.
            session.add(Workflows(resource_id=new_id, schema_version=workflow.schema_version, definition=workflow.definition))
            # The copy references the same groups, so it must protect them too — otherwise a
            # group used only by clones could be deleted out from under them.
            self._replace_group_usages(session, new_id, self._load_definition(workflow.definition))
            try:
                session.commit()
            except BaseException as exc:
                return "", f"An error occurred while cloning workflow: {exc}"
        return new_id, ""

    def delete_workflow(self, resource_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            resource = session.get(Resources, resource_id)
            if resource is None or resource.type != "workflow":
                return "Workflow not found"
            if session.execute(select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id).limit(1)).first():
                return "Workflow is attached to a service"
            # Usages are keyed by consumer id, not by a foreign key on the resource, so the
            # cascade cannot reclaim them.
            self._replace_group_usages(session, resource_id, None)
            session.delete(resource)
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while deleting workflow: {exc}"
        return ""

    def attach_workflow(self, resource_id: str, service_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            workflow = session.get(Workflows, resource_id)
            if workflow is None:
                return "Workflow not found"
            service = session.execute(select(Services).where(Services.id == service_id).with_for_update()).scalar_one_or_none()
            if service is None:
                return "Service not found"
            if session.execute(
                select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id).limit(1)
            ).first():
                return ""  # already attached: idempotent, and nothing changed to signal

            definition = self._load_definition(workflow.definition)
            if error := self._service_budget_error(session, resource_id, definition, [service_id]):
                return error
            if error := self._provider_prerequisite_error(session, definition, [service_id]):
                return error

            # is_primary stays False and match_path stays "": every attached workflow is
            # evaluated, in attachment order, for the whole service.
            session.add(ResourceAttachments(resource_id=resource_id, service_id=service_id, is_primary=False, creation_date=datetime.now(timezone.utc)))
            try:
                self._flag_workflows_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while attaching workflow: {exc}"
        return ""

    def detach_workflow(self, resource_id: str, service_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            result = session.execute(
                delete(ResourceAttachments).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id),
                execution_options={"synchronize_session": False},
            )
            if not result.rowcount:
                return "Workflow attachment not found"
            try:
                self._flag_workflows_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while detaching workflow: {exc}"
        return ""
