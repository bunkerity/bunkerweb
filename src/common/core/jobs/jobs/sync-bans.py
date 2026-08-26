#!/usr/bin/env python3

"""Converge the durable ban store with what the fleet is actually enforcing.

One pass, in order: **learn → re-unban → project → purge**.

The database is the source of truth. Each instance's shared dict is a local enforcement cache and
Redis is an optional distributed projection; both are rebuilt from here, never the other way round.
"""

from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from math import ceil
from os import getenv, sep
from os.path import join
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from common_utils import get_redis_client  # type: ignore
from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("JOBS.SYNC-BANS")
exit_status = 0


def exp_for_wire(expires_at, now):
    """Seconds to put in a ``POST /ban``.

    ``exp == 0`` means *permanent* on the wire (``utils.add_ban``), so a ban 0.4s from expiry must
    never round down to 0 — that would promote it to permanent on every instance we push it to.
    """
    if not expires_at:
        return 0
    return max(1, ceil(expires_at - now))


def ban_key(ban):
    return f"bans_service_{ban['service']}_ip_{ban['ip']}" if ban["ban_scope"] == "service" else f"bans_ip_{ban['ip']}"


def redis_value(ban):
    """The exact JSON the Lua side decodes (``utils.is_banned``, ``ban_sync.build_snapshot``).

    A missing ``permanent`` flips a permanent ban into an expiring one, so the key set is pinned by
    a unit test rather than left to drift.
    """
    return dumps(
        {
            "reason": ban["reason"],
            "service": ban["service"],
            "date": ban["date"],
            "country": ban["country"],
            "ban_scope": ban["ban_scope"],
            "reason_data": ban["reason_data"],
            "permanent": ban["permanent"],
            "expires_at": ban["expires_at"],
        }
    )


def records_from_redis(redis_client):
    """Bans held in Redis, in the same record shape the instances report."""
    records = []
    for pattern, scope in (("bans_ip_*", "global"), ("bans_service_*_ip_*", "service")):
        for key in redis_client.scan_iter(pattern):
            key_str = key.decode("utf-8", "replace") if isinstance(key, bytes) else key
            if scope == "global":
                service, ip = "", key_str.replace("bans_ip_", "")
            else:
                service, ip = key_str.replace("bans_service_", "").rsplit("_ip_", 1)
            data = redis_client.get(key)
            if not data:
                continue
            try:
                ban_data = loads(data.decode("utf-8", "replace") if isinstance(data, bytes) else data)
            except (JSONDecodeError, ValueError):
                LOGGER.warning(f"Ignoring undecodable Redis ban {key_str}")
                continue
            ban_data["ip"] = ip
            ban_data["ban_scope"] = scope
            ban_data["service"] = service or ban_data.get("service", "")
            ban_data["origin"] = "redis"
            records.append(ban_data)
    return records


def identity_payload(identity):
    payload = {"ip": identity["ip"], "ban_scope": identity["ban_scope"]}
    if identity["ban_scope"] == "service" and identity["service"]:
        payload["service"] = identity["service"]
    return payload


def project_bans(active, callers, reported, redis_client, now):
    """Write the active bans out to wherever enforcement reads them. Returns ``(count, failures)``.

    **Under Redis, the instances are never pushed to.** They materialize a Redis ban into their own
    shared dict lazily, when ``is_banned`` first sees that IP (``utils.lua``), so bans that are
    missing from most shared dicts is the *healthy* state — not a gap to fill. Pushing anyway would
    run on every pass, reset each ban's ``date`` to ``os.time()`` on every target (``POST /ban`` in
    ``utils.add_ban``), and grow every instance's 64 MB datastore until ``set_with_retries`` gives
    up. This branch is not an optimization; removing it breaks the fleet.
    """
    projected = 0
    failures = 0

    if redis_client:
        for ban in active:
            ttl = exp_for_wire(ban["expires_at"], now)
            if ttl:
                redis_client.set(ban_key(ban), redis_value(ban), ex=ttl)
            else:
                redis_client.set(ban_key(ban), redis_value(ban))
            projected += 1
        return projected, failures

    # No Redis: each instance holds its own copy, so push what it is missing. In steady state the
    # diff is empty; after a restart the diff is the whole set, which is the restore. The empty
    # shared dict is the signal — no restart detector, no epoch bookkeeping.
    for hostname, caller in callers.items():
        known = {identity_of(record) for record in reported.get(hostname, [])}
        for ban in active:
            if identity_of(ban) in known:
                continue
            data = {
                "ip": ban["ip"],
                "exp": exp_for_wire(ban["expires_at"], now),
                "reason": ban["reason"],
                "service": ban["service"],
                "ban_scope": ban["ban_scope"],
            }
            push_ok, _ = caller.send_to_apis("POST", "/ban", data=data)
            if not push_ok:
                LOGGER.error(f"Couldn't restore the ban of {ban['ip']} on {hostname}")
                failures += 1
                continue
            projected += 1
    return projected, failures


def identity_of(ban):
    """``(ip, scope, service)`` with the service dropped for a global ban — instances report a
    placeholder there (``unknown``, ``bwcli``, the service that triggered it), so comparing it
    would make every global ban look missing and re-push it every pass."""
    return (ban.get("ip"), ban.get("ban_scope", "global"), ban.get("service", "") if ban.get("ban_scope") == "service" else "")


try:
    JOB = Job(LOGGER, __file__)

    db_metadata = JOB.db.get_metadata()
    if isinstance(db_metadata, str) or db_metadata["scheduler_first_start"]:
        LOGGER.info("First start of the scheduler, skipping ban convergence...")
        sys_exit(0)

    use_redis = getenv("USE_REDIS", "no") == "yes"
    redis_client = None
    if use_redis:
        redis_client = get_redis_client(
            use_redis=True,
            redis_host=getenv("REDIS_HOST"),
            redis_port=getenv("REDIS_PORT", "6379"),
            redis_db=getenv("REDIS_DATABASE", "0"),
            redis_timeout=getenv("REDIS_TIMEOUT", "1000.0"),
            redis_keepalive_pool=getenv("REDIS_KEEPALIVE_POOL", "10"),
            redis_ssl=getenv("REDIS_SSL", "no") == "yes",
            redis_ssl_ca=getenv("REDIS_SSL_CA") or None,
            redis_username=getenv("REDIS_USERNAME") or None,
            redis_password=getenv("REDIS_PASSWORD") or None,
            redis_sentinel_hosts=getenv("REDIS_SENTINEL_HOSTS", []),
            redis_sentinel_username=getenv("REDIS_SENTINEL_USERNAME") or None,
            redis_sentinel_password=getenv("REDIS_SENTINEL_PASSWORD") or None,
            redis_sentinel_master=getenv("REDIS_SENTINEL_MASTER", ""),
            logger=LOGGER,
        )
        if not redis_client:
            LOGGER.error("USE_REDIS is set but Redis is unreachable, falling back to instance projection this pass")

    # Only healthy instances take part: a "failover" instance runs a config we do not trust, so
    # neither its ban list nor a push to it means anything.
    instances = [instance for instance in (JOB.db.get_instances(with_credential=True) or []) if instance.get("status") == "up"]
    callers = {instance["hostname"]: ApiCaller([API.from_instance(instance)]) for instance in instances}

    # ── 1. Learn ────────────────────────────────────────────────────────────────────────────────
    # Everything the fleet is enforcing that the database does not know about yet. Redis is just
    # another learn source, every pass — which is also why upgrading from 1.6.x needs no import
    # step: the first pass absorbs whatever was already there.
    learned = 0
    reported = {}
    for hostname, caller in callers.items():
        ok, responses = caller.send_to_apis("GET", "/bans", response=True)
        # One API per caller, and send_to_apis keys the response by the endpoint's host, which is
        # not always the registered hostname — take the single value rather than guessing the key.
        payload = next(iter((responses or {}).values()), None)
        if not ok or not isinstance(payload, dict):
            LOGGER.warning(f"Couldn't read bans from {hostname}, skipping it this pass")
            continue
        records = payload.get("data") or []
        reported[hostname] = records
        inserted, tombstoned = JOB.db.learn_bans(records)
        learned += len(inserted)

        # ── 2. Re-unban ─────────────────────────────────────────────────────────────────────────
        # This instance still enforces a ban the operator revoked: its API path was down when the
        # unban went out, and NGINX kept serving. Without this, the ban would be re-learned and
        # re-pushed to the whole fleet for the rest of its lifetime.
        for identity in tombstoned:
            unban_ok, _ = caller.send_to_apis("POST", "/unban", data=identity_payload(identity))
            if not unban_ok:
                LOGGER.error(f"Couldn't replay the unban of {identity['ip']} on {hostname}")
                exit_status = 2

    if redis_client:
        redis_records = records_from_redis(redis_client)
        inserted, tombstoned = JOB.db.learn_bans(redis_records)
        learned += len(inserted)
        for identity in tombstoned:
            redis_client.delete(ban_key(identity))

    # ── 3. Project ──────────────────────────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc).timestamp()
    active = JOB.db.get_bans()
    projected, failures = project_bans(active, callers, reported, redis_client, now)
    if failures:
        exit_status = 2

    # ── 4. Purge ────────────────────────────────────────────────────────────────────────────────
    # Tombstones outlive the longest ban plus plausible downtime, then go.
    purge_error = JOB.db.purge_bans()
    if purge_error:
        LOGGER.error(f"Couldn't purge expired bans: {purge_error}")
        exit_status = 2

    LOGGER.info(f"Ban convergence done: {len(active)} active, {learned} learned, {projected} projected.")
except SystemExit as e:
    exit_status = e.code
except BaseException as e:
    exit_status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running sync-bans.py :\n{e}")

sys_exit(exit_status)
