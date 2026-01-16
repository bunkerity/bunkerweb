from contextlib import suppress
from typing import Annotated, Any, Dict, List, Optional
from re import sub as re_sub
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, Path as PathParam, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db
from ..schemas import (
    ConfigCreateRequest,
    ConfigUpdateRequest,
    ConfigsDeleteRequest,
    ConfigKey,
    ConfigType,
    OptionalConfigType,
    validate_config_name,
)


router = APIRouter(prefix="/configs", tags=["configs"])


def _sanitize_name_from_filename(filename: str) -> str:
    base = Path(filename).stem
    # Replace invalid chars with underscore and collapse repeats
    cleaned = re_sub(r"[^\w-]+", "_", base).strip("_-")
    if len(cleaned) > 255:
        cleaned = cleaned[:255]
    return cleaned


def _service_exists(service: Optional[str]) -> bool:
    if not service:
        return True
    db = get_db()
    try:
        conf = db.get_config(global_only=True, methods=False, with_drafts=True)
        return service in (conf.get("SERVER_NAME", "www.example.com") or "").split()
    except Exception:
        return False


def _decode_data(val: bytes | str | None) -> str:
    if val is None:
        return ""
    if isinstance(val, bytes):
        with suppress(Exception):
            return val.decode("utf-8")
        return val.decode("utf-8", errors="replace")
    return str(val)


@router.get("", dependencies=[Depends(guard)])
def list_configs(
    service: Optional[str] = None,
    type: Annotated[OptionalConfigType, Query(description="Config type filter")] = None,  # noqa: A002
    with_drafts: bool = True,
    with_data: bool = False,
) -> JSONResponse:
    """List custom configs.

    Query params:
    - service: service id, or "global"/empty for global configs
    - type: optional filter (e.g., http, server_http, modsec, ...)
    - with_drafts: include draft services when computing templates
    - with_data: include the content of configs
    """
    db = get_db()
    s_filter = None if (service in (None, "", "global")) else service
    t_filter = type  # Already normalized by Pydantic
    items = db.get_custom_configs(with_drafts=with_drafts, with_data=with_data)

    out: List[Dict[str, Any]] = []
    for it in items:
        if s_filter is not None and it.get("service_id") != s_filter:
            continue
        if t_filter is not None and it.get("type") != t_filter:
            continue
        data = {k: v for k, v in it.items() if k != "data"}
        if with_data:
            data["data"] = _decode_data(it.get("data"))
        # Normalize global service presentation
        data["service"] = data.pop("service_id", None) or "global"
        data["is_draft"] = bool(it.get("is_draft", False))
        out.append(data)

    return JSONResponse(status_code=200, content={"status": "success", "configs": out})


@router.post("/upload", dependencies=[Depends(guard)])
async def upload_configs(
    files: List[UploadFile] = File(..., description="One or more config files to create"),
    service: Optional[str] = Form(None, description='Service id; use "global" or leave empty for global'),
    type: Annotated[ConfigType, Form(description="Config type")] = ...,  # noqa: A002
    is_draft: bool = Form(False, description="Mark uploaded custom configs as draft"),
) -> JSONResponse:
    """Create new custom configs from uploaded files (method="api").

    The config name is derived from each file's basename (without extension),
    sanitized to `^[\\w_-]{1,255}$`.

    Args:
        files: Config files to upload
        service: Service ID or "global"
        type: Config type
    """
    s_id = None if service in (None, "", "global") else service
    ctype = type  # Already normalized by Pydantic
    if not _service_exists(s_id):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Service not found"})

    db = get_db()
    created: List[str] = []
    errors: List[Dict[str, str]] = []

    for f in files:
        try:
            filename = f.filename or ""
            name = _sanitize_name_from_filename(filename)
            err = validate_config_name(name)
            if err:
                errors.append({"file": filename or name, "error": err})
                continue
            content_bytes = await f.read()
            # Decode as UTF-8 text; replace undecodable bytes
            config_content = ""
            with suppress(Exception):
                config_content = content_bytes.decode("utf-8")
            if not isinstance(content_bytes, (bytes, bytearray)):
                # Should not happen, but guard anyway
                config_content = str(content_bytes)
            else:
                try:
                    config_content = content_bytes.decode("utf-8", errors="replace")
                except Exception:
                    config_content = ""

            error = db.upsert_custom_config(
                ctype,
                name,
                {"service_id": s_id, "type": ctype, "name": name, "data": config_content, "method": "api", "is_draft": is_draft},
                service_id=s_id,
                new=True,
            )
            if error:
                errors.append({"file": filename or name, "error": error})
            else:
                created.append(f"{(s_id or 'global')}/{ctype}/{name}")
        except Exception as e:
            errors.append({"file": f.filename or "(unknown)", "error": str(e)})

    status_code = 207 if errors and created else (400 if errors and not created else 201)
    content: Dict[str, Any] = {"status": "success" if created and not errors else ("partial" if created else "error")}
    if created:
        content["created"] = created
    if errors:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content)


@router.get("/{service}/{config_type}/{name}", dependencies=[Depends(guard)])
def get_config(
    service: str,
    config_type: Annotated[ConfigType, PathParam(description="Config type")],
    name: str,
    with_data: bool = True,
) -> JSONResponse:
    """Get a specific custom config.

    Args:
        service: Service ID or "global"
        config_type: Config type
        name: Config name
        with_data: Include config content
    """
    db = get_db()
    s_id = None if service in (None, "", "global") else service
    ctype = config_type  # Already normalized by Pydantic
    item = db.get_custom_config(ctype, name, service_id=s_id, with_data=with_data)
    if not item:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Config not found"})
    data = {k: v for k, v in item.items() if k != "data"}
    if with_data:
        data["data"] = _decode_data(item.get("data"))
    data["service"] = data.pop("service_id", None) or "global"
    data["is_draft"] = bool(item.get("is_draft", False))
    return JSONResponse(status_code=200, content={"status": "success", "config": data})


@router.post("", dependencies=[Depends(guard)])
def create_config(req: ConfigCreateRequest) -> JSONResponse:
    """Create a new custom config (method="api").

    Body:
    - service: optional service id (use "global" or omit for global)
    - type: config type (e.g., http, server_http, modsec, ...)
    - name: config name (^[\\w_-]{1,255}$)
    - data: content as UTF-8 string
    """
    service = req.service
    ctype = req.type
    name = req.name
    data = req.data
    is_draft = req.is_draft
    if not _service_exists(service):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Service not found"})

    error = get_db().upsert_custom_config(
        ctype,
        name,
        {"service_id": service, "type": ctype, "name": name, "data": data, "method": "api", "is_draft": is_draft},
        service_id=service,
        new=True,
    )
    if error:
        code = 400 if ("already exists" in error or "read-only" in error) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": error})
    return JSONResponse(status_code=201, content={"status": "success"})


@router.patch("/{service}/{config_type}/{name}", dependencies=[Depends(guard)])
def update_config(
    service: str,
    config_type: Annotated[ConfigType, PathParam(description="Config type")],
    name: str,
    req: ConfigUpdateRequest,
) -> JSONResponse:
    """Update or move a custom config. Only configs managed by method "api" or template-derived ones can be edited via API."""
    s_orig = None if service in (None, "", "global") else service
    ctype_orig = config_type  # Already normalized by Pydantic
    name_orig = name

    db = get_db()
    current = db.get_custom_config(ctype_orig, name_orig, service_id=s_orig, with_data=True)
    if not current:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Config not found"})
    # Enforce ownership similar to UI: allow editing only if current method is "api" or the item is template-derived
    if not current.get("template") and current.get("method") != "api":
        return JSONResponse(status_code=403, content={"status": "error", "message": "Config is not API-managed and cannot be edited"})

    # New values (optional)
    service_new = req.service
    type_new = req.type if req.type is not None else current.get("type")
    name_new = req.name if req.name is not None else current.get("name")
    data_new = req.data if req.data is not None else _decode_data(current.get("data"))
    is_draft_new = req.is_draft if req.is_draft is not None else current.get("is_draft", False)

    # Disallow renaming (changing the name) for template-derived configs; content edits are allowed
    if current.get("template") and name_new != current.get("name"):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Renaming a template-based custom config is not allowed"})
    if not _service_exists(service_new):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Service not found"})

    if (
        current.get("type") == type_new
        and current.get("name") == name_new
        and current.get("service_id") == service_new
        and _decode_data(current.get("data")) == data_new
        and bool(current.get("is_draft", False)) == bool(is_draft_new)
    ):
        return JSONResponse(status_code=400, content={"status": "error", "message": "No values were changed"})

    error = db.upsert_custom_config(
        ctype_orig,
        name_orig,
        {"service_id": service_new, "type": type_new, "name": name_new, "data": data_new, "method": "api", "is_draft": is_draft_new},
        service_id=s_orig,
    )
    if error:
        code = 400 if ("read-only" in error or "already exists" in error or "does not exist" in error) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": error})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.patch("/{service}/{config_type}/{name}/upload", dependencies=[Depends(guard)])
async def update_config_upload(
    service: str,
    config_type: Annotated[ConfigType, PathParam(description="Config type")],
    name: str,
    file: UploadFile = File(...),
    new_service: Optional[str] = Form(None),
    new_type: Annotated[OptionalConfigType, Form(description="New config type")] = None,
    new_name: Optional[str] = Form(None),
    new_is_draft: Optional[bool] = Form(None),
) -> JSONResponse:
    """Update an existing custom config using an uploaded file.

    Optional form fields `new_service`, `new_type`, `new_name` allow moving/renaming.
    """
    s_orig = None if service in (None, "", "global") else service
    ctype_orig = config_type  # Already normalized by Pydantic
    name_orig = name

    db = get_db()
    current = db.get_custom_config(ctype_orig, name_orig, service_id=s_orig, with_data=True)
    if not current:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Config not found"})
    if not current.get("template") and current.get("method") != "api":
        return JSONResponse(status_code=403, content={"status": "error", "message": "Config is not API-managed and cannot be edited"})

    s_new = None if new_service in (None, "", "global") else new_service
    t_new = new_type or current.get("type")  # Already normalized by Pydantic if provided
    n_new = new_name.strip() if isinstance(new_name, str) and new_name else current.get("name")
    if n_new == current.get("name") and not new_name:
        # If no explicit new_name, derive name from uploaded file if different
        filename = file.filename or ""
        derived = _sanitize_name_from_filename(filename)
        # Disallow implicit rename for template-derived configs
        if current.get("template") and derived and derived != n_new:
            return JSONResponse(status_code=403, content={"status": "error", "message": "Renaming a template-based custom config is not allowed"})
        if derived and derived != n_new:
            n_new = derived

    # If explicit new_name is provided and differs, forbid for template-derived configs
    if current.get("template") and new_name and n_new != current.get("name"):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Renaming a template-based custom config is not allowed"})

    err = validate_config_name(n_new)
    if err:
        return JSONResponse(status_code=422, content={"status": "error", "message": err})
    if not _service_exists(s_new):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Service not found"})

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8", errors="replace")
    except Exception:
        content = ""

    if (
        current.get("type") == t_new
        and current.get("name") == n_new
        and current.get("service_id") == s_new
        and _decode_data(current.get("data")) == content
        and (new_is_draft is None or bool(current.get("is_draft", False)) == bool(new_is_draft))
    ):
        return JSONResponse(status_code=400, content={"status": "error", "message": "No values were changed"})

    error = db.upsert_custom_config(
        ctype_orig,
        name_orig,
        {
            "service_id": s_new,
            "type": t_new,
            "name": n_new,
            "data": content,
            "method": "api",
            "is_draft": bool(new_is_draft) if new_is_draft is not None else current.get("is_draft", False),
        },
        service_id=s_orig,
    )
    if error:
        code = 400 if ("read-only" in error or "already exists" in error or "does not exist" in error) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": error})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.delete("", dependencies=[Depends(guard)])
def delete_configs(req: ConfigsDeleteRequest) -> JSONResponse:
    """Delete multiple API-managed custom configs.

    Body example:
    {"configs": [{"service": "global", "type": "http", "name": "my_snippet"}, ...]}
    Only configs with method == "api" will be deleted; others are ignored.
    """
    configs = req.configs

    # Build a set of keys to delete
    to_del = {(it.service, it.type, it.name) for it in configs}

    if not to_del:
        return JSONResponse(status_code=422, content={"status": "error", "message": "No valid configs to delete"})

    db = get_db()
    # Keep only API-managed configs not in to_del
    current = db.get_custom_configs(with_drafts=True, with_data=True)
    keep: List[Dict[str, Any]] = []
    skipped: List[str] = []
    for it in current:
        key = (it.get("service_id"), it.get("type"), it.get("name"))
        if it.get("method") != "api":
            # Not API-managed: ignore deletions for these
            if key in to_del:
                skipped.append(f"{(it.get('service_id') or 'global')}/{it.get('type')}/{it.get('name')}")
            continue
        if key in to_del:
            # delete -> skip adding to keep
            continue
        # Convert to expected format for save_custom_configs
        keep.append(
            {
                "service_id": it.get("service_id") or None,
                "type": it.get("type"),
                "name": it.get("name"),
                "data": it.get("data") or b"",
                "method": "api",
            }
        )

    err = db.save_custom_configs(keep, "api")
    if err:
        return JSONResponse(status_code=500, content={"status": "error", "message": err})

    content: Dict[str, Any] = {"status": "success"}
    if skipped:
        content["skipped"] = skipped
    return JSONResponse(status_code=200, content=content)


@router.delete("/{service}/{config_type}/{name}", dependencies=[Depends(guard)])
def delete_config(
    service: str,
    config_type: Annotated[ConfigType, PathParam(description="Config type")],
    name: str,
) -> JSONResponse:
    """Delete a single API-managed custom config by replacing the API set without the selected item."""
    s_id = None if service in (None, "", "global") else service
    # config_type is already normalized by Pydantic
    return delete_configs(ConfigsDeleteRequest(configs=[ConfigKey(service=s_id or "global", type=config_type, name=name)]))
