from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/users", tags=["users"])


# ── Schemas ─────────────────────────────────────────────────────────


class CreateUserRequest(BaseModel):
    username: str
    password: str
    roles: List[str] = Field(default_factory=lambda: ["admin"])
    email: Optional[str] = None
    theme: str = "light"
    language: str = "en"
    totp_secret: Optional[str] = None
    totp_recovery_codes: Optional[List[str]] = None
    method: str = "manual"
    admin: bool = False


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    theme: Optional[str] = None
    old_username: Optional[str] = None
    email: Optional[str] = None
    totp_secret: Optional[str] = None
    totp_recovery_codes: Optional[List[str]] = None
    method: Optional[str] = None
    language: Optional[str] = None


class LoginRequest(BaseModel):
    ip: str
    user_agent: str


class RecoveryCodeUseRequest(BaseModel):
    hashed_code: str


class RecoveryCodesRefreshRequest(BaseModel):
    codes: List[str]


class UpdatePreferencesRequest(BaseModel):
    columns: Dict[str, bool]


class AccessRequest(BaseModel):
    session_id: int


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(guard)])
def get_admin_user(auth: bool = False) -> JSONResponse:
    """Get the first admin user. Returns 404 if no admin exists."""
    user = get_db().get_ui_user(as_dict=True)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "message": "No admin user found"})

    if not auth:
        user = {k: v for k, v in user.items() if k not in ("password", "recovery_codes", "totp_secret")}

    # Serialize datetime fields
    for field in ("creation_date", "update_date"):
        if field in user and hasattr(user[field], "isoformat"):
            user[field] = user[field].isoformat()

    # Decode password bytes to str when returning auth data
    if auth and "password" in user and isinstance(user.get("password"), bytes):
        user["password"] = user["password"].decode("utf-8")

    return JSONResponse(status_code=200, content={"status": "success", "user": user})


@router.post("", dependencies=[Depends(guard)])
def create_user(req: CreateUserRequest) -> JSONResponse:
    """Create a new UI user."""
    ret = get_db().create_ui_user(
        username=req.username,
        password=req.password.encode("utf-8"),
        roles=req.roles,
        email=req.email,
        theme=req.theme,
        language=req.language,
        totp_secret=req.totp_secret,
        totp_recovery_codes=req.totp_recovery_codes,
        method=req.method,
        admin=req.admin,
    )
    if ret:
        code = 400 if "already exists" in ret or "read-only" in ret else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=201, content={"status": "success"})


@router.get("/{username}", dependencies=[Depends(guard)])
def get_user(username: str, auth: bool = False) -> JSONResponse:
    """Get a UI user by username. Set auth=True to include password hash."""
    user = get_db().get_ui_user(username=username, as_dict=True)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"User {username} not found"})

    if auth:
        # Return full user data including auth fields
        user_data = dict(user)
        # Decode password bytes to str for JSON serialization
        if "password" in user_data and isinstance(user_data.get("password"), bytes):
            user_data["password"] = user_data["password"].decode("utf-8")
    else:
        # Sanitize sensitive fields
        user_data = {k: v for k, v in user.items() if k not in ("password", "recovery_codes", "totp_secret")}

    if "creation_date" in user_data:
        user_data["creation_date"] = user_data["creation_date"].isoformat()
    if "update_date" in user_data:
        user_data["update_date"] = user_data["update_date"].isoformat()
    return JSONResponse(status_code=200, content={"status": "success", "user": user_data})


@router.patch("/{username}", dependencies=[Depends(guard)])
def update_user(username: str, req: UpdateUserRequest) -> JSONResponse:
    """Update a UI user's profile, password, theme, or TOTP settings."""
    db = get_db()

    user = db.get_ui_user(username=req.old_username or username, as_dict=True)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"User {username} not found"})

    ret = db.update_ui_user(
        username=username,
        password=req.password.encode("utf-8") if req.password else user["password"],
        totp_secret=req.totp_secret if req.totp_secret is not None else user.get("totp_secret"),
        theme=req.theme or user.get("theme", "light"),
        old_username=req.old_username,
        email=req.email if req.email is not None else user.get("email"),
        totp_recovery_codes=req.totp_recovery_codes,
        method=req.method or user.get("method", "manual"),
        language=req.language or user.get("language", "en"),
    )
    if ret:
        code = 400 if "read-only" in ret or "doesn't exist" in ret else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.get("/{username}/sessions", dependencies=[Depends(guard)])
def get_user_sessions(username: str, current_session_id: Optional[str] = None) -> JSONResponse:
    """List active sessions for a user."""
    sessions = get_db().get_ui_user_sessions(username, current_session_id)

    for s in sessions:
        if "creation_date" in s:
            s["creation_date"] = s["creation_date"].isoformat() if hasattr(s["creation_date"], "isoformat") else str(s["creation_date"])
        if "last_activity" in s:
            s["last_activity"] = s["last_activity"].isoformat() if hasattr(s["last_activity"], "isoformat") else str(s["last_activity"])

    return JSONResponse(status_code=200, content={"status": "success", "sessions": sessions})


@router.delete("/{username}/sessions", dependencies=[Depends(guard)])
def delete_user_sessions(username: str) -> JSONResponse:
    """Delete old sessions for a user (keeps the most recent one)."""
    ret = get_db().delete_ui_user_old_sessions(username)
    if ret:
        return JSONResponse(status_code=500, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{username}/login", dependencies=[Depends(guard)])
def mark_user_login(username: str, req: LoginRequest) -> JSONResponse:
    """Mark a login event and return a session ID."""
    from datetime import datetime

    ret = get_db().mark_ui_user_login(username, datetime.now().astimezone(), req.ip, req.user_agent)
    if isinstance(ret, str):
        return JSONResponse(status_code=500, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success", "session_id": ret})


@router.post("/{username}/recovery-codes/refresh", dependencies=[Depends(guard)])
def refresh_recovery_codes(username: str, req: RecoveryCodesRefreshRequest) -> JSONResponse:
    """Regenerate recovery codes for a user."""
    ret = get_db().refresh_ui_user_recovery_codes(username, req.codes)
    if ret:
        return JSONResponse(status_code=500, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{username}/recovery-codes/use", dependencies=[Depends(guard)])
def use_recovery_code(username: str, req: RecoveryCodeUseRequest) -> JSONResponse:
    """Validate and consume a recovery code."""
    ret = get_db().use_ui_user_recovery_code(username, req.hashed_code)
    if ret:
        code = 400 if "Invalid" in ret or "doesn't exist" in ret else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


# ── Preferences ────────────────────────────────────────────────────


@router.get("/{username}/preferences/{table_name}", dependencies=[Depends(guard)])
def get_user_preferences(username: str, table_name: str) -> JSONResponse:
    """Get column visibility preferences for a table."""
    prefs = get_db().get_ui_user_columns_preferences(username, table_name)
    return JSONResponse(status_code=200, content={"status": "success", "preferences": prefs})


@router.patch("/{username}/preferences/{table_name}", dependencies=[Depends(guard)])
def update_user_preferences(username: str, table_name: str, req: UpdatePreferencesRequest) -> JSONResponse:
    """Update column visibility preferences for a table."""
    ret = get_db().update_ui_user_columns_preferences(username, table_name, req.columns)
    if ret:
        return JSONResponse(status_code=400, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


# ── Access Tracking ────────────────────────────────────────────────


@router.post("/{username}/access", dependencies=[Depends(guard)])
def mark_user_access(username: str, req: AccessRequest) -> JSONResponse:
    """Record user activity timestamp for a session."""
    from datetime import datetime

    ret = get_db().mark_ui_user_access(req.session_id, datetime.now().astimezone())
    if ret:
        return JSONResponse(status_code=400, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


# ── Permissions ────────────────────────────────────────────────────


@router.get("/{username}/permissions", dependencies=[Depends(guard)])
def get_user_permissions(username: str) -> JSONResponse:
    """Get all permissions for a user (aggregated from all roles)."""
    db = get_db()
    user = db.get_ui_user(username=username)
    if not user:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"User {username} not found"})
    permissions = []
    for role in getattr(user, "roles", []):
        permissions.extend(db.get_ui_role_permissions(role.role_name))
    return JSONResponse(status_code=200, content={"status": "success", "permissions": permissions})
