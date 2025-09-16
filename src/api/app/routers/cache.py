from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from ..schemas import CacheFilesDeleteRequest, CacheFileKey

from ..auth.guard import guard
from ..utils import get_db


router = APIRouter(prefix="/cache", tags=["cache"])


def _normalize_service(value: Optional[str]) -> Optional[str]:
    if value in (None, "", "global"):
        return None
    return str(value)


def _decode_printable(b: Optional[bytes]) -> tuple[str, bool]:
    if not isinstance(b, (bytes, bytearray)):
        return "", False
    try:
        s = b.decode("utf-8")
    except Exception:
        return "Download file to view content", False
    # Keep simple heuristic: printable if utf-8 decode succeeded and no control chars beyond common whitespace
    if any(ord(ch) < 9 or (13 < ord(ch) < 32) for ch in s):
        return "Download file to view content", False
    return s, True


@router.get("", dependencies=[Depends(guard)])
def list_cache(
    service: Optional[str] = None,
    plugin: Optional[str] = None,
    job_name: Optional[str] = None,
    with_data: bool = Query(False, description="Include file data inline (text only)"),
) -> JSONResponse:
    """List cache files from job executions.

    Args:
        service: Filter by service ID
        plugin: Filter by plugin ID
        job_name: Filter by job name
        with_data: Include file content (text files only)
    """
    items = get_db().get_jobs_cache_files(with_data=with_data, job_name=job_name or "", plugin_id=plugin or "")
    out: List[Dict[str, Any]] = []
    for it in items:
        if service not in (None, "", "global") and it.get("service_id") != service:
            continue
        data = {
            "plugin": it.get("plugin_id"),
            "job_name": it.get("job_name"),
            "service": it.get("service_id") or "global",
            "file_name": it.get("file_name"),
            "last_update": it.get("last_update").astimezone().isoformat() if it.get("last_update") else None,
            "checksum": it.get("checksum"),
        }
        if with_data:
            text, printable = _decode_printable(it.get("data"))
            data["data"] = text
            data["printable"] = printable
        out.append(data)
    return JSONResponse(status_code=200, content={"status": "success", "cache": out})


def _transform_filename(path_token: str) -> str:
    # UI uses a special encoding for folders: prefix "folder:" and replace '_' with '/'
    if path_token.startswith("folder:"):
        return path_token.replace("_", "/")[len("folder:") :]  # noqa: E203
    return path_token


@router.get(
    "/{service}/{plugin_id}/{job_name}/{file_name}",
    dependencies=[Depends(guard)],
    response_model=None,
)
def fetch_cache_file(
    service: str,
    plugin_id: str,
    job_name: str,
    file_name: str,
    download: bool = False,
) -> Response:
    """Fetch content of a specific cache file.

    Args:
        service: Service ID
        plugin_id: Plugin ID
        job_name: Job name
        file_name: File name
        download: Return as downloadable attachment
    """
    db = get_db()
    fname = _transform_filename(file_name)
    data = db.get_job_cache_file(job_name, fname, service_id=_normalize_service(service) or "", plugin_id=plugin_id, with_info=True, with_data=True)
    if not data:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Cache file not found"})
    if download:
        content = data.get("data") if isinstance(data, dict) else data
        if not isinstance(content, (bytes, bytearray)):
            content = b""
        headers = {"Content-Disposition": f"attachment; filename={fname}"}
        return Response(status_code=200, content=content, media_type="application/octet-stream", headers=headers)
    # Return printable content only
    content = data.get("data") if isinstance(data, dict) else data
    text, printable = _decode_printable(content)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "file": {
                "plugin": plugin_id,
                "job_name": job_name,
                "service": service or "global",
                "file_name": fname,
                "last_update": (datetime.fromtimestamp(data.get("last_update")).astimezone().isoformat() if isinstance(data, dict) and data.get("last_update") else None),  # type: ignore
                "checksum": (data.get("checksum") if isinstance(data, dict) else None),
                "data": text,
                "printable": printable,
            },
        },
    )


@router.delete("", dependencies=[Depends(guard)])
def delete_cache_files(payload: CacheFilesDeleteRequest) -> JSONResponse:
    """Delete multiple cache files.

    Args:
        payload: Request containing list of cache files to delete
    """
    items = payload.cache_files

    db = get_db()
    deleted = 0
    errors: List[str] = []
    changed_plugins: set[str] = set()
    for it in items:
        fname = _transform_filename(it.fileName)
        job = it.jobName
        svc = _normalize_service(it.service)
        plug = it.plugin
        if not fname or not job:
            continue
        err = db.delete_job_cache(fname, job_name=job, service_id=svc)
        if err:
            errors.append(f"{fname}: {err}")
        else:
            changed_plugins.add(plug)
            deleted += 1

    # Notify scheduler to apply changes for affected plugins
    with suppress(Exception):
        db.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)

    status_code = 207 if errors and deleted else (400 if errors and not deleted else 200)
    body: Dict[str, Any] = {"status": "success" if deleted and not errors else ("partial" if deleted else "error")}
    body["deleted"] = deleted
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


@router.delete("/{service}/{plugin_id}/{job_name}/{file_name}", dependencies=[Depends(guard)])
def delete_cache_file(service: str, plugin_id: str, job_name: str, file_name: str) -> JSONResponse:
    """Delete a specific cache file.

    Args:
        service: Service ID
        plugin_id: Plugin ID
        job_name: Job name
        file_name: File name
    """
    req = CacheFilesDeleteRequest(cache_files=[CacheFileKey(service=service, plugin=plugin_id, jobName=job_name, fileName=file_name)])
    return delete_cache_files(req)
