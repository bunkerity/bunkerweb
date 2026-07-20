#!/usr/bin/env python3
"""Provider-owned API routes for Let's Encrypt certificates."""

from typing import List

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.utils import get_db  # type: ignore
from letsencrypt_cache import list_letsencrypt_orphans  # type: ignore

router = APIRouter(tags=["certificates", "letsencrypt"])


class LetsEncryptCreateRequest(BaseModel):
    service_ids: List[str] = Field(..., min_length=1, max_length=100)

    @field_validator("service_ids")
    @classmethod
    def _service_ids(cls, values: List[str]) -> List[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not normalized or any("\x00" in value or len(value) > 253 for value in normalized):
            raise ValueError("service_ids must contain non-empty values of at most 253 characters without NUL bytes")
        return normalized


def _error(message: str, status_code: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        status_code = 404
    elif "read-only" in message.lower():
        status_code = 409
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message})


def _schedule() -> str:
    return get_db().checked_changes(["config"], plugins_changes=["letsencrypt"], value=True) or ""


def _certificates(db):
    offset = 0
    while True:
        page = db.get_certificates(source="letsencrypt", offset=offset, limit=500)
        yield from page["items"]
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            return


@router.post("/certificates")
def issue_certificate(payload: LetsEncryptCreateRequest) -> JSONResponse:
    db = get_db()
    known_services = {service["id"] for service in db.get_services(with_drafts=True)}
    unknown = [service_id for service_id in payload.service_ids if service_id not in known_services]
    if unknown:
        return _error(f"Service not found: {', '.join(unknown)}", 404)

    config = db.get_config(methods=False, with_drafts=True)
    default = config.get("AUTO_LETS_ENCRYPT", "no")
    disabled = [service_id for service_id in payload.service_ids if config.get(f"{service_id}_AUTO_LETS_ENCRYPT", default) != "yes"]
    if disabled:
        return _error(f"Let's Encrypt is not enabled for service(s): {', '.join(disabled)}", 409)
    if error := _schedule():
        return _error(error, 500)
    return JSONResponse(status_code=202, content={"status": "success", "message": "Let's Encrypt issuance scheduled"})


@router.post("/certificates/renew-due")
def renew_due_certificates() -> JSONResponse:
    due = [certificate for certificate in _certificates(get_db()) if certificate["status"] in ("expiring_soon", "expired")]
    results = [{"id": certificate["id"], "name": certificate["name"], "source": "letsencrypt", "status": "scheduled"} for certificate in due]
    if not due:
        return JSONResponse(
            status_code=200,
            content={"status": "success", "total_due": 0, "results": [], "message": "No Let's Encrypt certificates are due for renewal"},
        )
    if error := _schedule():
        return _error(error, 500)
    return JSONResponse(
        status_code=202,
        content={
            "status": "success",
            "total_due": len(due),
            "results": results,
            "message": f"Scheduled a Let's Encrypt renewal check for {len(due)} due certificate{'s' if len(due) != 1 else ''}",
        },
    )


@router.get("/certificates/orphans")
def get_orphan_certificates() -> JSONResponse:
    try:
        orphans = list_letsencrypt_orphans(get_db())
    except ValueError as exc:
        return _error(str(exc), 409)
    except Exception as exc:
        return _error(f"Unable to read the Let's Encrypt cache: {exc}", 500)
    return JSONResponse(status_code=200, content={"status": "success", "count": len(orphans), "orphans": orphans})
