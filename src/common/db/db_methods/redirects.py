#!/usr/bin/env python3
"""Reusable HTTP redirect resources: CRUD, service attachment and expansion input."""

from datetime import datetime, timezone
from re import compile as re_compile, error as re_error
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from model import Global_values, Plugins, Redirects, ResourceAttachments, Resources, Services, Services_settings, Settings  # type: ignore
from sqlalchemy import delete, or_, select, update

from .common import DatabaseMixinBase

# The redirect core plugin owns the schema for these values; a redirect resource is the same
# rule stored as a first-class object instead of four suffixed settings, so it must accept
# exactly what an inline rule accepts. The regexes are read from the Settings rows the plugin
# registered rather than copied here, so the two can never drift.
REDIRECT_FIELD_SETTINGS = {
    "from_path": "REDIRECT_FROM",
    "to_url": "REDIRECT_TO",
    "status_code": "REDIRECT_TO_STATUS_CODE",
}
REDIRECT_MAX_NAME_LENGTH = 256


class DatabaseRedirectsMixin(DatabaseMixinBase):
    """Redirect resource CRUD, service assignment and conflict detection."""

    @staticmethod
    def _flag_redirect_config_changed(session) -> None:
        """Signal the scheduler that the rendered redirect configuration is out of date.

        Set inside the mutating method's own session so the flag and the change commit
        together. Unlike certificates this needs no Metadata column: the scheduler already
        watches per-plugin ``config_changed`` (plugins_config_changed), and a redirect only
        ever affects generated NGINX config.
        """
        session.execute(update(Plugins).where(Plugins.id == "redirect").values(config_changed=True, last_config_change=datetime.now().astimezone()))

    def _validate_redirect_fields(self, session, values: Dict[str, Any]) -> str:
        """Validate the rule fields against the redirect plugin's own regexes.

        A missing Settings row (plugin not registered yet, e.g. a bare test database) skips
        the check rather than rejecting the write: the plugin schema is the authority when it
        is there, and its absence is not the caller's fault.
        """
        for field, setting_id in REDIRECT_FIELD_SETTINGS.items():
            if field not in values:
                continue
            value = values[field]
            regex = session.scalars(select(Settings.regex).where(Settings.id == setting_id).limit(1)).first()
            if not regex:
                continue
            try:
                if not re_compile(regex).match(value):
                    return f"Invalid value for {setting_id}: {value!r}"
            except re_error:  # a malformed schema regex must not make every write fail
                self.logger.debug(f"Could not compile the regex of {setting_id}")
        if "to_url" in values and not values["to_url"]:
            # REDIRECT_TO's regex accepts the empty string (it is how an inline rule is
            # disabled), but an empty target makes a *named* rule meaningless: it would
            # attach to services and render nothing.
            return "Redirect target is required"
        return ""

    def _inline_redirect_paths(self, session, service_id: str) -> Set[str]:
        """Source paths already claimed by the service's inline ``REDIRECT_*`` settings.

        Only suffixes with a non-empty ``REDIRECT_TO`` count — that is exactly the condition
        the redirect template renders on, so a disabled inline rule never blocks a resource.
        Service values shadow global ones, matching the multisite inheritance the generator
        applies.
        """
        by_suffix: Dict[int, Dict[str, str]] = {}
        for scope in (
            select(Global_values.setting_id, Global_values.value, Global_values.suffix).where(
                Global_values.setting_id.in_(("REDIRECT_FROM", "REDIRECT_TO"))
            ),
            select(Services_settings.setting_id, Services_settings.value, Services_settings.suffix).where(
                Services_settings.service_id == service_id, Services_settings.setting_id.in_(("REDIRECT_FROM", "REDIRECT_TO"))
            ),
        ):
            for row in session.execute(scope):
                by_suffix.setdefault(row.suffix or 0, {})[row.setting_id] = row.value or ""

        paths: Set[str] = set()
        for values in by_suffix.values():
            if values.get("REDIRECT_TO"):
                paths.add(values.get("REDIRECT_FROM") or "/")
        return paths

    def _redirect_conflict(self, session, resource_id: str, from_path: str, service_ids: List[str]) -> str:
        """Return an actionable error when ``from_path`` is already served on a service.

        Two rules on the same source path make the winner depend on NGINX ``location``
        ordering, which the operator never chose. Refusing the mutation keeps that ambiguity
        out of the database instead of resolving it silently at render time.
        """
        if not service_ids:
            return ""
        rows = session.execute(
            select(ResourceAttachments.service_id, Resources.name, Redirects.from_path)
            .join(Resources, Resources.id == ResourceAttachments.resource_id)
            .join(Redirects, Redirects.resource_id == Resources.id)
            .where(ResourceAttachments.service_id.in_(service_ids), ResourceAttachments.resource_id != resource_id)
        ).all()
        for row in rows:
            if row.from_path == from_path:
                return f"Service {row.service_id} already has the redirect {row.name} on path {from_path}"
        for service_id in service_ids:
            if from_path in self._inline_redirect_paths(session, service_id):
                return f"Service {service_id} already has an inline redirect on path {from_path}"
        return ""

    @staticmethod
    def _attached_service_ids(session, resource_id: str) -> List[str]:
        return list(session.scalars(select(ResourceAttachments.service_id).where(ResourceAttachments.resource_id == resource_id)).all())

    def _redirect_attachments(self, session, resource_ids: List[str]) -> Dict[str, List[str]]:
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
    def _redirect_dict(resource, redirect, services: List[str]) -> dict:
        return {
            "id": resource.id,
            "name": resource.name,
            "description": resource.description or "",
            "from_path": redirect.from_path,
            "to_url": redirect.to_url,
            "status_code": redirect.status_code,
            "append_request_uri": redirect.append_request_uri,
            "services": services,
            "creation_date": resource.creation_date.isoformat(),
            "last_update": resource.last_update.isoformat(),
        }

    def get_redirects(self, *, search: str = "", service_id: str = "", offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        with self._db_session() as session:
            query = select(Resources, Redirects).join(Redirects, Redirects.resource_id == Resources.id).order_by(Resources.name)
            if search:
                pattern = f"%{search.strip()}%"
                query = query.where(or_(Resources.name.ilike(pattern), Redirects.from_path.ilike(pattern), Redirects.to_url.ilike(pattern)))
            rows = list(session.execute(query))
            attachments = self._redirect_attachments(session, [resource.id for resource, _ in rows])
            items = [self._redirect_dict(resource, redirect, attachments[resource.id]) for resource, redirect in rows]

        if service_id:
            items = [item for item in items if service_id in item["services"]]
        total = len(items)
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return {"items": items[offset : offset + limit], "total": total, "offset": offset, "limit": limit}  # noqa: E203

    def get_redirect_details(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self._db_session() as session:
            row = session.execute(
                select(Resources, Redirects).join(Redirects, Redirects.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return None
            return self._redirect_dict(row[0], row[1], self._redirect_attachments(session, [resource_id])[resource_id])

    @staticmethod
    def _service_redirects(session) -> Dict[str, List[Dict[str, Any]]]:
        """Session-taking core of :meth:`get_service_redirects`.

        Separate so a caller already holding a session — ``save_config`` validating an
        incoming inline rule — reuses it instead of nesting a second one.
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in session.execute(
            select(
                ResourceAttachments.service_id,
                Resources.name,
                Redirects.from_path,
                Redirects.to_url,
                Redirects.status_code,
                Redirects.append_request_uri,
            )
            .join(Resources, Resources.id == ResourceAttachments.resource_id)
            .join(Redirects, Redirects.resource_id == Resources.id)
            .order_by(ResourceAttachments.creation_date, Resources.name)
        ):
            result.setdefault(row.service_id, []).append(
                {
                    "name": row.name,
                    "from_path": row.from_path,
                    "to_url": row.to_url,
                    "status_code": row.status_code,
                    "append_request_uri": row.append_request_uri,
                }
            )
        return result

    def get_service_redirects(self) -> Dict[str, List[Dict[str, Any]]]:
        """Every attached rule, keyed by service id, in the order the resolver must inject them.

        Ordered by attachment date then resource name so the suffix a rule receives is stable
        across renders: an unstable order would rewrite ``location`` blocks — and so the
        rendered config hash — on every generation.
        """
        with self._db_session() as session:
            return self._service_redirects(session)

    def create_redirect(
        self,
        *,
        name: str,
        to_url: str,
        from_path: str = "/",
        status_code: str = "301",
        append_request_uri: bool = False,
        description: str = "",
    ) -> Tuple[str, str]:
        """Create a redirect resource. Returns ``(resource_id, error)``."""
        with self._db_session() as session:
            if self.readonly:
                return "", "The database is read-only, the changes will not be saved"

            normalized = name.strip()
            if not normalized:
                return "", "Redirect name is required"
            if len(normalized) > REDIRECT_MAX_NAME_LENGTH:
                return "", f"Redirect names cannot exceed {REDIRECT_MAX_NAME_LENGTH} characters"
            if session.execute(select(Resources.id).where(Resources.type == "redirect", Resources.name == normalized).limit(1)).first():
                return "", f"Redirect name {normalized} already exists"

            values = {"from_path": from_path.strip() or "/", "to_url": to_url.strip(), "status_code": str(status_code).strip()}
            if error := self._validate_redirect_fields(session, values):
                return "", error

            resource_id = str(uuid4())
            now = datetime.now(timezone.utc)
            session.add(Resources(id=resource_id, type="redirect", name=normalized, description=description, creation_date=now, last_update=now))
            session.add(Redirects(resource_id=resource_id, append_request_uri=bool(append_request_uri), **values))
            try:
                # No config_changed flag: a resource attached to nothing renders nothing, so
                # creation alone must not trigger a generation and a reload.
                session.commit()
            except BaseException as exc:
                return "", f"An error occurred while creating redirect: {exc}"
        return resource_id, ""

    def update_redirect(
        self,
        resource_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        from_path: Optional[str] = None,
        to_url: Optional[str] = None,
        status_code: Optional[str] = None,
        append_request_uri: Optional[bool] = None,
    ) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            row = session.execute(
                select(Resources, Redirects).join(Redirects, Redirects.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return "Redirect not found"
            resource, redirect = row

            if name is not None:
                normalized = name.strip()
                if not normalized:
                    return "Redirect name is required"
                if len(normalized) > REDIRECT_MAX_NAME_LENGTH:
                    return f"Redirect names cannot exceed {REDIRECT_MAX_NAME_LENGTH} characters"
                duplicate = session.execute(
                    select(Resources.id).where(Resources.type == "redirect", Resources.name == normalized, Resources.id != resource_id).limit(1)
                ).first()
                if duplicate:
                    return f"Redirect name {normalized} already exists"
                resource.name = normalized
            if description is not None:
                resource.description = description

            values = {}
            if from_path is not None:
                values["from_path"] = from_path.strip() or "/"
            if to_url is not None:
                values["to_url"] = to_url.strip()
            if status_code is not None:
                values["status_code"] = str(status_code).strip()
            if error := self._validate_redirect_fields(session, values):
                return error

            attached = self._attached_service_ids(session, resource_id)
            if "from_path" in values and values["from_path"] != redirect.from_path:
                # The rule is shared: moving its source path must not collide on any service
                # it is already attached to.
                if error := self._redirect_conflict(session, resource_id, values["from_path"], attached):
                    return error
            for field, value in values.items():
                setattr(redirect, field, value)
            if append_request_uri is not None:
                redirect.append_request_uri = bool(append_request_uri)

            resource.last_update = datetime.now(timezone.utc)
            try:
                if attached and (values or append_request_uri is not None):
                    self._flag_redirect_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while updating redirect: {exc}"
        return ""

    def delete_redirect(self, resource_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            resource = session.get(Resources, resource_id)
            if resource is None or resource.type != "redirect":
                return "Redirect not found"
            if session.execute(select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id).limit(1)).first():
                return "Redirect is attached to a service"
            session.delete(resource)
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while deleting redirect: {exc}"
        return ""

    def attach_redirect(self, resource_id: str, service_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            redirect = session.get(Redirects, resource_id)
            if redirect is None:
                return "Redirect not found"
            service = session.execute(select(Services).where(Services.id == service_id).with_for_update()).scalar_one_or_none()
            if service is None:
                return "Service not found"
            if session.execute(
                select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id).limit(1)
            ).first():
                return ""  # already attached: idempotent, and nothing changed to signal
            if error := self._redirect_conflict(session, resource_id, redirect.from_path, [service_id]):
                return error
            # is_primary stays False: it disambiguates the single certificate NGINX serves per
            # SNI, whereas every attached redirect renders.
            session.add(ResourceAttachments(resource_id=resource_id, service_id=service_id, is_primary=False, creation_date=datetime.now(timezone.utc)))
            try:
                self._flag_redirect_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while attaching redirect: {exc}"
        return ""

    def detach_redirect(self, resource_id: str, service_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            result = session.execute(
                delete(ResourceAttachments).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id),
                execution_options={"synchronize_session": False},
            )
            if not result.rowcount:
                return "Redirect attachment not found"
            try:
                self._flag_redirect_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while detaching redirect: {exc}"
        return ""
