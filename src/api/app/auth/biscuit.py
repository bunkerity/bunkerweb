from contextlib import suppress
from ipaddress import ip_address
from traceback import format_exc
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request
from biscuit_auth import Authorizer, Biscuit, BiscuitValidationError, Check, Policy, PublicKey, AuthorizationError, Fact

from common_utils import get_version  # type: ignore

from ..config import api_config
from ..utils import BISCUIT_PUBLIC_KEY_FILE
from .common import get_auth_header, parse_bearer_token


OPERATION_BY_METHOD = {
    "GET": "read",
    "OPTIONS": "read",
    "POST": "write",
    "PUT": "write",
    "PATCH": "write",
    "DELETE": "write",
}

# Default fine-grained permission verb mapping by method
PERM_VERB_BY_METHOD = {
    "GET": "read",
    "OPTIONS": "read",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def _resolve_bans(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve bans endpoints to fine-grained permissions.

    Supported endpoints:
    - GET    /bans            -> ban_read
    - POST   /bans            -> ban_created
    - POST   /bans/ban        -> ban_created
    - DELETE /bans            -> ban_delete
    - POST   /bans/unban      -> ban_delete
    For any other path under /bans, fallback to verb-based mapping.
    """
    rtype = "bans"
    p = path_normalized
    if p == "/bans":
        if method_u == "GET":
            return rtype, "ban_read"
        if method_u == "POST":
            return rtype, "ban_created"
        if method_u == "DELETE":
            return rtype, "ban_delete"
    elif p == "/bans/ban" and method_u == "POST":
        return rtype, "ban_created"
    elif p == "/bans/unban" and method_u == "POST":
        return rtype, "ban_delete"

    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "ban_read"
    if verb == "update":
        return rtype, "ban_update"
    if verb == "delete":
        return rtype, "ban_delete"
    if verb == "create":
        return rtype, "ban_created"
    return rtype, None


def _resolve_instances(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve instances endpoints to fine-grained permissions.

    Supported endpoints:
    - GET    /instances/health | /instances/ping -> instances_read
    - POST   /instances/reload | legacy /reload  -> instances_execute
    - POST   /instances/stop   | legacy /stop    -> instances_execute
    Fallback: instances_<verb> based on method.
    """
    rtype = "instances"
    p = path_normalized
    parts = [seg for seg in p.split("/") if seg]
    # Read actions
    if method_u in {"GET", "OPTIONS"}:
        if p in {"/instances/health", "/instances/ping"}:
            return rtype, "instances_read"
        # Support per-instance ping: /instances/{hostname}/ping
        if len(parts) == 3 and parts[0] == "instances" and parts[2] == "ping":
            return rtype, "instances_read"
    # Execute actions
    if method_u == "POST":
        if p in {"/instances/reload", "/reload", "/instances/stop", "/stop"}:
            return rtype, "instances_execute"
        # Support per-instance reload/stop: /instances/{hostname}/reload|stop
        if len(parts) == 3 and parts[0] == "instances" and parts[2] in {"reload", "stop"}:
            return rtype, "instances_execute"
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb:
        return rtype, f"instances_{verb}"
    return rtype, None


def _resolve_global_config(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve global_config endpoints to fine-grained permissions.

    Supported endpoints:
    - GET              /global_config       -> global_config_read
    - POST|PUT|PATCH   /global_config       -> global_config_update
    Also accepts hyphenated path prefix (global-config) but canonicalizes rtype to global_config.
    """
    rtype = "global_config"
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "global_config_read"
    if verb in {"create", "update"}:
        return rtype, "global_config_update"
    # For DELETE or other methods, no fine-grained permission mapping
    return rtype, None


def _resolve_services(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve services endpoints to fine-grained permissions.

    Permissions are named with singular prefix (service_*), resource_type is plural "services".
    Special endpoints:
    - POST   /services/convert -> service_convert
    - GET    /services/export  -> service_export
    CRUD:
    - GET    /services or /services/{id} -> service_read
    - POST   /services                   -> service_create
    - PUT|PATCH /services/{id}           -> service_update
    - DELETE /services/{id}              -> service_delete
    """
    rtype = "services"
    p = path_normalized
    parts = [seg for seg in p.split("/") if seg]

    # Special actions
    if p == "/services/convert" and method_u == "POST":
        return rtype, "service_convert"
    if p == "/services/export" and method_u in {"GET", "OPTIONS"}:
        return rtype, "service_export"

    # Read
    if method_u in {"GET", "OPTIONS"}:
        if p == "/services" or (len(parts) == 2 and parts[0] == "services"):
            return rtype, "service_read"
    # Create
    if method_u == "POST" and p == "/services":
        return rtype, "service_create"
    # Update
    if method_u in {"PUT", "PATCH"} and len(parts) == 2 and parts[0] == "services":
        return rtype, "service_update"
    # Delete
    if method_u == "DELETE" and len(parts) == 2 and parts[0] == "services":
        return rtype, "service_delete"

    # Fallback by verb if under services
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "service_read"
    if verb == "create":
        return rtype, "service_create"
    if verb == "update":
        return rtype, "service_update"
    if verb == "delete":
        return rtype, "service_delete"
    return rtype, None


def _resolve_configs(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve configs endpoints to fine-grained permissions (singular names).

    Maps to: config_read, config_create, config_update, config_delete
    Examples:
    - GET    /configs or /configs/{...}                 -> config_read
    - POST   /configs or /configs/upload                -> config_create
    - PUT|PATCH /configs/{service}/{type}/{name}[... ]  -> config_update
    - DELETE /configs[...]                              -> config_delete
    """
    rtype = "configs"
    p = path_normalized
    parts = [seg for seg in p.split("/") if seg]

    # Read
    if method_u in {"GET", "OPTIONS"}:
        if p == "/configs":
            return rtype, "configs_read"
        if len(parts) >= 2 and parts[0] == "configs":
            return rtype, "config_read"
    # Create
    if method_u == "POST" and p in ("/configs", "/configs/upload"):
        return rtype, "config_create"
    # Update
    if method_u in {"PUT", "PATCH"} and len(parts) >= 2 and parts[0] == "configs":
        return rtype, "config_update"
    # Delete
    if method_u == "DELETE" and parts and parts[0] == "configs":
        return rtype, "config_delete"

    # Fallback by verb
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "config_read"
    if verb == "create":
        return rtype, "config_create"
    if verb == "update":
        return rtype, "config_update"
    if verb == "delete":
        return rtype, "config_delete"
    return rtype, None


def _resolve_plugins(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve plugins endpoints to fine-grained permissions (singular names).

    Maps to: plugin_read, plugin_create, plugin_delete
    Examples:
    - GET    /plugins or /plugins/{id}     -> plugin_read
    - POST   /plugins/upload               -> plugin_create
    - DELETE /plugins/{id}                 -> plugin_delete
    """
    rtype = "plugins"
    p = path_normalized
    parts = [seg for seg in p.split("/") if seg]

    if method_u in {"GET", "OPTIONS"}:
        if p == "/plugins" or (len(parts) == 2 and parts[0] == "plugins"):
            return rtype, "plugin_read"
    if method_u == "POST" and p == "/plugins/upload":
        return rtype, "plugin_create"
    if method_u == "DELETE" and len(parts) == 2 and parts[0] == "plugins":
        return rtype, "plugin_delete"

    # Fallback by verb
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "plugin_read"
    if verb == "create":
        return rtype, "plugin_create"
    if verb == "update":
        # No explicit update endpoint yet; treat as create for permission purposes
        return rtype, "plugin_create"
    if verb == "delete":
        return rtype, "plugin_delete"
    return rtype, None


def _resolve_cache(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve cache endpoints to fine-grained permissions.

    Supported endpoints (current router):
    - GET    /cache                                  -> cache_read
    - GET    /cache/{service}/{plugin}/{job}/{file}  -> cache_read
    - DELETE /cache                                  -> cache_delete
    - DELETE /cache/{service}/{plugin}/{job}/{file}  -> cache_delete

    For any other method, fall back to coarse role-based auth.
    """
    rtype = "cache"
    if method_u in {"GET", "OPTIONS"}:
        return rtype, "cache_read"
    if method_u == "DELETE":
        return rtype, "cache_delete"
    return rtype, None


def _resolve_jobs(path_normalized: str, method_u: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve jobs endpoints to fine-grained permissions.

    - GET    /jobs           -> job_read
    - GET    /jobs/errors    -> job_read
    - POST   /jobs/run       -> job_run
    """
    rtype = "jobs"
    p = path_normalized
    if method_u in {"GET", "OPTIONS"}:
        if p in {"/jobs", "/jobs/errors"}:
            return rtype, "job_read"
    if method_u == "POST" and p == "/jobs/run":
        return rtype, "job_run"

    # Fallback by verb
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if verb == "read":
        return rtype, "job_read"
    return rtype, None


def _resolve_resource_and_perm(path: str, method: str) -> tuple[Optional[str], Optional[str]]:
    """Derive resource_type and required permission name from request path and method.

    Rules:
    - Category (resource_type) is the first path segment ("/x/..." -> x).
    - Bans:
        - GET /bans -> ban_read
        - POST /ban -> ban_created
        - POST /unban -> ban_delete
        - Else map by method: ban_update/ban_delete/ban_read/ban_created
    - Instances:
        - POST /reload or /stop -> instances_execute
        - Else instances_<verb>
    - Generic fallback:
        - {resource_type}_{verb}
    Returns (resource_type, permission) or (None, None) if not applicable.
    """
    # Normalize and split path (ignore trailing slash)
    if not path.startswith("/"):
        path = "/" + path
    p = path.rstrip("/") or "/"
    parts = [seg for seg in p.split("/") if seg]
    if not parts:
        return None, None

    first = parts[0].lower()
    method_u = method.upper()

    # Bans category
    if first == "bans" or p.startswith("/bans"):
        return _resolve_bans(p, method_u)

    # Instances special cases
    if first in {"instances", "reload", "stop"}:
        return _resolve_instances(p, method_u)
    # Global config special cases (canonicalize hyphenated version)
    if first in {"global_config", "global-config"}:
        return _resolve_global_config(p, method_u)
    # Services special cases
    if first == "services":
        return _resolve_services(p, method_u)
    # Configs special cases
    if first == "configs":
        return _resolve_configs(p, method_u)
    # Plugins special cases
    if first == "plugins":
        return _resolve_plugins(p, method_u)
    # Jobs special cases
    if first == "jobs":
        return _resolve_jobs(p, method_u)
    # Cache special cases
    if first == "cache":
        return _resolve_cache(p, method_u)

    # Generic mapping based on first segment
    rtype = first
    verb = PERM_VERB_BY_METHOD.get(method_u)
    if not verb:
        return rtype, None
    return rtype, f"{rtype}_{verb}"


def _extract_resource_id(path: str, rtype: Optional[str]) -> Optional[str]:
    """Extract a resource identifier from the path when possible.

    Convention: /<rtype>/<id>/... -> id
    For action-only routes like /reload, /stop, /ban, /unban, returns None.
    """
    if not rtype:
        return None
    if not path.startswith("/"):
        path = "/" + path
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    # Skip known action-like endpoints without IDs
    if parts[0] in {"reload", "stop", "ban", "unban", "bans", "global_config", "global-config"}:
        return None
    # Skip services action endpoints when extracting ID
    if parts[0] == "services" and len(parts) >= 2 and parts[1] in {"convert", "export"}:
        return None
    # Skip upload pseudo-id segments for configs/plugins
    if parts[0] in {"configs", "plugins"} and len(parts) >= 2 and parts[1] == "upload":
        return None
    # Skip jobs pseudo-action segments
    if parts[0] == "jobs" and len(parts) >= 2 and parts[1] in {"run", "errors"}:
        return None
    # For instances category, skip action subpaths like /instances/ping, /instances/reload, /instances/stop
    if parts[0] == "instances" and len(parts) >= 2 and parts[1] in {"ping", "reload", "stop"}:
        return None
    # Second segment is considered the resource_id if present
    if len(parts) >= 2:
        return parts[1]
    return None


class BiscuitGuard:
    def __init__(self) -> None:
        from ..utils import LOGGER  # local import to avoid cycles

        self._logger = LOGGER
        self._public_key: Optional[PublicKey] = None
        self._load_public_key()

    def _load_public_key(self) -> None:
        try:
            hex_key = BISCUIT_PUBLIC_KEY_FILE.read_text(encoding="utf-8").strip()
            if not hex_key:
                raise ValueError("Biscuit public key file is empty")
            self._public_key = PublicKey.from_hex(hex_key)
            self._logger.debug("Biscuit public key loaded successfully")
        except Exception as e:
            with suppress(Exception):
                self._logger.debug(f"Failed to load Biscuit public key: {e}")
            raise RuntimeError(f"Failed to load Biscuit public key: {e}")

    def __call__(self, request: Request) -> None:
        # Skip auth for health, login, and OpenAPI/docs endpoints
        # Use scope["path"] to get the path without root_path prefix (handles proxy/gateway scenarios)
        path = request.scope.get("path", request.url.path)
        self._logger.debug(f"Biscuit start: {request.method} {path} from {request.client.host if request.client else 'unknown'}")
        openapi_match = api_config.openapi_url and path == api_config.openapi_url
        docs_match = api_config.docs_url and path.startswith(api_config.docs_url)
        redoc_match = api_config.redoc_url and path.startswith(api_config.redoc_url)
        if path in ("/health", "/ping") or bool(openapi_match) or bool(docs_match) or path.startswith("/auth") or bool(redoc_match):
            self._logger.debug(f"Biscuit skip for path: {path}")
            return

        authz = get_auth_header(request)
        token_str = parse_bearer_token(authz)
        if not token_str:
            self._logger.debug("Biscuit missing bearer token")
            raise HTTPException(status_code=401, detail="Unauthorized")
        try:
            assert self._public_key is not None
            token = Biscuit.from_base64(token_str, self._public_key)
            self._logger.debug("Biscuit token parsed and verified against public key")
        except BiscuitValidationError:
            self._logger.debug(f"Biscuit token validation error:\n{format_exc()}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        except Exception:
            self._logger.debug(f"Biscuit token parsing failed with unexpected error:\n{format_exc()}")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Phase 1: freshness and IP binding
        try:
            az = Authorizer()
            az.add_token(token)
            az.add_check(Check(f'check if version("{get_version()}")'))
            # Enforce token issuance time not older than configured TTL
            try:
                ttl_s = int(api_config.biscuit_ttl_seconds)
            except Exception:
                ttl_s = 0
            if ttl_s > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_s)
                # Token contains a typed datetime literal via time(<iso8601>)
                az.add_check(Check(f"check if time($t), $t >= {cutoff.isoformat()}"))
                self._logger.debug(f"Biscuit phase1: enforce TTL={ttl_s}s (cutoff={cutoff.isoformat()})")

            client_ip = request.client.host if request.client else "0.0.0.0"
            if api_config.check_private_ip or not ip_address(client_ip).is_private:
                az.add_check(Check(f'check if client_ip("{client_ip}")'))
                self._logger.debug(f"Biscuit phase1: enforce client_ip={client_ip} (check_private_ip={api_config.check_private_ip})")
            else:
                self._logger.debug(f"Biscuit phase1: skip client_ip check for private IP {client_ip}")

            az.add_policy(Policy("allow if true"))
            self._logger.debug("Biscuit phase1: authorizing freshness/IP checks")
            az.authorize()
            self._logger.debug("Biscuit phase1: authorization success")
        except AuthorizationError:
            self._logger.debug(f"Biscuit phase1: authorization failed (AuthorizationError):\n{format_exc()}")
            raise HTTPException(status_code=401, detail="Unauthorized")
        except Exception:
            self._logger.debug(f"Biscuit phase1: authorization failed (unexpected error):\n{format_exc()}")
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Phase 2: route authorization (coarse and fine-grained)
        try:
            az = Authorizer()
            az.add_token(token)

            # Always add operation fact for observability
            operation = OPERATION_BY_METHOD.get(request.method.upper(), "read")
            az.add_fact(Fact(f'operation("{operation}")'))
            self._logger.debug(f"Biscuit phase2: operation={operation}")

            # Derive fine-grained context
            rtype, req_perm = _resolve_resource_and_perm(path, request.method)
            if rtype and req_perm:
                az.add_fact(Fact(f'resource("{path}")'))
                az.add_fact(Fact(f'resource_type("{rtype}")'))
                az.add_fact(Fact(f'required_perm("{req_perm}")'))
                rid = _extract_resource_id(path, rtype)
                if rid is not None:
                    az.add_fact(Fact(f'resource_id("{rid}")'))
                self._logger.debug(f"Biscuit phase2: rtype={rtype}, required_perm={req_perm}, resource_id={rid if rid is not None else '*none*'}")

                # Enforce fine-grained authorization
                az.add_policy(Policy("allow if admin(true)"))
                # Global grant (resource_id == "*")
                az.add_policy(Policy('allow if api_perm($rt, "*", $perm), required_perm($perm), resource_type($rt)'))
                # Specific resource grant
                az.add_policy(Policy("allow if api_perm($rt, $rid, $perm), required_perm($perm), resource_type($rt), resource_id($rid)"))
            else:
                # Fallback to coarse role-based authorization when no fine-grained mapping exists
                az.add_policy(Policy("allow if role($role, $perms), operation($op), $perms.contains($op)"))
                self._logger.debug("Biscuit phase2: fallback to coarse role-based authorization")

            self._logger.debug("Biscuit phase2: authorizing route access")
            az.authorize()
            self._logger.debug("Biscuit phase2: authorization success")
        except AuthorizationError:
            self._logger.debug(f"Biscuit phase2: authorization failed (AuthorizationError):\n{format_exc()}")
            raise HTTPException(status_code=403, detail="Forbidden")
        except Exception:
            self._logger.debug(f"Biscuit phase2: authorization failed (unexpected error):\n{format_exc()}")
            raise HTTPException(status_code=403, detail="Forbidden")


guard = BiscuitGuard()
