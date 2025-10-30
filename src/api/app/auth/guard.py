from hmac import compare_digest
from time import time
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from ..utils import LOGGER
from ..config import api_config
from .biscuit import guard as biscuit_guard
from ..utils import check_password, get_api_db
from .common import get_auth_header, parse_bearer_token


security = HTTPBasic(auto_error=False)


class BiscuitWithAdminBearer:
    """Authorization dependency:
    - If API_TOKEN is configured and matches Bearer token, allow full access (admin-like).
    - If HTTP Basic auth is provided and matches an admin API user, allow full access.
    - If Authorization is Bearer but doesn't match API_TOKEN (or no API_TOKEN), defer to Biscuit guard for ACL-based authorization.
    - Skips health, ping, and docs.
    """

    def __init__(self) -> None:
        self._logger = LOGGER
        # username -> (is_admin, password_hash_bytes, expires_at)
        self._admin_cache: dict[str, tuple[bool, bytes, float]] = {}
        self._cache_ttl = 30.0  # seconds

    async def __call__(self, request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
        # Skip auth for health, login, and OpenAPI/docs endpoints
        # Strip root_path prefix if configured (handles proxy/gateway scenarios)
        path = request.scope.get("path", request.url.path)
        root_path = api_config.API_ROOT_PATH
        if root_path and path.startswith(root_path):
            path = path[len(root_path) :] or "/"  # noqa: E203
        self._logger.debug(f"Auth start: {request.method} {path} from {request.client.host if request.client else 'unknown'}")
        openapi_match = api_config.openapi_url and path == api_config.openapi_url
        docs_match = api_config.docs_url and path.startswith(api_config.docs_url)
        redoc_match = api_config.redoc_url and path.startswith(api_config.redoc_url)
        if path in ("/health", "/ping") or bool(openapi_match) or bool(docs_match) or bool(redoc_match) or path.startswith("/auth"):
            self._logger.debug(f"Auth skip for path: {path}")
            return

        # Read Authorization header once
        authz = get_auth_header(request)
        scheme = (authz.split(" ", 1)[0].lower() if authz else "").strip(":") or "none"
        self._logger.debug(f"Authorization scheme detected: {scheme}")

        # First path: HTTP Basic for admin users
        if credentials is not None:
            username = credentials.username or ""
            password = credentials.password or ""
            self._logger.debug(f"Basic auth provided for user={username}")

            # Validate against API users and require admin (with cache)
            now = time()
            hit = self._admin_cache.get(username)
            is_admin: bool
            pwd_hash: bytes
            if hit and hit[2] > now:
                is_admin, pwd_hash, _exp = hit
                self._logger.debug(f"Admin cache hit for user={username}, expires_in={int(hit[2]-now)}s")
            else:
                db = get_api_db(log=False)
                user = db.get_api_user(username=username, as_dict=True)
                is_admin = bool(user.get("admin")) if user else False
                raw_hash = (user.get("password") if user else b"") or b""
                if not isinstance(raw_hash, (bytes, bytearray)):
                    try:
                        raw_hash = str(raw_hash or "").encode("utf-8")
                    except Exception:
                        raw_hash = b""
                pwd_hash = bytes(raw_hash)
                # Negative and positive cache
                self._admin_cache[username] = (is_admin, pwd_hash, now + self._cache_ttl)
                self._logger.debug(f"Admin cache {'populate' if user else 'miss'} for user={username}, is_admin={is_admin}")

            if not is_admin:
                self._logger.warning(
                    f"Auth failed (basic user not admin or not found): user={username} {request.method} {path} from {request.client.host if request.client else 'unknown'}"
                )
                raise HTTPException(status_code=401, detail="Unauthorized")
            if not pwd_hash or not check_password(password, pwd_hash):
                self._logger.warning(
                    f"Auth failed (basic password mismatch): user={username} {request.method} {path} from {request.client.host if request.client else 'unknown'}"
                )
                raise HTTPException(status_code=401, detail="Unauthorized")
            self._logger.debug(f"Auth success via Basic admin: user={username}")
            return  # Full access for admin via Basic

        # Second path: API token as admin override (Bearer) or Biscuit
        api_token = api_config.API_TOKEN
        if authz.lower().startswith("bearer "):
            provided = parse_bearer_token(authz) or ""
            if api_token and compare_digest(provided, api_token):
                self._logger.debug("Auth success via admin Bearer token (API_TOKEN)")
                return  # Full access via admin Bearer
            # Not the admin token (or no API_TOKEN set): try Biscuit ACL
            try:
                self._logger.debug("Delegating to Biscuit guard (Bearer)")
                biscuit_guard(request)
                self._logger.debug("Biscuit guard success (Bearer path)")
                return
            except HTTPException as e:
                # Bubble up after logging
                self._logger.warning(
                    f"Auth failed (biscuit {e.status_code}): {request.method} {path} from {request.client.host if request.client else 'unknown'} reason={getattr(e, 'detail', '')}"
                )
                raise

        # Else rely on Biscuit token for ACL (will raise Missing Bearer if none)
        try:
            self._logger.debug("Delegating to Biscuit guard (no Basic/Bearer admin)")
            biscuit_guard(request)
            self._logger.debug("Biscuit guard success (default path)")
        except HTTPException as e:
            # Log Biscuit authorization failures without exposing token
            self._logger.warning(
                f"Auth failed (biscuit {e.status_code}): {request.method} {path} from {request.client.host if request.client else 'unknown'} reason={getattr(e, 'detail', '')}"
            )
            raise


guard = BiscuitWithAdminBearer()
