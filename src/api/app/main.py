from contextlib import suppress
from functools import lru_cache
from io import StringIO
from os import sep
from os.path import join
from re import split
from sys import path as sys_path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from traceback import format_exc
from ipaddress import ip_address, ip_network, IPv4Network, IPv6Network

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from yaml import safe_dump as yaml_dump

from common_utils import get_version  # type: ignore

from .routers.core import router as core_router
from .utils import LOGGER
from .rate_limit import setup_rate_limiter, limiter_dep_dynamic
from .config import api_config

BUNKERWEB_VERSION = get_version()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BunkerWeb API",
        description=description,
        summary="The API used by BunkerWeb to communicate with the database and the instances",
        version=BUNKERWEB_VERSION,
        contact={"name": "BunkerWeb Team", "url": "https://www.bunkerweb.io", "email": "contact@bunkerity.com"},
        license_info={"name": "GNU Affero General Public License v3.0", "url": "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE.md"},
        openapi_tags=tags_metadata,
        docs_url=api_config.docs_url,
        redoc_url=api_config.redoc_url,
        openapi_url=api_config.openapi_url,
        root_path=api_config.API_ROOT_PATH or "",
    )

    # Optional IP whitelist (enabled by default, can be disabled)
    whitelist_networks: list[IPv4Network | IPv6Network] = []
    if api_config.whitelist_enabled:
        raw_whitelist = api_config.API_WHITELIST_IPS.strip()
        if raw_whitelist:
            for tok in split(r"[\s,]+", raw_whitelist):
                if not tok:
                    continue
                try:
                    if "/" in tok:
                        whitelist_networks.append(ip_network(tok, strict=False))
                    else:
                        ipobj = ip_address(tok)
                        cidr = f"{ipobj.exploded}/32" if ipobj.version == 4 else f"{ipobj.exploded}/128"
                        whitelist_networks.append(ip_network(cidr, strict=False))
                except ValueError:
                    LOGGER.error(f"Invalid IP/CIDR in API whitelist: {tok}")
                except Exception:
                    LOGGER.error(f"Error parsing API whitelist entry {tok}: {format_exc()}")
                    continue

    if whitelist_networks:

        @app.middleware("http")
        async def whitelist_middleware(request: Request, call_next):  # pragma: no cover
            cip = request.client.host if request.client else "0.0.0.0"
            ipobj = ip_address(cip)
            for net in whitelist_networks:
                if ipobj in net:
                    return await call_next(request)
            LOGGER.warning(f"Blocking API request from non-whitelisted IP {request.client.host if request.client else 'unknown'}")
            return JSONResponse(status_code=403, content={"status": "error", "message": "forbidden"})

    # Rate limiter (optional, safe if disabled)
    setup_rate_limiter(app)

    # Inject rate limit headers on successful responses when enabled
    @app.middleware("http")
    async def rate_limit_headers_middleware(request: Request, call_next):  # pragma: no cover
        response = await call_next(request)
        limiter = getattr(app.state, "limiter", None)
        if limiter is not None:
            # Only inject when slowapi has computed the current limit
            current = getattr(request.state, "view_rate_limit", None)
            if current is not None:
                limiter._inject_asgi_headers(response.headers, current)
        return response

    # Routers with optional dynamic per-endpoint rate limiting
    app.include_router(core_router, dependencies=[limiter_dep_dynamic()])

    # Error normalization
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        if exc.status_code == 500:
            # Emit full traceback at debug level to aid diagnostics
            with suppress(Exception):
                LOGGER.debug(f"HTTPException 500: {exc}\n{format_exc()}")
        detail = exc.detail if isinstance(exc.detail, str) else "error"
        return JSONResponse(status_code=exc.status_code, content={"status": "error", "message": detail})

    # Log tracebacks for unexpected errors (500)
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        # Emit full traceback at debug level to aid diagnostics
        with suppress(Exception):
            LOGGER.debug(f"Unhandled exception: {exc}\n{format_exc()}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "internal error"})

    @app.get("/openapi.yaml", include_in_schema=False)
    @lru_cache()
    def read_openapi_yaml():
        openapi_json = app.openapi()
        yaml_s = StringIO()
        yaml_dump(openapi_json, yaml_s)
        return Response(yaml_s.getvalue(), media_type="text/yaml")

    return app


description = (
    """# BunkerWeb API

This API is the control plane for BunkerWeb. It manages configuration, instances, plugins, bans, and scheduler artefacts and should remain on a trusted network.

## Feature overview

- Core: `/ping` and `/health` offer lightweight liveness probes.
- Auth: `POST /auth` exchanges Basic credentials or the admin override token for a Biscuit; admin users may also authenticate with HTTP Basic directly.
- Instances: register, list, update, and remove instances or broadcast `/ping`, `/reload`, and `/stop` to all or specific hosts.
- Global settings: `GET`/`PATCH /global_settings` read or update API-owned global settings without touching other sources.
- Services: create, rename, toggle draft/online modes, convert, and delete services while keeping prefixed variables consistent.
- Custom configs: manage HTTP/stream/ModSecurity/CRS snippets via JSON payloads or uploads with `GET`/`POST`/`PATCH`/`DELETE /configs`.
- Bans: aggregate current bans and orchestrate ban/unban operations across instances with flexible bulk payloads.
- Plugins: list and install/remove UI plugins from supported archive formats with checksum validation.
- Cache & jobs: inspect, download, or purge job cache files and trigger scheduler jobs via `/cache` and `/jobs` endpoints.

All responses are normalised; errors return `{ "status": "error", "message": "..." }` with appropriate status codes.

## Access and security

- Authentication flows:
  - Login endpoint: send `Authorization: Basic <base64(username:password)>`, or provide `username`/`password` as form or JSON to `/auth`; it returns a Biscuit token you use as `Authorization: Bearer <token>` for subsequent calls.
  - Admin override: if `API_TOKEN` is set, `Authorization: Bearer <API_TOKEN>` grants full access without Biscuit.
  - Direct Basic admin: protected endpoints also accept HTTP Basic when the user is an admin; no Biscuit is required in that case.
- Biscuit token contents: facts such as `user(<username>)`, `time(<utc-iso>)`, `client_ip(<ip>)`, `domain(<host>)`, `version(<bw-version>)`; a coarse role `role("api_user", ["read"[, "write"]])`; and either `admin(true)` for admins or fine-grained permission facts like `api_perm(<resource_type>, <resource_id|*>, <permission>)` based on DB permissions. Keys are stored at `/var/lib/bunkerweb/.api_biscuit_private_key` (signing) and `/var/lib/bunkerweb/.api_biscuit_public_key` (verification).
- Biscuit checks: verification uses the public key and enforces freshness/IP binding, then authorizes routes by mapping path/method to a required permission (for example, bans and instances have specialised mappings) with wildcard (`*`) or specific resource IDs; the guard falls back to coarse read/write when no fine-grained mapping applies.
- Passwords: API user passwords are stored as bcrypt hashes and validated on login.
- IP allowlist: when enabled, only requests from allowed IPs/CIDRs can reach the API.
- Rate limiting: configurable global and auth-specific limits; headers are injected when enabled.

Example header:

```
Authorization: Bearer <your_token_here>
```

## Configuration

Settings can be provided via `/etc/bunkerweb/api.yml`, `/etc/bunkerweb/api.env`, and `/run/secrets` (environment variables take precedence). Common keys include:

- `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`: documentation and OpenAPI exposure.
- `API_TOKEN`: optional admin Bearer token used at `/auth`.
- `API_WHITELIST_IPS`: space/comma-separated IPs/CIDRs for the allowlist.
- `API_RATE_LIMIT_*`: knobs to enable/shape rate limiting.
- `API_BISCUIT_TTL_SECONDS`: lifetime of Biscuit tokens in seconds (0 disables expiry; default 3600).

"""
    + f"See the [BunkerWeb documentation](https://docs.bunkerweb.io/{BUNKERWEB_VERSION}/api/) for more details."
)  # noqa: E501

tags_metadata = [
    {"name": "core", "description": "Health probes and global utility endpoints"},
    {"name": "auth", "description": "Authentication and Biscuit issuance"},
    {"name": "bans", "description": "Operations related to ban management"},
    {"name": "instances", "description": "Operations related to instance management"},
    {"name": "global_settings", "description": "Operations related to global settings"},
    {"name": "services", "description": "Operations related to service management"},
    {"name": "configs", "description": "Operations related to custom NGINX configs"},
    {"name": "plugins", "description": "Operations related to plugin management"},
    {"name": "cache", "description": "Operations related to job cache files"},
    {"name": "jobs", "description": "Operations related to scheduler jobs"},
]

app = create_app()
