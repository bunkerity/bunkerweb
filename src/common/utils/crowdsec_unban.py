"""Unban flow for CrowdSec leases: discover, preview, revalidate, apply. Shared by the API, the Web UI and bwcli.

A lease is an ordinary ban created by the CrowdSec plugin (reason "crowdsec", ``reason_data.lease`` and a
``reason_data.lease_id`` that is new on every renewal). Unbanning one also has to delete the CrowdSec decisions
behind it, or the next request promotes it again.

Leases are found in the runtime view (each instance's ``GET /bans``, plus the Redis key of that identity), never in
the database alone: ``sync-bans`` learns once a minute and a lease can live for 30 seconds. A lease is removed only
through ``remove_lease`` (``POST /unban`` with ``lease_id``) and revoked only through ``revoke_lease``, so an explicit
ban on the same IP is never touched.
"""

from itertools import chain
from ipaddress import ip_network
from json import JSONDecodeError, loads
from time import time
from typing import Optional

from CrowdSec import CrowdSecError  # type: ignore
from common_utils import get_redis_client  # type: ignore
from db_methods.bans import KIND_LEASE, ban_kind, lease_id_of  # type: ignore
from redis_keys import ban_key as redis_ban_key, is_cluster  # type: ignore

LIST_ORIGINS = frozenset({"capi", "lists"})
PAGE = 200


def _up(instance: dict) -> bool:
    return instance.get("status") != "down"


def is_lease(row) -> bool:
    """Pure: does this ban row (runtime or Redis shape) describe a CrowdSec lease that can be removed by its ``lease_id``?

    One definition of the kind, shared with ``get_bans`` (lane A's ``ban_kind``); a lease without an id cannot be removed.
    """
    return ban_kind(row) == KIND_LEASE and bool(lease_id_of(row))


def _same_identity(row: dict, ip: str, ban_scope: str, service: Optional[str]) -> bool:
    return row.get("ip") == ip and row.get("ban_scope", "global") == ban_scope and (ban_scope != "service" or row.get("service") == service)


def redis_client_from(settings: dict):
    """The Redis client for the ban keys, or None when Redis is off. ``settings`` is the environment over the global configuration."""
    if str(settings.get("USE_REDIS") or "no").lower() != "yes":
        return None
    return get_redis_client(
        use_redis=True,
        redis_host=settings.get("REDIS_HOST") or None,
        redis_port=settings.get("REDIS_PORT") or "6379",
        redis_db=settings.get("REDIS_DATABASE") or "0",
        redis_timeout=settings.get("REDIS_TIMEOUT") or "1000.0",
        redis_keepalive_pool=settings.get("REDIS_KEEPALIVE_POOL") or "10",
        redis_ssl=str(settings.get("REDIS_SSL") or "no").lower() == "yes",
        redis_ssl_verify=str(settings.get("REDIS_SSL_VERIFY") or "yes").lower() == "yes",
        redis_ssl_ca=settings.get("REDIS_SSL_CA") or None,
        redis_username=settings.get("REDIS_USERNAME") or None,
        redis_password=settings.get("REDIS_PASSWORD") or None,
        redis_sentinel_hosts=settings.get("REDIS_SENTINEL_HOSTS") or [],
        redis_sentinel_username=settings.get("REDIS_SENTINEL_USERNAME") or None,
        redis_sentinel_password=settings.get("REDIS_SENTINEL_PASSWORD") or None,
        redis_sentinel_master=settings.get("REDIS_SENTINEL_MASTER") or "",
        redis_cluster_nodes=settings.get("REDIS_CLUSTER_NODES") or "",
    )


def _redis_row(redis_client, ip: str, ban_scope: str, service: Optional[str]) -> Optional[dict]:
    """The ban held in Redis for one identity, in the row shape instances report. Exact key, no SCAN."""
    local_key = f"bans_service_{service}_ip_{ip}" if ban_scope == "service" else f"bans_ip_{ip}"
    data = redis_client.get(redis_ban_key(local_key, is_cluster(redis_client)))
    if not data:
        return None
    try:
        row = loads(data.decode("utf-8", "replace") if isinstance(data, bytes) else data)
    except (JSONDecodeError, ValueError):
        return None
    if not isinstance(row, dict):
        return None
    expires_at = row.get("expires_at") or 0
    if row.get("permanent") is not True and expires_at <= time():
        return None
    return row | {"ip": ip, "ban_scope": ban_scope, "service": service if ban_scope == "service" else row.get("service", "")}


def collect_runtime(client) -> dict:
    """One ``GET /bans`` per instance: ``{"rows": {hostname: [rows]}, "failures": [hostname, ...]}``.

    Take it once per request and pass it to every lookup: the listing holds the instance's ban lock for the whole scan.
    """
    rows, failures = {}, []
    for instance in client._instances():
        host = instance.get("hostname")
        if not _up(instance):
            failures.append(host)
            continue
        try:
            listing = client.instance_request(instance, "GET", "/bans")
        except CrowdSecError:
            failures.append(host)
            continue
        if isinstance(listing, dict):
            listing = listing.get("bans", [])
        if not isinstance(listing, list):
            failures.append(host)
            continue
        rows[host] = listing
    return {"rows": rows, "failures": failures}


def find_leases(runtime: dict, ip: str, ban_scope: str, service: Optional[str], redis_client=None) -> tuple[list[dict], list[str]]:
    """The live leases of one identity, as ``{"lease_id", "source", "row"}``, and what could not be checked.

    Instances usually hold different ``lease_id`` values for the same identity: each one promotes on its own.
    """
    leases = []
    failures = [f"instance:{host}" for host in runtime["failures"]]
    for host, rows in runtime["rows"].items():
        for row in rows:
            if isinstance(row, dict) and _same_identity(row, ip, ban_scope, service) and is_lease(row):
                leases.append({"lease_id": row["reason_data"]["lease_id"], "source": host, "row": row})
    if redis_client is not None:
        try:
            row = _redis_row(redis_client, ip, ban_scope, service)
        except Exception:  # a remote store: any failure means "could not check", never "absent"
            failures.append("redis")
        else:
            if row and is_lease(row):
                leases.append({"lease_id": row["reason_data"]["lease_id"], "source": "redis", "row": row})
    return leases, failures


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


def preview(client, ip: str, ban_scope: str, service: Optional[str], runtime: Optional[dict] = None, redis_client=None) -> dict:
    runtime = runtime or collect_runtime(client)
    leases, failures = find_leases(runtime, ip, ban_scope, service, redis_client)
    if not leases:
        # Absence needs a completed negative from every instance and from Redis
        if failures:
            raise CrowdSecError("Could not check every instance for a CrowdSec ban: " + ", ".join(failures), 502)
        raise CrowdSecError("No CrowdSec ban found for this IP", 404)
    listing = client.connections()
    rows = listing.get("connections", [])
    # The connection that issued a lease: same local id, healthy, on the instance named by reason_data.instance when
    # the connection rows carry it (`node`). Several instances sharing one configuration share the local id.
    source = None
    for connection_hash, node in sorted(
        {(lease["row"]["reason_data"].get("connection"), lease["row"]["reason_data"].get("instance")) for lease in leases}, key=str
    ):
        candidates = [c for c in rows if c.get("id") and c.get("local_id") == connection_hash]
        if any("node" in c for c in candidates):
            candidates = [c for c in candidates if c.get("node") == node]
        healthy_sources = [c for c in candidates if c.get("status") == "success"]
        if not healthy_sources:
            raise CrowdSecError("The CrowdSec source connection is unavailable; the ban expires on its own", 409)
        source = source or healthy_sources[0]
    serving = []
    for scope_value in sorted({lease["row"]["reason_data"].get("service_scope") or "global" for lease in leases}):
        serving.extend(c for c in _serving(rows, scope_value) if not any(c is seen for seen in serving))
    unavailable = [_label(c) for c in serving if not c.get("id") or c.get("status") != "success"]
    unavailable += [f"instance:{host}" for host in (listing.get("errors") or {})]
    unavailable += [entry for entry in failures if entry not in unavailable]
    healthy = [c for c in serving if c.get("id") and c.get("status") == "success"]
    unavailable_ids = [c["id"] for c in serving if c.get("id") and c.get("status") != "success"]
    decisions = []
    for conn in healthy:
        try:
            found = _all_decisions(client, conn["id"], ip)
        except CrowdSecError:
            unavailable.append(conn["id"])
            unavailable_ids.append(conn["id"])
            continue
        for decision in found:
            if decision.get("remediation") != "ban":
                continue
            decisions.append(
                {
                    "key": f"{conn['id']}:{decision['id']}",
                    "connection_id": conn["id"],
                    **{field: decision.get(field) for field in ("id", "scope", "value", "type", "origin", "scenario", "remediation")},
                }
            )
    return {
        "lease": {"ip": ip, "ban_scope": ban_scope, "service": service, "exp": max(lease["row"].get("exp") or 0 for lease in leases)},
        "leases": [{"lease_id": lease["lease_id"], "source": lease["source"], "exp": lease["row"].get("exp")} for lease in leases],
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


def revalidate(
    client,
    ip: str,
    ban_scope: str,
    service: Optional[str],
    confirmed_keys: list[str],
    allowed_connections: Optional[set[str]] = None,
    runtime: Optional[dict] = None,
    redis_client=None,
) -> dict:
    """Fresh preview checked against what the caller confirmed. Returns {"status": "ready", "preview": ...} or "changed".

    allowed_connections: what the caller authorized, as the ids from `involved`, plus "*" when it holds wildcard
    authorization; None means the caller is admin. ``runtime``: a snapshot taken for this barrier (see collect_runtime).
    """
    current = preview(client, ip, ban_scope, service, runtime, redis_client)
    if allowed_connections is not None and "*" not in allowed_connections:
        ids, wildcard = involved(current)
        if wildcard or not ids <= set(allowed_connections):
            return {"status": "changed"}  # no preview: it would disclose unauthorized connections
    if current["management_missing"]:
        raise CrowdSecError("CrowdSec management credentials are not configured on: " + ", ".join(current["management_missing"]), 409)
    if sorted(d["key"] for d in current["decisions"]) != sorted(confirmed_keys):
        return {"status": "changed", "preview": current}
    return {"status": "ready", "preview": current}


def execute(
    client,
    ip: str,
    ban_scope: str,
    service: Optional[str],
    confirmed_keys: list[str],
    allowed_connections: Optional[set[str]] = None,
    db=None,
    redis_client=None,
    actor: str = "",
) -> dict:
    """Single item: revalidate, then apply."""
    checked = revalidate(client, ip, ban_scope, service, confirmed_keys, allowed_connections, redis_client=redis_client)
    if checked["status"] != "ready":
        return checked
    return apply(client, ip, ban_scope, service, checked["preview"], db=db, actor=actor)


def _removal_plan(current: dict) -> tuple[dict[str, list[str]], list[str]]:
    """(``lease_id`` values per instance, ``lease_id`` values seen only in Redis).

    An instance removes the ids it reported, never another instance's. A lease seen only in Redis goes to the first up
    instance, whose Redis half deletes it.
    """
    plan: dict[str, list[str]] = {}
    for lease in current["leases"]:
        if lease["source"] != "redis":
            plan.setdefault(lease["source"], []).append(lease["lease_id"])
    held = set(chain.from_iterable(plan.values()))
    return plan, [lease["lease_id"] for lease in current["leases"] if lease["source"] == "redis" and lease["lease_id"] not in held]


def apply(client, ip: str, ban_scope: str, service: Optional[str], current: dict, db=None, actor: str = "") -> dict:
    """Mutations only, on an already revalidated preview. Batch callers revalidate every item first, then apply each.

    Order: delete the ban decisions, refresh the IP on every serving connection, check no ban decision is left, remove
    the lease on every instance, and only then revoke it in the database (``db.revoke_lease``, which answers "" both for a
    revoke and for no match: it is idempotent, the instances decide ``changed``).
    """
    result = {
        "status": "success",
        "deleted": [],
        "already_absent": [],
        "failed": [],
        "refreshed": [],
        "lease_removed": [],
        "lease_absent": [],
        "lease_changed": [],
        "lease_failed": [],
        "down": [],
        "db_revoked": [],
        "db_failed": [],
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

    plan, redis_only = _removal_plan(current)
    instances = client._instances()
    first_up = next((instance.get("hostname") for instance in instances if _up(instance)), None)
    if redis_only and first_up is not None:
        plan.setdefault(first_up, []).extend(redis_only)
    for instance in instances:
        host = instance.get("hostname")
        if not _up(instance):
            result["down"].append(host)
            continue
        for lease_id in plan.get(host, []):
            try:
                outcome = client.remove_lease(instance, ip, ban_scope, service, lease_id)
            except CrowdSecError as exc:
                result["lease_failed"].append({"instance": host, "error": str(exc)})
                continue
            if outcome == "changed":
                result["lease_changed"].append({"instance": host, "lease_id": lease_id})
            else:
                result["lease_absent" if outcome == "absent" else "lease_removed"].append(host)
    if redis_only and first_up is None:
        result["lease_failed"].append({"instance": "redis", "error": "no BunkerWeb instance is up to remove the Redis ban"})

    # Last: the tombstone only means something once the instances were asked. A replaced lease keeps its new row.
    if db is not None:
        changed = {entry["lease_id"] for entry in result["lease_changed"]}
        for lease_id in sorted({lease["lease_id"] for lease in current["leases"]} - changed):
            error = db.revoke_lease(ip, ban_scope=ban_scope, service_id=service or "", lease_id=lease_id, revoked_by=actor)
            if error:
                result["db_failed"].append({"lease_id": lease_id, "error": str(error)})
            else:
                result["db_revoked"].append(lease_id)
    if result["lease_changed"] and not result["lease_removed"]:
        result["status"] = "changed"
    elif result["lease_changed"] or result["lease_failed"] or result["db_failed"] or result["unavailable"] or result["down"]:
        result["status"] = "partial"
    return result
