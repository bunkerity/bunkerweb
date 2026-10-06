"""Unban flow for CrowdSec leases: locate, discover, confirm, delete, converge, remove. Shared by the API, the Web UI and bwcli."""

from ipaddress import ip_network

from CrowdSec import CrowdSecError

LIST_ORIGINS = frozenset({"capi", "lists"})
PAGE = 200


def _up(instance: dict) -> bool:
    return instance.get("status") != "down"


def lease_in_rows(rows, ip: str, ban_scope: str, service: str | None) -> dict | None:
    """Pure: the lease row for (ip, ban_scope, service) in one instance's GET /bans data, if any."""
    for row in rows or []:
        if not isinstance(row, dict) or row.get("kind") != "crowdsec_lease" or row.get("ip") != ip:
            continue
        if row.get("ban_scope", "global") != ban_scope or (ban_scope == "service" and row.get("service") != service):
            continue
        if isinstance(row.get("reason_data"), dict):
            return row
    return None


def find_lease(client, ip: str, ban_scope: str, service: str | None) -> dict | None:
    """Exact lookup through the instance API: local copy first, then Redis (POST /lease_lookup, no SCAN)."""
    payload = {"ip": ip, "ban_scope": ban_scope, **({"service": service} if ban_scope == "service" and service else {})}
    failures = []
    for instance in client._instances():
        host = instance.get("hostname")
        if not _up(instance):
            failures.append(f"{host}: down")
            continue
        try:
            reply = client.instance_request(instance, "POST", "/lease_lookup", payload)
        except CrowdSecError as exc:
            failures.append(f"{host}: {exc}")
            continue
        if not isinstance(reply, dict) or not isinstance(reply.get("found"), bool):
            failures.append(f"{host}: malformed lease lookup reply")
            continue
        if reply["found"]:
            row = reply.get("row")
            if isinstance(row, dict) and isinstance(row.get("reason_data"), dict):
                return row
            failures.append(f"{host}: malformed lease row")
            continue
    # Absence needs a completed negative from every instance: a local-only lease (written while Redis was unreachable)
    # lives on one instance only, so a Redis negative elsewhere proves nothing about it
    if failures:
        raise CrowdSecError("Could not check every instance for a CrowdSec ban: " + "; ".join(failures), 502)
    return None


def _all_decisions(client, connection_id: str, ip: str) -> list[dict]:
    decisions, offset = [], 0
    while True:
        page = client.query(connection_id, "decisions", {"ip": ip, "limit": PAGE, "offset": offset})
        batch = page.get("decisions") or []
        decisions.extend(batch)
        offset += len(batch)
        if not batch or offset >= int(page.get("total") or 0):
            return decisions


def _wide_range(decision: dict) -> bool:
    if str(decision.get("scope", "")).lower() != "range":
        return False
    try:
        return ip_network(str(decision.get("value")), strict=False).num_addresses > 1
    except ValueError:
        return True  # an unreadable range is shown as a warning rather than crashing the preview


def _label(connection: dict) -> str:
    return connection.get("id") or f"{connection.get('instance')}:{','.join(connection.get('services') or [])}"


def _serving(rows: list[dict], scope_value: str) -> list[dict]:
    """Every connection row, ID-less failure rows included, whose decisions can block the lease's scope.

    A global lease is a global ban: it blocks every service, so every connection applies. A service lease applies,
    on each instance, to the connections configured for that service, or to that instance's global connections when
    the service has none there (the bouncer's own fallback, crowdsec.lua access()).
    """
    if scope_value == "global":
        return rows.copy()
    serving = []
    for instance in {row.get("instance") for row in rows}:
        group = [row for row in rows if row.get("instance") == instance]
        specific = [row for row in group if scope_value in (row.get("services") or [])]
        serving.extend(specific)
        # A failed service bouncer (no valid id) is not loaded, so the bouncer falls back to global there
        if not any(row.get("id") for row in specific):
            serving.extend(row for row in group if "global" in (row.get("services") or []))
    return serving


def preview(client, ip: str, ban_scope: str, service: str | None) -> dict:
    lease = find_lease(client, ip, ban_scope, service)
    if not lease:
        raise CrowdSecError("No CrowdSec ban found for this IP", 404)
    reason_data = lease["reason_data"]
    listing = client.connections()
    rows = listing.get("connections", [])
    matches = [c for c in rows if c.get("id") and c.get("node") == reason_data.get("instance") and c.get("local_id") == reason_data.get("connection")]
    if len(matches) != 1 or matches[0].get("status") != "success":
        raise CrowdSecError("The CrowdSec source instance is unavailable or ambiguous; the ban expires on its own", 409)
    source = matches[0]
    serving = _serving(rows, reason_data.get("service_scope") or "global")
    unavailable = [_label(c) for c in serving if not c.get("id") or c.get("status") != "success"]
    unavailable += [f"instance:{host}" for host in (listing.get("errors") or {})]
    healthy = [c for c in serving if c.get("id") and c.get("status") == "success"]
    unavailable_ids = [c["id"] for c in serving if c.get("id") and c.get("status") != "success"]
    decisions = []
    for connection in healthy:
        try:
            found = _all_decisions(client, connection["id"], ip)
        except CrowdSecError:
            unavailable.append(connection["id"])
            unavailable_ids.append(connection["id"])
            continue
        for decision in found:
            if decision.get("remediation") != "ban":
                continue
            decisions.append(
                {
                    "key": f"{connection['id']}:{decision['id']}",
                    "connection_id": connection["id"],
                    **{field: decision.get(field) for field in ("id", "scope", "value", "type", "origin", "scenario", "remediation")},
                }
            )
    return {
        "lease": {"ip": ip, "ban_scope": ban_scope, "service": service, "exp": lease.get("exp")},
        "source": {"connection_id": source["id"], "instance": source.get("instance")},
        "connections": [c["id"] for c in healthy if c["id"] not in unavailable],
        "unavailable": unavailable,
        "unavailable_ids": unavailable_ids,
        "decisions": decisions,
        "warnings": {
            "list_origin": any(str(d.get("origin", "")).lower() in LIST_ORIGINS for d in decisions),
            "range": any(_wide_range(d) for d in decisions),
        },
        # Deleting needs management credentials only where a selected decision lives; refresh_ip uses the bouncer key
        "management_missing": sorted({d["connection_id"] for d in decisions} - {c["id"] for c in healthy if c.get("management_configured")}),
    }


def involved(current: dict) -> tuple[set[str], bool]:
    """(connection ids, needs wildcard) for everything a preview touches or reports: source, healthy and failed connections, decisions.

    An unavailable entry without a known connection id (an ID-less row or an instance that failed to list) cannot be
    matched to a grant, so it needs wildcard authorization.
    """
    known = set(current.get("unavailable_ids") or [])
    ids = {current["source"]["connection_id"], *current["connections"], *known, *(d["connection_id"] for d in current["decisions"])}
    return ids, any(entry not in known for entry in current["unavailable"])


def revalidate(client, ip: str, ban_scope: str, service: str | None, confirmed_keys: list[str], allowed_connections: set[str] | None = None) -> dict:
    """Fresh preview checked against what the caller confirmed. Returns {"status": "ready", "preview": ...} or "changed".

    allowed_connections: what the caller authorized, as the ids from `involved`, plus "*" when it holds wildcard
    authorization; None means the caller is admin.
    """
    current = preview(client, ip, ban_scope, service)
    if allowed_connections is not None and "*" not in allowed_connections:
        ids, wildcard = involved(current)
        if wildcard or not ids <= set(allowed_connections):
            return {"status": "changed"}  # no preview: it would disclose unauthorized connections
    if current["management_missing"]:
        raise CrowdSecError("CrowdSec management credentials are not configured on: " + ", ".join(current["management_missing"]), 409)
    if sorted(d["key"] for d in current["decisions"]) != sorted(confirmed_keys):
        return {"status": "changed", "preview": current}
    return {"status": "ready", "preview": current}


def execute(client, ip: str, ban_scope: str, service: str | None, confirmed_keys: list[str], allowed_connections: set[str] | None = None) -> dict:
    """Single item: revalidate, then apply."""
    checked = revalidate(client, ip, ban_scope, service, confirmed_keys, allowed_connections)
    if checked["status"] != "ready":
        return checked
    return apply(client, ip, ban_scope, service, checked["preview"])


def apply(client, ip: str, ban_scope: str, service: str | None, current: dict) -> dict:
    """Mutations only, on an already revalidated preview. Batch callers revalidate every item first, then apply each."""

    result = {
        "status": "success",
        "deleted": [],
        "already_absent": [],
        "failed": [],
        "refreshed": [],
        "lease_removed": [],
        "lease_failed": [],
        "down": [],
        "unavailable": list(current["unavailable"]),
    }
    for decision in current["decisions"]:
        params = {"decision_id": decision["id"], "scope": decision["scope"], "value": decision["value"], "decision_type": decision["type"]}
        try:
            reply = client.query(decision["connection_id"], "unban", params)
        except CrowdSecError as exc:
            result["failed"].append({"key": decision["key"], "error": str(exc)})
            continue
        result["already_absent" if reply.get("already_absent") else "deleted"].append(decision["key"])
    if result["failed"]:
        result["status"] = "partial"
        return result

    for connection_id in current["connections"]:
        try:
            client.query(connection_id, "refresh_ip", {"ip": ip})
            result["refreshed"].append(connection_id)
        except CrowdSecError as exc:
            result["failed"].append({"connection_id": connection_id, "error": str(exc)})
    for connection_id in current["connections"]:
        try:
            remaining = _all_decisions(client, connection_id, ip)
        except CrowdSecError as exc:
            result["failed"].append({"connection_id": connection_id, "error": f"postcondition check failed: {exc}"})
            continue
        if any(d.get("remediation") == "ban" for d in remaining):
            result["failed"].append({"connection_id": connection_id, "error": "a CrowdSec ban decision is still active"})
    if result["failed"]:
        result["status"] = "partial"
        return result

    payload = {"ip": ip, "ban_scope": ban_scope, **({"service": service} if ban_scope == "service" and service else {})}
    for instance in client._instances():
        if not _up(instance):
            result["down"].append(instance.get("hostname"))
            continue
        try:
            client.instance_request(instance, "POST", "/remove_lease", payload)
            result["lease_removed"].append(instance.get("hostname"))
        except CrowdSecError as exc:
            result["lease_failed"].append({"instance": instance.get("hostname"), "error": str(exc)})
    if result["lease_failed"] or result["unavailable"] or result["down"]:
        result["status"] = "partial"
    return result
