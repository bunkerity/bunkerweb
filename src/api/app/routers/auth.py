from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
from biscuit_auth import BiscuitBuilder, PrivateKey

from common_utils import get_version  # type: ignore
from ..utils import LOGGER

from ..utils import BISCUIT_PRIVATE_KEY_FILE, check_password, get_api_db
from ..config import api_config
from ..auth.common import get_auth_header


router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBasic(auto_error=False)
# Use shared logger instance from utils


@router.post("")
async def login(request: Request, credentials: HTTPBasicCredentials | None = Depends(security)) -> JSONResponse:
    """Authenticate and return a Biscuit token.

    Accepted credential sources (in order):
    - Authorization: Basic <base64(username:password)>
    - Authorization: Bearer <API_TOKEN> (admin override)
    - Form body: username=<u>&password=<p>
    - JSON body: {"username": "...", "password": "..."}
    """

    async def _from_form() -> Optional[Tuple[str, str]]:
        with suppress(Exception):
            form = await request.form()
            u = form.get("username")
            p = form.get("password")
            if u and p:
                return str(u), str(p)
        return None

    async def _from_json() -> Optional[Tuple[str, str]]:
        with suppress(Exception):
            data = await request.json()
            if isinstance(data, dict):
                u = data.get("username")
                p = data.get("password")
                if u and p:
                    return str(u), str(p)
        return None

    authz = get_auth_header(request)
    creds = None
    if credentials is not None:
        # Use FastAPI's HTTPBasic to get username/password
        creds = (credentials.username or "", credentials.password or "")
    is_admin_override = False
    if not creds and authz.lower().startswith("bearer ") and api_config.API_TOKEN:
        token_val = authz.split(" ", 1)[1].strip()
        if token_val and token_val == api_config.API_TOKEN:
            is_admin_override = True

    if not creds and not is_admin_override:
        creds = await _from_form() or await _from_json()
    if not creds and not is_admin_override:
        raise HTTPException(status_code=401, detail="Missing or invalid credentials")

    username: Optional[str] = None
    password: Optional[str] = None
    if creds:
        username, password = creds

    db = get_api_db(log=False)
    if is_admin_override:
        user = db.get_api_user(as_dict=True) or {"username": "admin", "admin": True}
        is_admin = True
    else:
        user = db.get_api_user(username=username or "", as_dict=True)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        stored_hash = user.get("password") or b""
        if not isinstance(stored_hash, (bytes, bytearray)):
            stored_hash = str(stored_hash or "").encode("utf-8")
        if not password or not check_password(password, stored_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        is_admin = bool(user.get("admin"))

    perms: set[str] = set()
    is_admin = bool(user.get("admin"))
    fine_grained: list[tuple[str, str, str]] = []
    if is_admin:
        perms.update(["read", "write"])
    else:
        try:
            rows = db.get_api_permissions(username=username)  # type: ignore
        except Exception:
            rows = []
        for row in rows or []:
            name = getattr(row, "permission", "") or ""
            lname = name.lower()
            if "read" in lname:
                perms.add("read")
            if any(x in lname for x in ("create", "update", "delete", "execute", "run", "convert", "export")):
                perms.add("write")
            rtype = getattr(row, "resource_type", "") or ""
            rid = getattr(row, "resource_id", None) or "*"
            fine_grained.append((str(rtype), str(rid), str(name)))

    try:
        priv_hex = BISCUIT_PRIVATE_KEY_FILE.read_text(encoding="utf-8").strip()
        if not priv_hex:
            raise RuntimeError("Biscuit private key not found")
        private_key = PrivateKey.from_hex(priv_hex)
    except Exception as e:
        LOGGER.error(f"/login: failed to load Biscuit private key: {e}")
        raise HTTPException(status_code=500, detail="Authentication service unavailable")

    client_ip = request.client.host if request.client else "0.0.0.0"
    host = request.headers.get("host", "bwapi")
    builder = BiscuitBuilder(
        f"""
        user("{(user.get('username') if isinstance(user, dict) else username) or 'user'}");
        time({datetime.now(timezone.utc).isoformat()});
        client_ip("{client_ip}");
        domain("{host}");
        version("{get_version()}");
        """
    )

    # API has no role logic; encode read/write under a fixed role name.
    role_name = "api_user"
    if "read" in perms and "write" in perms:
        builder.add_code(f'role("{role_name}", ["read", "write"]);')
    elif "read" in perms:
        builder.add_code(f'role("{role_name}", ["read"]);')
    else:
        raise HTTPException(status_code=403, detail="No permissions assigned to user")

    # Embed fine-grained permissions as facts
    def _esc(val: str) -> str:
        return val.replace("\\", "\\\\").replace('"', '\\"')

    if is_admin:
        builder.add_code("admin(true);")
    else:
        for rtype, rid, pname in fine_grained:
            builder.add_code(f'api_perm("{_esc(rtype)}", "{_esc(rid)}", "{_esc(pname)}");')

    token = builder.build(private_key)
    return JSONResponse(status_code=200, content={"token": token.to_base64()})
