#!/usr/bin/env python3
"""Reusable HTTP upstream pools: CRUD, service attachment and expansion input."""

from datetime import datetime, timezone
from re import compile as re_compile
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from model import (  # type: ignore
    Plugins,
    ResourceAttachments,
    Resources,
    Services,
    UPSTREAM_METHODS,
    UPSTREAM_PROTOCOLS,
    Upstreams,
    UpstreamServers,
)
from sqlalchemy import delete, or_, select, update

from .common import DatabaseMixinBase
from .locations import LOCATION_SETTINGS, inline_family_paths, location_conflict, service_setting

UPSTREAM_MAX_NAME_LENGTH = 64
# Deliberately narrower than a hostname: with a variable in ``proxy_pass`` NGINX looks the
# address up among the defined upstream groups *before* falling back to the resolver, so a pool
# named like a host (``api.internal``) would hijack every ``proxy_pass http://api.internal`` in
# the configuration. Forbidding dots makes that collision unrepresentable.
UPSTREAM_NAME_RE = re_compile(r"^[a-zA-Z0-9_-]+$")
# ``server`` takes an address, not a URL: host, IPv4, or bracketed IPv6, with an optional port.
UPSTREAM_SERVER_RE = re_compile(r"^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)(:[1-9][0-9]{0,4})?$")
UPSTREAM_FAIL_TIMEOUT_RE = re_compile(r"^[0-9]+(ms|s|m|h|d)?$")
UPSTREAM_MAX_SERVERS = 64


class DatabaseUpstreamsMixin(DatabaseMixinBase):
    """Upstream pool CRUD, service assignment and conflict detection."""

    @staticmethod
    def _flag_upstream_config_changed(session) -> None:
        """Signal the scheduler that the rendered reverse-proxy configuration is out of date.

        The pool renders through the ``reverseproxy`` plugin's own templates, so its per-plugin
        ``config_changed`` flag is the one to raise — the scheduler already watches
        ``plugins_config_changed``. Set inside the mutating method's session so the flag and the
        change commit together.
        """
        session.execute(update(Plugins).where(Plugins.id == "reverseproxy").values(config_changed=True, last_config_change=datetime.now().astimezone()))

    def _validate_upstream_fields(
        self, method: Optional[str], keepalive: Optional[int], servers: Optional[List[Dict[str, Any]]], protocol: Optional[str] = None
    ) -> str:
        """Validate pool settings against what the rendered ``upstream {}`` block accepts.

        Everything here ends up verbatim in an NGINX directive, so a value refused now is a
        failed ``nginx -t`` and a skipped reload later.
        """
        if protocol is not None and protocol not in UPSTREAM_PROTOCOLS:
            return f"Invalid protocol {protocol!r}, expected one of {', '.join(UPSTREAM_PROTOCOLS)}"
        if protocol == "stream" and keepalive:
            # keepalive is an http upstream directive; the stream module has no equivalent.
            return "Keepalive is not supported on a stream upstream"
        if method is not None and method not in UPSTREAM_METHODS:
            return f"Invalid load balancing method {method!r}, expected one of {', '.join(UPSTREAM_METHODS)}"
        if keepalive is not None and keepalive < 1:
            # NGINX rejects ``keepalive 0``; "no keepalive" is expressed by omitting the
            # directive, which is what NULL means here.
            return "Keepalive must be at least 1, or empty to disable it"
        if servers is None:
            return ""
        if not servers:
            return "An upstream needs at least one server"
        if len(servers) > UPSTREAM_MAX_SERVERS:
            return f"An upstream cannot exceed {UPSTREAM_MAX_SERVERS} servers"

        seen: Set[str] = set()
        for server in servers:
            host = str(server.get("host", "")).strip()
            if not host:
                return "Server address is required"
            if not UPSTREAM_SERVER_RE.match(host):
                return f"Invalid server address {host!r}, expected host[:port] without a scheme"
            if host in seen:
                return f"Server {host} is listed twice in the same upstream"
            seen.add(host)

            if "ip_hash" == method and server.get("backup"):
                # NGINX refuses ``backup`` together with ip_hash; catching it here keeps the
                # generated configuration loadable.
                return "The ip_hash method does not support backup servers"

            weight = server.get("weight", 1)
            if not isinstance(weight, int) or weight < 1:
                return f"Invalid weight for {host}: weight must be a positive integer"
            max_fails = server.get("max_fails", 1)
            if not isinstance(max_fails, int) or max_fails < 0:
                return f"Invalid max_fails for {host}: max_fails cannot be negative"
            fail_timeout = str(server.get("fail_timeout", "10s")).strip()
            if not UPSTREAM_FAIL_TIMEOUT_RE.match(fail_timeout):
                return f"Invalid fail_timeout for {host}: {fail_timeout!r}"

        if all(server.get("down") for server in servers):
            return "At least one server must be up"
        if all(server.get("backup") for server in servers):
            return "An upstream needs at least one non-backup server"
        return ""

    def _upstream_conflict(self, session, resource_id: str, protocol: str, match_path: str, service_ids: List[str], name: str = "") -> str:  # noqa: C901
        """Return an actionable error when the target is already taken on a service.

        For an http or gRPC pool the whole location namespace is consulted — redirects
        included — because NGINX refuses two ``location`` blocks with the same URI whichever
        plugin emitted them. A stream pool has no path and is checked against the single
        backend a stream server can have.
        """
        if not service_ids:
            return ""
        subject = f"upstream “{name}”" if name else "this upstream"

        if protocol == "stream":
            # A stream server proxies the whole connection: there is no path to disambiguate
            # two backends with, so a service can only ever have one.
            rows = session.execute(
                select(ResourceAttachments.service_id, Resources.name)
                .join(Resources, Resources.id == ResourceAttachments.resource_id)
                .join(Upstreams, Upstreams.resource_id == Resources.id)
                .where(ResourceAttachments.service_id.in_(service_ids), ResourceAttachments.resource_id != resource_id, Upstreams.protocol == "stream")
            ).all()
            if rows:
                return (
                    f"Cannot attach {subject}: a stream service proxies every connection to a single backend, and "
                    f"{rows[0].service_id} already uses the upstream “{rows[0].name}”. Detach it first."
                )
            for service_id in service_ids:
                # On a stream service REVERSE_PROXY_HOST is *the* backend, not a location, and
                # the pool takes its place — refuse rather than override it silently.
                if inline_family_paths(session, service_id, *LOCATION_SETTINGS["reverse proxy"]):
                    return (
                        f"Cannot attach {subject}: {service_id} already has its own backend in REVERSE_PROXY_HOST. "
                        f"Clear that setting to let the upstream take over."
                    )
            return ""

        return location_conflict(session, resource_id, match_path, service_ids, subject=subject)

    @staticmethod
    def _server_type_conflict(session, service_id: str, protocol: str) -> str:
        """Refuse a pool whose protocol does not match what the service actually serves.

        An http pool on a stream service would put a scheme in a stream ``server`` directive and
        break the whole configuration; a stream pool on an http service would render nothing at
        all. Neither is worth discovering at reload time.
        """
        server_type = service_setting(session, service_id, "SERVER_TYPE", "http")
        wanted = "stream" if protocol == "stream" else "http"
        if server_type != wanted:
            return (
                f"Cannot attach a {protocol} upstream to {service_id}: it is a {server_type} service. "
                f"{protocol} upstreams go on services whose SERVER_TYPE is {wanted}."
            )
        return ""

    @staticmethod
    def _upstream_attachments(session, resource_ids: List[str]) -> Dict[str, List[Dict[str, str]]]:
        attachments: Dict[str, List[Dict[str, str]]] = {resource_id: [] for resource_id in resource_ids}
        if not resource_ids:
            return attachments
        for row in session.execute(
            select(ResourceAttachments.resource_id, ResourceAttachments.service_id, ResourceAttachments.match_path)
            .where(ResourceAttachments.resource_id.in_(resource_ids))
            .order_by(ResourceAttachments.service_id, ResourceAttachments.match_path)
        ):
            attachments[row.resource_id].append({"service_id": row.service_id, "match_path": row.match_path})
        return attachments

    @staticmethod
    def _server_dict(server) -> Dict[str, Any]:
        return {
            "host": server.host,
            "weight": server.weight,
            "max_fails": server.max_fails,
            "fail_timeout": server.fail_timeout,
            "backup": server.backup,
            "down": server.down,
        }

    @staticmethod
    def _upstream_dict(resource, upstream, servers: List[Dict[str, Any]], services: List[Dict[str, str]]) -> dict:
        return {
            "id": resource.id,
            "name": resource.name,
            "description": resource.description or "",
            "protocol": upstream.protocol,
            "backend_ssl": upstream.backend_ssl,
            "method": upstream.method,
            "keepalive": upstream.keepalive,
            "servers": servers,
            "services": services,
            "creation_date": resource.creation_date.isoformat(),
            "last_update": resource.last_update.isoformat(),
        }

    def get_upstreams(self, *, search: str = "", service_id: str = "", offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        with self._db_session() as session:
            query = select(Resources, Upstreams).join(Upstreams, Upstreams.resource_id == Resources.id).order_by(Resources.name)
            if search:
                pattern = f"%{search.strip()}%"
                matching = select(UpstreamServers.resource_id).where(UpstreamServers.host.ilike(pattern))
                query = query.where(or_(Resources.name.ilike(pattern), Resources.description.ilike(pattern), Resources.id.in_(matching)))
            rows = list(session.execute(query))
            resource_ids = [resource.id for resource, _ in rows]
            attachments = self._upstream_attachments(session, resource_ids)
            servers = self._pool_servers(session, resource_ids)
            items = [self._upstream_dict(resource, upstream, servers[resource.id], attachments[resource.id]) for resource, upstream in rows]

        if service_id:
            items = [item for item in items if any(service["service_id"] == service_id for service in item["services"])]
        total = len(items)
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return {"items": items[offset : offset + limit], "total": total, "offset": offset, "limit": limit}  # noqa: E203

    def _pool_servers(self, session, resource_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        servers: Dict[str, List[Dict[str, Any]]] = {resource_id: [] for resource_id in resource_ids}
        if not resource_ids:
            return servers
        for server in session.scalars(
            select(UpstreamServers).where(UpstreamServers.resource_id.in_(resource_ids)).order_by(UpstreamServers.resource_id, UpstreamServers.order)
        ):
            servers[server.resource_id].append(self._server_dict(server))
        return servers

    def get_upstream_details(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self._db_session() as session:
            row = session.execute(
                select(Resources, Upstreams).join(Upstreams, Upstreams.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return None
            return self._upstream_dict(
                row[0], row[1], self._pool_servers(session, [resource_id])[resource_id], self._upstream_attachments(session, [resource_id])[resource_id]
            )

    @staticmethod
    def _service_upstreams(session) -> Dict[str, List[Dict[str, Any]]]:
        """Session-taking core of :meth:`get_service_upstreams`.

        Separate so a caller already holding a session — ``save_config`` validating an incoming
        inline reverse-proxy setting — reuses it instead of nesting a second one.
        """
        rows = list(
            session.execute(
                select(
                    ResourceAttachments.service_id,
                    ResourceAttachments.match_path,
                    Resources.id,
                    Resources.name,
                    Upstreams.protocol,
                    Upstreams.backend_ssl,
                    Upstreams.method,
                    Upstreams.keepalive,
                )
                .join(Resources, Resources.id == ResourceAttachments.resource_id)
                .join(Upstreams, Upstreams.resource_id == Resources.id)
                .order_by(ResourceAttachments.creation_date, Resources.name)
            )
        )
        if not rows:
            return {}

        servers: Dict[str, List[Dict[str, Any]]] = {}
        for server in session.scalars(
            select(UpstreamServers)
            .where(UpstreamServers.resource_id.in_({row.id for row in rows}))
            .order_by(UpstreamServers.resource_id, UpstreamServers.order)
        ):
            servers.setdefault(server.resource_id, []).append(DatabaseUpstreamsMixin._server_dict(server))

        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row.service_id, []).append(
                {
                    "name": row.name,
                    "match_path": row.match_path,
                    "protocol": row.protocol,
                    "backend_ssl": row.backend_ssl,
                    "method": row.method,
                    "keepalive": row.keepalive,
                    "servers": servers.get(row.id, []),
                }
            )
        return result

    def get_service_upstreams(self) -> Dict[str, List[Dict[str, Any]]]:
        """Every attached pool, keyed by service id, in the order the resolver must inject them.

        Ordered by attachment date then pool name so the suffix an attachment receives is stable
        across renders: an unstable order would rewrite ``location`` blocks — and so the rendered
        configuration hash — on every generation.
        """
        with self._db_session() as session:
            return self._service_upstreams(session)

    @staticmethod
    def _replace_servers(session, resource_id: str, servers: List[Dict[str, Any]]) -> None:
        session.execute(delete(UpstreamServers).where(UpstreamServers.resource_id == resource_id), execution_options={"synchronize_session": False})
        for order, server in enumerate(servers):
            session.add(
                UpstreamServers(
                    resource_id=resource_id,
                    host=str(server["host"]).strip(),
                    weight=int(server.get("weight", 1)),
                    max_fails=int(server.get("max_fails", 1)),
                    fail_timeout=str(server.get("fail_timeout", "10s")).strip(),
                    backup=bool(server.get("backup", False)),
                    down=bool(server.get("down", False)),
                    order=order,
                )
            )

    def _validate_upstream_name(self, session, name: str, resource_id: str = "") -> Tuple[str, str]:
        normalized = name.strip()
        if not normalized:
            return "", "Upstream name is required"
        if len(normalized) > UPSTREAM_MAX_NAME_LENGTH:
            return "", f"Upstream names cannot exceed {UPSTREAM_MAX_NAME_LENGTH} characters"
        if not UPSTREAM_NAME_RE.match(normalized):
            return "", "Upstream names may only contain letters, digits, hyphens and underscores"
        query = select(Resources.id).where(Resources.type == "upstream", Resources.name == normalized)
        if resource_id:
            query = query.where(Resources.id != resource_id)
        if session.execute(query.limit(1)).first():
            return "", f"Upstream name {normalized} already exists"
        return normalized, ""

    def create_upstream(
        self,
        *,
        name: str,
        servers: List[Dict[str, Any]],
        protocol: str = "http",
        backend_ssl: bool = False,
        method: str = "round_robin",
        keepalive: Optional[int] = None,
        description: str = "",
    ) -> Tuple[str, str]:
        """Create an upstream pool. Returns ``(resource_id, error)``."""
        with self._db_session() as session:
            if self.readonly:
                return "", "The database is read-only, the changes will not be saved"

            normalized, error = self._validate_upstream_name(session, name)
            if error:
                return "", error
            if error := self._validate_upstream_fields(method, keepalive, servers, protocol):
                return "", error

            resource_id = str(uuid4())
            now = datetime.now(timezone.utc)
            session.add(Resources(id=resource_id, type="upstream", name=normalized, description=description, creation_date=now, last_update=now))
            session.add(Upstreams(resource_id=resource_id, protocol=protocol, backend_ssl=bool(backend_ssl), method=method, keepalive=keepalive))
            self._replace_servers(session, resource_id, servers)
            try:
                # No config_changed flag: a pool attached to nothing renders nothing, so
                # creation alone must not trigger a generation and a reload.
                session.commit()
            except BaseException as exc:
                return "", f"An error occurred while creating upstream: {exc}"
        return resource_id, ""

    def update_upstream(
        self,
        resource_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        protocol: Optional[str] = None,
        backend_ssl: Optional[bool] = None,
        method: Optional[str] = None,
        keepalive: Optional[int] = None,
        clear_keepalive: bool = False,
        servers: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            row = session.execute(
                select(Resources, Upstreams).join(Upstreams, Upstreams.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return "Upstream not found"
            resource, upstream = row

            if name is not None:
                normalized, error = self._validate_upstream_name(session, name, resource_id)
                if error:
                    return error
                resource.name = normalized
            if description is not None:
                resource.description = description

            attached = self._attached_service_ids(session, resource_id)
            if protocol is not None and protocol != upstream.protocol and attached:
                # An attachment means a path (http/grpc) or a whole stream server; switching
                # protocol would reinterpret every one of them at once.
                return "Detach the upstream from every service before changing its protocol"

            # ``backup`` is only rejected with ip_hash, so validate the incoming method against
            # the servers that will actually be stored, not the ones that were.
            effective_method = method if method is not None else upstream.method
            effective_protocol = protocol if protocol is not None else upstream.protocol
            effective_servers = servers if servers is not None else self._pool_servers(session, [resource_id])[resource_id]
            effective_keepalive = None if clear_keepalive else (keepalive if keepalive is not None else upstream.keepalive)
            if error := self._validate_upstream_fields(effective_method, effective_keepalive, effective_servers, effective_protocol):
                return error

            changed = False
            if protocol is not None and protocol != upstream.protocol:
                upstream.protocol = protocol
                changed = True
            if backend_ssl is not None and bool(backend_ssl) != upstream.backend_ssl:
                upstream.backend_ssl = bool(backend_ssl)
                changed = True
            if method is not None and method != upstream.method:
                upstream.method = method
                changed = True
            if clear_keepalive:
                changed = changed or upstream.keepalive is not None
                upstream.keepalive = None
            elif keepalive is not None and keepalive != upstream.keepalive:
                upstream.keepalive = keepalive
                changed = True
            if servers is not None:
                self._replace_servers(session, resource_id, servers)
                changed = True

            resource.last_update = datetime.now(timezone.utc)
            try:
                if changed and session.execute(select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id).limit(1)).first():
                    self._flag_upstream_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while updating upstream: {exc}"
        return ""

    def delete_upstream(self, resource_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            resource = session.get(Resources, resource_id)
            if resource is None or resource.type != "upstream":
                return "Upstream not found"
            if session.execute(select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id).limit(1)).first():
                return "Upstream is attached to a service"
            session.delete(resource)
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while deleting upstream: {exc}"
        return ""

    def attach_upstream(self, resource_id: str, service_id: str, *, match_path: str = "/") -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            upstream = session.get(Upstreams, resource_id)
            if upstream is None:
                return "Upstream not found"
            if upstream.protocol == "stream":
                # A stream server proxies the whole connection, so there is no path to attach
                # on: the empty path is what the shared attachment table stores for it.
                path = ""
            else:
                path = match_path.strip() or "/"
                if not path.startswith("/"):
                    return f"Invalid path {path}: a reverse proxy path must start with /"
            service = session.execute(select(Services).where(Services.id == service_id).with_for_update()).scalar_one_or_none()
            if service is None:
                return "Service not found"
            if error := self._server_type_conflict(session, service_id, upstream.protocol):
                return error
            if session.execute(
                select(ResourceAttachments.id)
                .where(
                    ResourceAttachments.resource_id == resource_id,
                    ResourceAttachments.service_id == service_id,
                    ResourceAttachments.match_path == path,
                )
                .limit(1)
            ).first():
                return ""  # already attached on that path: idempotent, and nothing changed to signal
            name = session.execute(select(Resources.name).where(Resources.id == resource_id).limit(1)).scalar_one_or_none() or ""
            if error := self._upstream_conflict(session, resource_id, upstream.protocol, path, [service_id], name):
                return error
            # is_primary stays False: it disambiguates the single certificate NGINX serves per
            # SNI, whereas every attached pool renders its own location.
            session.add(
                ResourceAttachments(resource_id=resource_id, service_id=service_id, is_primary=False, match_path=path, creation_date=datetime.now(timezone.utc))
            )
            try:
                self._flag_upstream_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while attaching upstream: {exc}"
        return ""

    def detach_upstream(self, resource_id: str, service_id: str, *, match_path: str = "") -> str:
        """Detach a pool from a service. Without ``match_path`` every path is detached."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            query = delete(ResourceAttachments).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id)
            if match_path:
                query = query.where(ResourceAttachments.match_path == match_path)
            result = session.execute(query, execution_options={"synchronize_session": False})
            if not result.rowcount:
                return "Upstream attachment not found"
            try:
                self._flag_upstream_config_changed(session)
                session.commit()
            except BaseException as exc:
                return f"An error occurred while detaching upstream: {exc}"
        return ""
