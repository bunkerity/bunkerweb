"""Read-side aggregation of the resources attached to a single service.

Each resource family already exposes its own ``?service_id=`` filter on the API, so
this module fans out to the four of them and normalizes the answers into one shape.

A family is allowed to fail on its own: the workflows API ships inside the workflows
core plugin rather than in ``src/api/app/routers``, so it is simply absent when that
plugin is not loaded. Blanking the whole band for that would hide three working
families behind one missing one, hence the per-family error marker.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.api_client import ApiClientError, ApiUnavailableError

# The render-time mirror of the location namespace, shipped in src/common/utils and on the UI's
# sys.path (main.py:21-23 appends /usr/share/bunkerweb/utils). Reused rather than re-derived:
# db_methods/locations.py:44-50 computes the inline half of a conflict from exactly these three
# families, and a second copy of that loop in a Jinja template is how the two would drift.
from location_claims import claimed_paths  # type: ignore

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


def _resource_name(row: Dict[str, Any]) -> str:
    return str(row.get("name") or row.get("id") or "")


def _service_location_claims(attachments: Dict[str, Dict[str, Any]], service_id: str, config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """``{path: {"kind", "name", "resource_id"}}`` -- the HTTP location namespace already taken.

    Mirrors ``db_methods/locations.py:location_conflict`` (:88-109), both of its loops:

    * **attached resources** (``resource_location_claims``, :53-85). A redirect claims its own
      ``from_path``, shared by every attachment; an upstream claims the ``match_path`` of *its*
      attachment, so the same pool sits on a different path per service; a ``stream`` pool claims
      no path at all (:83) because a stream server has no ``location``.
    * **the service's own inline settings** (``inline_location_paths``, :44-50) -- REVERSE_PROXY,
      gRPC and REDIRECT, through the shipped ``claimed_paths`` rather than a second copy of it.

    ``resource_id`` rides along because ``location_conflict`` is called with the incoming
    resource as ``exclude_resource_id`` (:96): re-attaching a pool onto the path it already
    occupies is NOT a conflict, and a warning there would block a legal attach. Inline claims
    carry no id -- the DB does not exclude them either (:102-108).
    """
    claims: Dict[str, Dict[str, str]] = {}

    for row in attachments.get("redirect", {}).get("items", []):
        path = row.get("from_path")
        if path:
            claims.setdefault(path, {"kind": "redirect", "name": _resource_name(row), "resource_id": str(row.get("id") or "")})

    for row in attachments.get("upstream", {}).get("items", []):
        if row.get("protocol") == "stream":
            continue
        for attachment in row.get("services", []):
            if attachment.get("service_id") != service_id:
                continue
            path = attachment.get("match_path")
            if path:
                claims.setdefault(path, {"kind": "upstream", "name": _resource_name(row), "resource_id": str(row.get("id") or "")})

    if config:
        # The settings page holds {key: {"value": ...}}; claimed_paths wants flat values, and the
        # service payload is unprefixed, hence the single empty prefix.
        #
        # `method != "default"` is load-bearing, not tidiness. The API's own refusal reads
        # Global_values + Services_settings only (db_methods/locations.py:24-41), so a value with
        # no stored row is invisible to it -- and a template overlay is exactly that:
        # config_read.py:349-355 injects template settings at method "default" with `template`
        # set. Every shipped template (core/templates/templates/{low,medium,high,api}.json) sets
        # REVERSE_PROXY_HOST and REVERSE_PROXY_URL=/, and `low` is the default, so claiming those
        # would have this dialog refuse a pool-at-"/" attach on EVERY templated service -- an
        # operation the API accepts, citing settings the operator cannot clear from here. That is
        # the invented-warning direction the docstring below promises to avoid.
        flat = {
            key: (entry.get("value", "") if isinstance(entry, dict) else entry)
            for key, entry in config.items()
            if not isinstance(entry, dict) or entry.get("method") != "default"
        }
        for path, label in claimed_paths(flat, [""]).items():
            claims.setdefault(path, {"kind": "inline", "name": label, "resource_id": ""})

    return claims


def resource_conflict_context(
    attachments: Dict[str, Dict[str, Any]],
    service_id: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """What the attach dialog needs to refuse a conflict *before* the API does.

    One value rather than three, so the page wiring is a single context variable.

    ``config`` is the settings page's ``{key: {"value": ...}}`` map. Omit it and only the
    resource half of the location namespace is known: the dialog then warns about strictly less
    than the API refuses, which is the safe direction -- a missed warning costs a round trip and
    an error flash, while an invented one blocks an attach the API would have accepted.
    """
    stream_upstream = None
    for row in attachments.get("upstream", {}).get("items", []):
        # db_methods/upstreams.py:120-133 -- a stream server proxies the whole connection, so a
        # service can only ever carry one stream pool; a second attach is refused outright.
        if row.get("protocol") == "stream" and any(att.get("service_id") == service_id for att in row.get("services", [])):
            stream_upstream = {"id": row.get("id", ""), "name": _resource_name(row)}
            break

    primary_certificate = None
    for row in attachments.get("certificate", {}).get("items", []):
        # db_methods/certificates.py:588-591 -- attaching a certificate as primary clears
        # is_primary on every attachment of the service first, and says nothing about it. What
        # changes is which certificate is deployed: get_deployable_certificates orders by
        # `is_primary desc, creation_date desc` and keeps the first row per service (:175-180).
        if any(att.get("service_id") == service_id and att.get("is_primary") for att in row.get("attachments", [])):
            primary_certificate = {"id": row.get("id", ""), "name": _resource_name(row) or row.get("common_name", "")}
            break

    return {
        "paths": _service_location_claims(attachments, service_id, config),
        "stream_upstream": stream_upstream,
        "primary_certificate": primary_certificate,
    }
