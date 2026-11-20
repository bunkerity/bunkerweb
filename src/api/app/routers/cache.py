from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from common_utils import is_sensitive_job_cache_file  # type: ignore
from model import Jobs, Jobs_cache  # type: ignore

from ..schemas import CacheFilesDeleteRequest, CacheFileKey

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/cache", tags=["cache"])

RESTRICTED = object()


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
    request: Request,
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
        with_data: Include file content (text files only); never for sensitive entries unless the caller is an API admin
    """
    is_admin = getattr(request.state, "auth_admin", False) is True
    items = get_db().get_jobs_cache_files(with_data=with_data, job_name=job_name or "", plugin_id=plugin or "")
    out: List[Dict[str, Any]] = []
    for it in items:
        if service not in (None, "", "global") and it.get("service_id") != service:
            continue
        last_update = it.get("last_update")
        data = {
            "plugin": it.get("plugin_id"),
            "job_name": it.get("job_name"),
            "service": it.get("service_id") or "global",
            "file_name": it.get("file_name"),
            "last_update": last_update.astimezone().isoformat() if isinstance(last_update, datetime) else None,
            "checksum": it.get("checksum"),
        }
        if with_data and (is_admin or not is_sensitive_job_cache_file(it.get("file_name") or "", it.get("plugin_id") or "", it.get("job_name") or "")):
            text, printable = _decode_printable(it.get("data"))
            data["data"] = text
            data["printable"] = printable
        out.append(data)
    return JSONResponse(status_code=200, content={"status": "success", "cache": out})


def _transform_filename(path_token: str) -> str:
    # UI uses a special encoding for folders: prefix "folder:" and replace '_' with '/'. The prefix
    # is kept: `cache_dir` stores `file_name` with it included and the DB lookup matches that column
    # exactly, so stripping it made every folder-backed cache file 404.
    if path_token.startswith("folder:"):
        return path_token.replace("_", "/")
    return path_token


@router.get(
    "/{service}/{plugin_id}/{job_name}/{file_name}",
    dependencies=[Depends(guard)],
    response_model=None,
)
def fetch_cache_file(
    request: Request,
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
    fname = _transform_filename(file_name)
    # Before the DB read, and for absent rows too, so the answer does not reveal which sensitive names exist. Only the
    # Basic admin and API_TOKEN paths set `auth_admin`; an admin-issued Biscuit deliberately does not.
    is_admin = getattr(request.state, "auth_admin", False) is True
    if not is_admin and is_sensitive_job_cache_file(fname, plugin_id, job_name):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden"})
    data = get_db().get_job_cache_file(job_name, fname, service_id=_normalize_service(service) or "", plugin_id=plugin_id, with_info=True, with_data=True)
    if not data:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Cache file not found"})
    # The lookup follows the database collation, so the row found may carry other spellings than the request (case, trailing
    # spaces): decide again on the stored names, before any byte leaves.
    if not is_admin and is_sensitive_job_cache_file(data["file_name"], data["plugin_id"], data["job_name"]):
        return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden"})
    if download:
        content = data.get("data") if isinstance(data, dict) else data
        if not isinstance(content, (bytes, bytearray)):
            content = b""
        headers = {"Content-Disposition": f'attachment; filename="{quote(fname, safe="")}"'}
        return Response(status_code=200, content=content, media_type="application/octet-stream", headers=headers)
    # Return printable content only
    content = data.get("data") if isinstance(data, dict) else data
    text, printable = _decode_printable(content)
    last_update = data.get("last_update") if isinstance(data, dict) else None
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "file": {
                "plugin": plugin_id,
                "job_name": job_name,
                "service": service or "global",
                "file_name": fname,
                "last_update": (datetime.fromtimestamp(last_update).astimezone().isoformat() if isinstance(last_update, (int, float)) else None),
                "checksum": (data.get("checksum") if isinstance(data, dict) else None),
                "data": text,
                "printable": printable,
            },
        },
    )


def _delete_cache_rows(db: Any, file_name: str, *, job_name: str, service_id: Optional[str], plugin_id: str, admin: bool):
    """Delete the cache rows a request names. None: no row. RESTRICTED: a stored row is sensitive and the caller is not an API admin.
    "": deleted. Other strings: errors.

    The lookup follows the database collation (MariaDB/MySQL: case-insensitive, trailing spaces ignored), so it can match rows the
    request did not spell. The rows are resolved, authorized and deleted by id and stored identity in one transaction: exactly the rows that were checked.
    """
    if db.readonly:
        return "The database is read-only, the changes will not be saved"

    with db._db_session() as session:
        if not session.query(Jobs).filter_by(name=job_name, plugin_id=plugin_id).first():
            return None

        rows = (
            session.query(Jobs_cache.id, Jobs_cache.file_name, Jobs_cache.job_name, Jobs_cache.service_id)
            .filter_by(file_name=file_name, service_id=service_id or None, job_name=job_name)
            .all()
        )
        if not rows:
            return None

        stored_plugins = {}
        for row in rows:
            stored_plugins[row.id] = session.query(Jobs.plugin_id).filter_by(name=row.job_name).scalar() or ""
            if not admin and is_sensitive_job_cache_file(row.file_name, stored_plugins[row.id], row.job_name):
                return RESTRICTED

        try:
            # The read above holds no lock: another writer can replace a row and reuse its id before this DELETE. Every column the
            # check read stays in the WHERE, so a replaced row matches nothing and is never deleted.
            for row in rows:
                deleted = (
                    session.query(Jobs_cache)
                    .filter(
                        Jobs_cache.id == row.id,
                        Jobs_cache.file_name == row.file_name,
                        Jobs_cache.job_name == row.job_name,
                        Jobs_cache.service_id.is_(None) if row.service_id is None else Jobs_cache.service_id == row.service_id,
                        Jobs_cache.job_name.in_(select(Jobs.name).where(Jobs.plugin_id == stored_plugins[row.id])),
                    )
                    .delete(synchronize_session=False)
                )
                if deleted != 1:
                    session.rollback()
                    return None
            db._blob_sweep(session)
            session.commit()
        except BaseException as e:
            return str(e)

    return ""


def _delete_cache_files(payload: CacheFilesDeleteRequest, *, admin: bool, single: bool = False) -> JSONResponse:
    """Delete cache files and report whether each requested row existed."""
    items = payload.cache_files

    db = get_db()
    deleted = 0
    errors: List[str] = []
    changed_plugins: set[str] = set()
    not_found_errors = 0
    forbidden_errors = 0
    for it in items:
        fname = _transform_filename(it.fileName)
        job = it.jobName
        svc = _normalize_service(it.service)
        plug = it.plugin
        if not fname or not job:
            continue
        # Same rule as the reads: API admins only, decided before the DB read and again on the stored rows.
        err = (
            RESTRICTED
            if not admin and is_sensitive_job_cache_file(fname, plug, job)
            else _delete_cache_rows(db, fname, job_name=job, service_id=svc, plugin_id=plug, admin=admin)
        )
        if err is RESTRICTED:
            forbidden_errors += 1
            errors.append(f"{fname}: Forbidden")
        elif err is None:
            not_found_errors += 1
            errors.append(f"{fname}: Cache file not found")
        elif err:
            errors.append(f"{fname}: {err}")
        else:
            changed_plugins.add(plug)
            deleted += 1

    # Notify scheduler to apply changes for affected plugins
    if changed_plugins:
        try:
            ret = db.checked_changes(changes=["config"], plugins_changes=list(changed_plugins), value=True)
        except Exception as e:
            ret = str(e)
        if ret:
            errors.append(f"Scheduler was not notified of the deletion: {ret}")

    if errors and deleted:
        status_code = 207
    elif errors:
        status_code = 403 if forbidden_errors == len(errors) else 404 if single and not_found_errors == len(errors) else 400
    else:
        status_code = 200
    body: Dict[str, Any] = {"status": "success" if deleted and not errors else ("partial" if deleted else "error")}
    body["deleted"] = deleted
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


@router.delete("", dependencies=[Depends(guard)])
def delete_cache_files(request: Request, payload: CacheFilesDeleteRequest) -> JSONResponse:
    """Delete multiple cache files.

    Args:
        payload: Request containing list of cache files to delete
    """
    return _delete_cache_files(payload, admin=getattr(request.state, "auth_admin", False) is True)


@router.delete("/{service}/{plugin_id}/{job_name}/{file_name}", dependencies=[Depends(guard)])
def delete_cache_file(request: Request, service: str, plugin_id: str, job_name: str, file_name: str) -> JSONResponse:
    """Delete a specific cache file.

    Args:
        service: Service ID
        plugin_id: Plugin ID
        job_name: Job name
        file_name: File name
    """
    req = CacheFilesDeleteRequest(cache_files=[CacheFileKey(service=service, plugin=plugin_id, jobName=job_name, fileName=file_name)])
    return _delete_cache_files(req, admin=getattr(request.state, "auth_admin", False) is True, single=True)
