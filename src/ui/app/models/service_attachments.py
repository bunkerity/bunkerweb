"""Read-side aggregation of the resources attached to a single service.

Each resource family already exposes its own ``?service_id=`` filter on the API, so
this module fans out to the four of them and normalizes the answers into one shape.

A family is allowed to fail on its own: the workflows API ships inside the workflows
core plugin rather than in ``src/api/app/routers``, so it is simply absent when that
plugin is not loaded. Blanking the whole band for that would hide three working
families behind one missing one, hence the per-family error marker.
"""

from typing import Any, Dict, List, Tuple

from app.api_client import ApiClientError, ApiUnavailableError

# Ordered as the band renders them: routing first, then TLS, then rules.
RESOURCE_FAMILIES: Tuple[str, ...] = ("upstream", "certificate", "redirect", "workflow")

# family -> (api_client method name, key holding the rows in the JSON response)
_FAMILY_SOURCES: Dict[str, Tuple[str, str]] = {
    "upstream": ("get_upstreams", "upstreams"),
    "certificate": ("get_certificates", "certificates"),
    "redirect": ("get_redirects", "redirects"),
    "workflow": ("get_workflows", "workflows"),
}


def _empty() -> Dict[str, Any]:
    return {"items": [], "error": None}


def get_service_attachments(api_client: Any, service_id: str) -> Dict[str, Dict[str, Any]]:
    """Return ``{family: {"items": [...], "error": str | None}}`` for one service.

    ``service_id`` empty (the "new service" page) short-circuits to empty entries
    without calling the API: there is no service to filter on yet.
    """
    result: Dict[str, Dict[str, Any]] = {family: _empty() for family in RESOURCE_FAMILIES}
    if not service_id:
        return result

    for family in RESOURCE_FAMILIES:
        method_name, rows_key = _FAMILY_SOURCES[family]
        try:
            payload = getattr(api_client, method_name)(service_id=service_id, limit=500)
        except (ApiClientError, ApiUnavailableError) as exc:
            result[family]["error"] = getattr(exc, "message", None) or str(exc)
            continue
        rows: List[dict] = payload.get(rows_key, []) if isinstance(payload, dict) else []
        result[family]["items"] = rows

    return result


def attached_ids(attachments: Dict[str, Dict[str, Any]], family: str) -> set:
    """Ids already attached for one family — used to filter the attach picker."""
    return {row.get("id") for row in attachments.get(family, {}).get("items", []) if row.get("id")}


def failed_families(attachments: Dict[str, Dict[str, Any]]) -> List[str]:
    """Families whose read failed, for a single aggregated warning in the UI."""
    return [family for family, entry in attachments.items() if entry["error"]]
