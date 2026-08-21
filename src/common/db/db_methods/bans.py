#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from json import dumps, loads
from math import ceil
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from model import Bans  # type: ignore

from .common import DatabaseMixinBase, retry_on_transient_db_errors
from .metrics import MAX_TIMESERIES_BUCKETS, _safe_epoch_to_datetime

# reason_data crosses a trust boundary: it is built on the instance (badbehavior ships per-IP
# counters through it) and scraped back here. Cap it rather than storing unbounded JSON.
MAX_REASON_DATA = 4096

# How long a revoked or expired row is kept as a tombstone. It has to outlive the longest ban we
# hand out (BAD_BEHAVIOR_BAN_TIME, 24h by default) plus plausible instance downtime, otherwise an
# instance that was offline resurrects the ban when it comes back and re-teaches it to the cluster.
TOMBSTONE_RETENTION_DAYS = 30


def normalize_ip(value: Any) -> str:
    """Canonical text form of an IP, matching what NGINX puts in ``$remote_addr``.

    The runtime builds its shm key from that form, so an uncompressed ``2001:0DB8::1`` stored here
    would never match the ban the instance is actually enforcing. Returns "" when unparseable.
    """
    with suppress(ValueError):
        return str(ip_address(str(value).strip()))
    return ""


def _now() -> datetime:
    """Everything on this table is stored in UTC. SQLite/MySQL/MariaDB hand a *naive* datetime back
    on read, so a local-timezone value written here would silently shift by the UTC offset."""
    return datetime.now(timezone.utc)


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    """Re-apply UTC to a datetime the driver returned without tzinfo, so it can be compared."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _aware(value: Any) -> Optional[datetime]:
    """Coerce an epoch / datetime / ISO string to a UTC datetime (None stays None)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        with suppress(ValueError, OverflowError, OSError):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return None
    if isinstance(value, str):
        with suppress(ValueError):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        with suppress(ValueError):
            return datetime.fromisoformat(value)
    return None


def _scope_key(ip: str, ban_scope: str, service_id: str) -> Tuple[str, str, str]:
    """Normalize the identity triple. A global ban always carries ``service_id == ""`` — see the
    model docstring for why that column is never NULL."""
    scope = "service" if ban_scope == "service" and service_id else "global"
    return (ip, scope, service_id if scope == "service" else "")


def _reason_data_text(value: Any) -> Optional[str]:
    """Serialize reason_data to bounded JSON text; drop it entirely when it does not fit."""
    if value in (None, "", {}, []):
        return None
    text = value if isinstance(value, str) else dumps(value, default=str)
    return text if len(text) <= MAX_REASON_DATA else None


def _row_to_dict(row: Bans, now: datetime) -> Dict[str, Any]:
    """Serialize a row into the ban shape the runtime, API and UI already speak
    (``utils.add_ban`` / ``api.lua`` ``GET /bans``), so switching the read source needs no
    consumer change."""
    expires = _utc(row.expires_at)
    permanent = expires is None
    expires_at = 0 if permanent else int(expires.timestamp())
    reason_data: Any = {}
    if row.reason_data:
        with suppress(ValueError, TypeError):
            reason_data = loads(row.reason_data)
    return {
        "ip": row.ip,
        "reason": row.reason,
        "service": row.service_id or "unknown",
        "date": int(_utc(row.created_at).timestamp()),
        "country": row.country,
        "ban_scope": row.ban_scope,
        # Remaining seconds, floored at 0. exp == 0 is how the wire says "permanent", which is why
        # `permanent` is the discriminant consumers must test first.
        "exp": 0 if permanent else max(int((expires - now).total_seconds()), 0),
        "expires_at": expires_at,
        "permanent": permanent,
        "reason_data": reason_data,
    }


def _active_clause(now: datetime):
    """A ban is in force when it was never revoked and has not reached ``expires_at``."""
    return and_(Bans.revoked_at.is_(None), or_(Bans.expires_at.is_(None), Bans.expires_at > now))


class DatabaseBansMixin(DatabaseMixinBase):
    """Durable ban lifecycle (``bw_bans``). The DB is the source of truth; shared dicts and Redis
    are projections. Nothing here is ever called from the request path."""

    @retry_on_transient_db_errors
    def upsert_ban(
        self,
        ip: str,
        *,
        ban_scope: str = "global",
        service_id: str = "",
        reason: str = "",
        reason_data: Any = None,
        country: str = "",
        expires_at: Any = None,
        origin: str = "api",
        created_by: str = "",
    ) -> str:
        """Create or refresh a ban. Idempotent, and clears any tombstone — an operator re-banning
        an IP they previously unbanned is a deliberate reactivation. Returns "" on success."""
        ip = normalize_ip(ip)
        if not ip:
            return "invalid IP address"
        ip, scope, service = _scope_key(ip, ban_scope, service_id)
        expires = _aware(expires_at)
        now = _now()
        if expires is not None and expires <= now:
            return "ban expiration is in the past"

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            row = session.execute(select(Bans).where(Bans.ip == ip, Bans.ban_scope == scope, Bans.service_id == service)).scalar_one_or_none()
            if row is None:
                session.add(
                    Bans(
                        ip=ip,
                        ban_scope=scope,
                        service_id=service,
                        origin=origin,
                        reason=reason,
                        reason_data=_reason_data_text(reason_data),
                        country=country,
                        created_at=now,
                        created_by=created_by,
                        expires_at=expires,
                    )
                )
            else:
                row.origin = origin
                row.reason = reason
                row.reason_data = _reason_data_text(reason_data)
                row.country = country or row.country
                row.created_at = now
                row.created_by = created_by
                row.expires_at = expires
                row.revoked_at = None
                row.revoked_by = None
            try:
                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)
        return ""

    @retry_on_transient_db_errors
    def revoke_ban(self, ip: str, *, ban_scope: str = "global", service_id: str = "", revoked_by: str = "") -> str:
        """Tombstone a ban (the row is kept, ``revoked_at`` is stamped). Returns "" on success.

        A **global** revoke also tombstones every service-scoped row for that IP, mirroring what
        ``utils.remove_ban`` does in Lua: it deletes the global key *and* every
        ``bans_service_*_ip_<ip>``. A tombstone that did not cover the same set would let the next
        convergence pass re-learn and re-push the service bans the operator just cleared.
        """
        ip = normalize_ip(ip)
        if not ip:
            return "invalid IP address"
        ip, scope, service = _scope_key(ip, ban_scope, service_id)
        now = _now()

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            conditions = [Bans.ip == ip, Bans.revoked_at.is_(None)]
            if scope == "service":
                conditions += [Bans.ban_scope == "service", Bans.service_id == service]
            try:
                session.execute(update(Bans).where(*conditions).values(revoked_at=now, revoked_by=revoked_by))
                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)
        return ""

    @retry_on_transient_db_errors
    def get_bans(self, *, include_revoked: bool = False) -> List[Dict[str, Any]]:
        """Every ban in force, in the shape consumers already expect from the instances.

        ponytail: returns the whole set, like the instance fan-out it replaces. At six-figure ban
        counts this wants ``?start=&length=`` pagination — but so does the shared dict it mirrors,
        so paginating here alone would not raise the real ceiling.
        """
        now = _now()
        stmt = select(Bans)
        if not include_revoked:
            stmt = stmt.where(_active_clause(now))
        with self._db_session() as session:
            return [_row_to_dict(row, now) for row in session.scalars(stmt.order_by(Bans.created_at.desc())).all()]

    @retry_on_transient_db_errors
    def get_bans_timeseries(self, *, start: int, end: int, bucket: str = "hour") -> Dict[str, Any]:
        """How many bans were **in force** during each interval of ``[start, end)`` (epoch seconds).

        Not "bans created per interval". ``bw_bans`` holds one row per ``(ip, ban_scope,
        service_id)`` and ``upsert_ban`` rewrites ``created_at`` on the existing row, so a
        re-ban overwrites the original date and a ban/unban/re-ban erases the revocation
        entirely: a creation series would be an event history the table cannot back. What the
        table *can* answer honestly is occupancy — a row counts in every bucket its lifetime
        ``[created_at, revoked_at or expires_at)`` overlaps, and a still-running ban counts to
        the end of the window.

        Bucketing is done in Python for the same reason ``get_metrics_timeseries`` does it: no
        portable ``date_trunc`` across the 4 engines. The ``MAX_TIMESERIES_BUCKETS`` guard and
        ``_safe_epoch_to_datetime`` come from that module verbatim, so a nonsense range is a 400
        at the boundary rather than a 500 or a multi-gigabyte list.

        ponytail: O(rows overlapping the window). ``ix_bw_bans_active`` covers the
        revoked/expires side; a six-figure ban table over a wide window still materializes every
        overlapping row. Move to per-engine SQL if that ever shows up as slow.
        """
        bucket_seconds = 3600 if bucket == "hour" else 86400
        window = end - start
        bucket_count = max(1, -(-window // bucket_seconds))  # ceil division
        if bucket_count > MAX_TIMESERIES_BUCKETS:
            raise ValueError(f"requested range too large: {bucket_count} buckets exceeds {MAX_TIMESERIES_BUCKETS}")

        start_dt = _safe_epoch_to_datetime(start, "start")
        end_dt = _safe_epoch_to_datetime(end, "end")
        prev_start_dt = _safe_epoch_to_datetime(start - window, "start")

        def _overlaps(window_start: datetime, window_end: datetime):
            """Ban lifetime ``[created_at, ended)`` intersects ``[window_start, window_end)``."""
            ended = func.coalesce(Bans.revoked_at, Bans.expires_at)
            return and_(Bans.created_at < window_end, or_(ended.is_(None), ended > window_start))

        with self._db_session() as session:
            rows = session.execute(select(Bans.created_at, Bans.revoked_at, Bans.expires_at).where(_overlaps(start_dt, end_dt))).all()
            prev_total = session.scalar(select(func.count()).select_from(select(Bans.id).where(_overlaps(prev_start_dt, start_dt)).subquery())) or 0

        counts = [0] * bucket_count
        for created_at, revoked_at, expires_at in rows:
            # SQLite/MySQL/MariaDB hand these back without tzinfo; .timestamp() on a naive
            # datetime resolves against the *local* zone, which would shift every bucket index
            # off UTC. _utc() is the same "naive means UTC" fix the write path already carries.
            began = _utc(created_at).timestamp()
            ended = _utc(revoked_at) or _utc(expires_at)
            first = max(0, int((began - start) // bucket_seconds))
            if ended is None:  # still in force -- occupies every remaining bucket
                last = bucket_count - 1
            else:
                # A ban ending exactly on a bucket boundary does NOT occupy that bucket:
                # the interval is half-open on both sides.
                last = min(bucket_count - 1, ceil((ended.timestamp() - start) / bucket_seconds) - 1)
            for index in range(first, last + 1):
                counts[index] += 1

        total = len(rows)
        trend_pct = round(((total - prev_total) / prev_total) * 100, 1) if prev_total else None
        return {
            "buckets": [start + i * bucket_seconds for i in range(bucket_count)],
            "counts": counts,
            "total": total,
            "prev_total": prev_total,
            "trend_pct": trend_pct,
        }

    @retry_on_transient_db_errors
    def learn_bans(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Absorb bans observed on an instance (or in Redis) into the durable store.

        Returns ``(inserted, tombstoned)``. A record is **tombstoned** when it — or the global ban
        covering the same IP — was revoked *after* the instance recorded it: that is the operator
        unban which never reached this instance, and the caller must push it back as a
        ``POST /unban`` instead of letting the ban be re-learned.

        Learning never clears a tombstone on its own; only a record that post-dates the revocation
        reactivates the row, and it does so through a guarded UPDATE so a concurrent operator
        revoke cannot be lost in a read-then-write window.

        ponytail: ``record["date"]`` is the instance's ``os.time()`` compared against control-plane
        timestamps. An instance running minutes behind can have a legitimate re-ban suppressed for
        one pass; it self-heals because badbehavior's counter is not cleared on a failed ban.
        """
        inserted: List[Dict[str, Any]] = []
        tombstoned: List[Dict[str, Any]] = []
        if not records:
            return inserted, tombstoned

        with self._db_session() as session:
            if self.readonly:
                return inserted, tombstoned

            now = _now()
            for record in records:
                ip = normalize_ip(record.get("ip"))
                if not ip:
                    continue
                service_id = record.get("service") or ""
                if service_id in ("unknown", "_"):
                    service_id = ""
                ip, scope, service = _scope_key(ip, record.get("ban_scope") or "global", service_id)
                seen_at = _aware(record.get("date")) or now
                expires = None if record.get("permanent") else _aware(record.get("expires_at"))
                identity = {"ip": ip, "ban_scope": scope, "service": service}

                rows = session.scalars(select(Bans).where(Bans.ip == ip, or_(Bans.ban_scope == "global", Bans.service_id == service))).all()
                own = next((r for r in rows if r.ban_scope == scope and r.service_id == service), None)
                # A revoked global ban also covers service-scoped records: the Lua unban wiped both.
                covering = next((r for r in rows if r.ban_scope == "global" and _utc(r.revoked_at) is not None and _utc(r.revoked_at) >= seen_at), None)

                if covering is not None and own is not covering:
                    tombstoned.append(identity)
                    continue
                if own is not None:
                    own_revoked_at = _utc(own.revoked_at)
                    if own_revoked_at is None:
                        continue  # already known and active
                    if own_revoked_at >= seen_at:
                        tombstoned.append(identity)
                        continue
                    # Revoked before the instance recorded this ban → a genuine re-ban. The guard
                    # makes the reactivation a no-op if the row was revoked again meanwhile.
                    result = session.execute(
                        update(Bans)
                        .where(Bans.id == own.id, Bans.revoked_at.is_not(None), Bans.revoked_at < seen_at)
                        .values(
                            revoked_at=None,
                            revoked_by=None,
                            created_at=seen_at,
                            expires_at=expires,
                            reason=record.get("reason") or "",
                            reason_data=_reason_data_text(record.get("reason_data")),
                            country=record.get("country") or own.country,
                            origin=record.get("origin") or "instance",
                        )
                        .execution_options(synchronize_session=False)
                    )
                    if result.rowcount:
                        inserted.append(identity)
                    else:
                        tombstoned.append(identity)
                    continue

                try:
                    # SAVEPOINT: a unique conflict on one record must not roll back the records
                    # already learned in this batch.
                    with session.begin_nested():
                        session.add(
                            Bans(
                                ip=ip,
                                ban_scope=scope,
                                service_id=service,
                                origin=record.get("origin") or "instance",
                                reason=record.get("reason") or "",
                                reason_data=_reason_data_text(record.get("reason_data")),
                                country=record.get("country") or "",
                                created_at=seen_at,
                                created_by="",
                                expires_at=expires,
                            )
                        )
                    inserted.append(identity)
                except IntegrityError:
                    # Another writer inserted the same identity between the SELECT and here. Its
                    # row wins; re-read it so a revoke that just landed is honoured.
                    existing = session.execute(select(Bans).where(Bans.ip == ip, Bans.ban_scope == scope, Bans.service_id == service)).scalar_one_or_none()
                    existing_revoked_at = _utc(existing.revoked_at) if existing is not None else None
                    if existing_revoked_at is not None and existing_revoked_at >= seen_at:
                        tombstoned.append(identity)

            try:
                session.commit()
            except BaseException as e:
                session.rollback()
                self.logger.error(f"Couldn't persist learned bans: {e}")
                return [], tombstoned
        return inserted, tombstoned

    @retry_on_transient_db_errors
    def purge_bans(self, retention_days: int = TOMBSTONE_RETENTION_DAYS) -> str:
        """Drop tombstones and expired rows older than ``retention_days``. Returns "" on success."""
        cutoff = _now() - timedelta(days=max(1, retention_days))
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            try:
                session.execute(delete(Bans).where(or_(Bans.revoked_at < cutoff, and_(Bans.expires_at.is_not(None), Bans.expires_at < cutoff))))
                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)
        return ""
