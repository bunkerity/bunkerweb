#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from json import dumps, loads
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError

from model import Requests  # type: ignore

from .common import DatabaseMixinBase, retry_on_transient_db_errors

# Columns the UI/API may sort by; anything else falls back to ``date``.
_ORDER_COLUMNS = {
    "date": Requests.date,
    "ip": Requests.ip,
    "country": Requests.country,
    "method": Requests.method,
    "url": Requests.url,
    "status": Requests.status,
    "reason": Requests.reason,
    "server_name": Requests.server_name,
    "security_mode": Requests.security_mode,
}
# Facet / search-pane fields (also the columns a faceted filter may target).
_FACET_COLUMNS = {
    "ip": Requests.ip,
    "country": Requests.country,
    "method": Requests.method,
    "url": Requests.url,
    "status": Requests.status,
    "reason": Requests.reason,
    "server_name": Requests.server_name,
    "security_mode": Requests.security_mode,
}
# Text columns scanned by a free-text search (status is matched numerically).
_SEARCH_COLUMNS = (
    Requests.ip,
    Requests.country,
    Requests.method,
    Requests.url,
    Requests.reason,
    Requests.server_name,
    Requests.user_agent,
    Requests.security_mode,
)


def _to_datetime(value: Any) -> datetime:
    """Coerce a metrics record ``date`` (Unix epoch int/float, datetime, or string) to an aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        with suppress(ValueError):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        with suppress(ValueError):
            return datetime.fromisoformat(value)
    return datetime.now().astimezone()


def _row_to_dict(row: Requests) -> Dict[str, Any]:
    """Serialize a row into the report shape the API/UI consume (``id`` aliases ``request_id``;
    ``data`` is deserialized back from its stored JSON text)."""
    return {
        "id": row.request_id,
        "request_id": row.request_id,
        "instance_hostname": row.instance_hostname,
        # epoch seconds, matching the Lua report contract the UI consumes. _to_datetime() re-applies
        # UTC when the driver drops tzinfo on read-back (SQLite/MySQL/MariaDB return a naive datetime
        # for a UTC wall-clock value; a bare .timestamp() would then apply the local system timezone).
        "date": int(_to_datetime(row.date).timestamp()),
        "ip": row.ip,
        "country": row.country,
        "method": row.method,
        "url": row.url,
        "status": row.status,
        "user_agent": row.user_agent,
        "reason": row.reason,
        "server_name": row.server_name,
        "data": loads(row.data) if row.data else None,
        "asn_number": row.asn_number,
        "asn_org": row.asn_org,
        "security_mode": row.security_mode,
    }


def _build_request_row(request_id: str, record: Dict[str, Any], instance_hostname: str, created_at: datetime) -> Requests:
    """Build a ``Requests`` row from a scraped record. ``data`` (the WAF detail blob, a dict in the
    Lua payload) is stored as JSON text so it round-trips back to a dict on read."""
    raw_data = record.get("data")
    return Requests(
        request_id=request_id,
        instance_hostname=instance_hostname,
        date=_to_datetime(record.get("date")),
        ip=str(record.get("ip") or ""),
        country=str(record.get("country") or ""),
        method=str(record.get("method") or ""),
        url=str(record.get("url") or ""),
        status=int(record.get("status") or 0),
        user_agent=record.get("user_agent"),
        reason=str(record.get("reason") or ""),
        server_name=str(record.get("server_name") or ""),
        data=dumps(raw_data) if raw_data not in (None, "") else None,
        asn_number=record.get("asn_number"),
        asn_org=record.get("asn_org"),
        security_mode=str(record.get("security_mode") or ""),
        created_at=created_at,
    )


def _report_clause():
    """A row is a report when it was blocked (4xx) or merely detected (any status)."""
    return or_(and_(Requests.status >= 400, Requests.status < 500), Requests.security_mode == "detect")


def _filter_conditions(search: str = "", filters: Optional[Dict[str, List[str]]] = None) -> list:
    """WHERE clauses selecting reports, narrowed by free-text ``search`` and faceted ``filters``."""
    conditions = [_report_clause()]
    if search:
        like = f"%{search}%"
        clauses = [col.ilike(like) for col in _SEARCH_COLUMNS]
        token = search.strip()
        if token.isdigit():
            clauses.append(Requests.status == int(token))
        conditions.append(or_(*clauses))
    if filters:
        for field, values in filters.items():
            col = _FACET_COLUMNS.get(field)
            if col is not None and values:
                conditions.append(col.in_(values))
    return conditions


def _filtered_select(search: str = "", filters: Optional[Dict[str, List[str]]] = None):
    """``SELECT`` over reports, narrowed by free-text ``search`` and faceted ``filters``."""
    return select(Requests).where(*_filter_conditions(search, filters))


class DatabaseMetricsMixin(DatabaseMixinBase):
    """Blocked-request reports persistence (``bw_metrics_requests``)."""

    @retry_on_transient_db_errors
    def batch_upsert_metrics_requests(self, records: List[Dict[str, Any]], *, instance_hostname: str = "") -> str:
        """Insert blocked-request report rows, skipping any ``(instance_hostname, request_id)`` already
        stored (idempotent re-scrape) and collapsing duplicates within the batch. Returns "" on success.

        The periodic scrape job is the single writer per instance; a rare concurrent insert that races
        the existence check is absorbed by re-querying and re-inserting only the still-missing remainder
        (rather than aborting the whole batch on the unique-constraint violation)."""
        if not records:
            return ""

        # collapse duplicates within the batch (last record for an id wins)
        by_id: Dict[str, Dict[str, Any]] = {}
        for record in records:
            rid = str(record.get("id") or record.get("request_id") or "")
            if rid:
                by_id[rid] = record
        if not by_id:
            return ""

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            now = datetime.now().astimezone()
            ids = list(by_id.keys())
            last_error = ""
            # Two attempts: on a concurrent unique-conflict, re-query the stored ids (now including the
            # racing rows) and re-insert only the remainder, so one conflict never drops the whole batch.
            for _attempt in (1, 2):
                existing = set(
                    session.scalars(select(Requests.request_id).where(Requests.instance_hostname == instance_hostname, Requests.request_id.in_(ids))).all()
                )
                to_add = [_build_request_row(rid, by_id[rid], instance_hostname, now) for rid in ids if rid not in existing]
                if not to_add:
                    return ""
                session.add_all(to_add)
                try:
                    session.commit()
                    return ""
                except IntegrityError as e:
                    session.rollback()
                    last_error = str(e)
                except BaseException as e:
                    return str(e)
        # both attempts hit a persistent unique conflict (abnormal for a single writer) — surface it
        # rather than reporting a silent success that hides un-inserted rows / a real constraint bug.
        return last_error or "metrics batch upsert: unresolved unique conflict after retry"

    @retry_on_transient_db_errors
    def get_metrics_requests(
        self,
        *,
        start: int = 0,
        length: int = 10,
        search: str = "",
        order_column: str = "date",
        order_dir: str = "desc",
        filters: Optional[Dict[str, List[str]]] = None,
        count_only: bool = False,
    ) -> Dict[str, Any]:
        """Return persisted reports as ``{total, filtered, data}``.

        ``total`` is every stored row; ``filtered`` is the count after the report clause,
        ``search`` and ``filters`` (ignoring pagination); ``data`` is the requested page.
        """
        with self._db_session() as session:
            total = session.scalar(select(func.count()).select_from(Requests)) or 0
            stmt = _filtered_select(search, filters)
            filtered = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            if count_only:
                return {"total": total, "filtered": filtered, "data": []}

            column = _ORDER_COLUMNS.get(order_column, Requests.date)
            stmt = stmt.order_by(column.asc() if order_dir == "asc" else column.desc())
            if length is not None and length >= 0:
                stmt = stmt.offset(max(0, start)).limit(length)
            rows = session.scalars(stmt).all()
            return {"total": total, "filtered": filtered, "data": [_row_to_dict(row) for row in rows]}

    @retry_on_transient_db_errors
    def get_metrics_facets(self, *, search: str = "", filters: Optional[Dict[str, List[str]]] = None) -> Dict[str, Dict[Any, Dict[str, int]]]:
        """Per-field search-pane facet counts: ``{field: {value: {"total": N, "count": M}}}``.

        Faithful to the metrics Lua endpoint (``metrics.lua:772-785``), replacing the per-instance Redis
        facet hashes with SQL ``GROUP BY``:
          * ``total`` counts the whole report set, ignoring ``search`` and all pane selections;
          * ``count`` counts the currently-shown set — report clause + ``search`` + **all** panes (a
            field's own selection included, exactly like the Lua ``filtered_ids`` gate). ``total`` keeps
            every value visible while ``count`` reflects the active filter.
        """
        report_only = _report_clause()
        filtered = _filter_conditions(search, filters)
        facets: Dict[str, Dict[Any, Dict[str, int]]] = {}
        with self._db_session() as session:
            for field, column in _FACET_COLUMNS.items():
                totals = dict(session.execute(select(column, func.count()).where(report_only).group_by(column)).all())
                counts = dict(session.execute(select(column, func.count()).where(*filtered).group_by(column)).all())
                facets[field] = {value: {"total": total, "count": counts.get(value, 0)} for value, total in totals.items()}
        return facets

    @retry_on_transient_db_errors
    def get_metrics_timeseries(
        self,
        *,
        start: int,
        end: int,
        bucket: str = "hour",
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Time-bucketed report counts over ``[start, end)`` (Unix epoch seconds), plus the same
        count over the immediately-preceding equal-length window for a period-over-period trend
        delta. Bucketing is done in Python rather than per-engine SQL (``date_trunc``/
        ``DATE_FORMAT``/``strftime``) to stay portable across all 4 supported engines — the query
        itself is bounded by the date range, not the whole table, but every matching row's ``date``
        is still materialized into Python to bucket it: O(rows-in-range), not O(buckets). Fine for
        dashboard-sized windows (hours/days); a "last 30 days" pull on a high-traffic WAF table can
        still be a large scan — if that shows up as slow, move the bucketing to per-engine SQL
        (``date_trunc``/``DATE_FORMAT``/``strftime``) instead.

        ``bucket`` accepts ``"hour"``; anything else (including typos) is treated as ``"day"``.
        """
        bucket_seconds = 3600 if bucket == "hour" else 86400
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        window = end - start
        prev_start_dt = datetime.fromtimestamp(start - window, tz=timezone.utc)

        conditions = _filter_conditions("", filters) + [Requests.date >= start_dt, Requests.date < end_dt]
        prev_conditions = _filter_conditions("", filters) + [Requests.date >= prev_start_dt, Requests.date < start_dt]

        with self._db_session() as session:
            dates = session.scalars(select(Requests.date).where(*conditions)).all()
            prev_total = session.scalar(select(func.count()).select_from(select(Requests).where(*prev_conditions).subquery())) or 0

        bucket_count = max(1, -(-window // bucket_seconds))  # ceil division
        counts = [0] * bucket_count
        for d in dates:
            # SQLite drops tzinfo on read-back (returns a naive datetime representing UTC wall-clock
            # time); .timestamp() on a naive datetime uses the local system timezone, which would
            # silently shift every bucket index outside UTC. _to_datetime() (below) already carries
            # this exact "treat naive as UTC" fix for the write path — reuse it here for reads.
            idx = int((_to_datetime(d).timestamp() - start) // bucket_seconds)
            if 0 <= idx < bucket_count:
                counts[idx] += 1

        total = len(dates)
        trend_pct = round(((total - prev_total) / prev_total) * 100, 1) if prev_total else None
        return {
            "buckets": [start + i * bucket_seconds for i in range(bucket_count)],
            "counts": counts,
            "total": total,
            "prev_total": prev_total,
            "trend_pct": trend_pct,
        }

    @retry_on_transient_db_errors
    def get_metrics_top_offenders(
        self,
        *,
        start: int,
        end: int,
        limit: int = 10,
        filters: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Top attacker IPs in ``[start, end)`` by block count, with country/ASN attribution
        (``None`` for rows predating the ASN migration), the most frequent block reason, and
        first/last-seen timestamps."""
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        conditions = _filter_conditions("", filters) + [Requests.date >= start_dt, Requests.date < end_dt]

        with self._db_session() as session:
            rows = session.execute(
                select(Requests.ip, Requests.country, Requests.asn_number, Requests.asn_org, Requests.reason, Requests.date).where(*conditions)
            ).all()

        by_ip: Dict[str, Dict[str, Any]] = {}
        for ip, country, asn_number, asn_org, reason, date in rows:
            entry = by_ip.setdefault(
                ip,
                {"ip": ip, "country": country, "asn_number": asn_number, "asn_org": asn_org, "blocks": 0, "reasons": {}, "first_seen": date, "last_seen": date},
            )
            # asn_number/asn_org are nullable and only populated post-ASN-migration (NULL on older
            # rows); country is NOT NULL but can still be "" (unset) pre-lookup. Row order across
            # engines is unspecified (no ORDER BY), so coalesce instead of trusting whichever row
            # landed first — once a truthy value is seen for an IP it's kept, and a later truthy
            # value backfills a still-empty field. Makes attribution order-independent by construction.
            entry["country"] = entry["country"] or country
            entry["asn_number"] = entry["asn_number"] or asn_number
            entry["asn_org"] = entry["asn_org"] or asn_org
            entry["blocks"] += 1
            entry["reasons"][reason] = entry["reasons"].get(reason, 0) + 1
            entry["first_seen"] = min(entry["first_seen"], date)
            entry["last_seen"] = max(entry["last_seen"], date)

        offenders = [
            {
                "ip": entry["ip"],
                "country": entry["country"],
                "asn_number": entry["asn_number"],
                "asn_org": entry["asn_org"],
                "blocks": entry["blocks"],
                "top_reason": max(entry["reasons"].items(), key=lambda kv: kv[1])[0],
                # _to_datetime() re-applies UTC when the driver drops tzinfo on read-back (see the
                # module docstring note on _row_to_dict's "date" field / get_metrics_timeseries above) —
                # a bare .timestamp() on a naive datetime would silently apply the host's local timezone.
                "first_seen": int(_to_datetime(entry["first_seen"]).timestamp()),
                "last_seen": int(_to_datetime(entry["last_seen"]).timestamp()),
            }
            for entry in by_ip.values()
        ]
        offenders.sort(key=lambda o: o["blocks"], reverse=True)
        return offenders[:limit]

    @retry_on_transient_db_errors
    def get_metrics_top_rules(self, *, start: int, end: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Most-frequently-fired ModSecurity rule IDs in ``[start, end)``, tallied from the
        ``data.ids`` JSON array each modsecurity-reason row carries (see ``utils.get_reason`` in
        ``utils.lua``). Non-modsecurity rows carry no ``ids`` and are skipped."""
        start_dt = datetime.fromtimestamp(start, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(end, tz=timezone.utc)
        conditions = [Requests.reason == "modsecurity", Requests.date >= start_dt, Requests.date < end_dt]

        with self._db_session() as session:
            blobs = session.scalars(select(Requests.data).where(*conditions)).all()

        tally: Dict[str, int] = {}
        for blob in blobs:
            if not blob:
                continue
            try:
                parsed = loads(blob)
            except (TypeError, ValueError):
                continue
            for rule_id in (parsed or {}).get("ids", []) or []:
                tally[str(rule_id)] = tally.get(str(rule_id), 0) + 1

        ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
        return [{"rule_id": rule_id, "count": count} for rule_id, count in ranked[:limit]]

    @retry_on_transient_db_errors
    def cleanup_metrics_by_age(self, days: int) -> str:
        """Delete reports older than ``days``. Returns ``"Removed N metrics requests by age"``."""
        removed = 0
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            cutoff = datetime.now().astimezone() - timedelta(days=days)
            removed = session.execute(delete(Requests).where(Requests.date < cutoff), execution_options={"synchronize_session": False}).rowcount
            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return f"Removed {removed} metrics requests by age"

    @retry_on_transient_db_errors
    def cleanup_metrics_by_count(self, max_rows: int) -> str:
        """Keep only the ``max_rows`` newest reports. Returns ``"Removed N metrics requests by count"``."""
        removed = 0
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            rows_count = session.scalar(select(func.count()).select_from(Requests)) or 0
            if rows_count > max_rows:
                ids_to_delete = session.scalars(select(Requests.id).order_by(Requests.date.asc()).limit(rows_count - max_rows)).all()
                if ids_to_delete:
                    removed = session.execute(delete(Requests).where(Requests.id.in_(ids_to_delete)), execution_options={"synchronize_session": False}).rowcount
                try:
                    session.commit()
                except BaseException as e:
                    return str(e)
        return f"Removed {removed} metrics requests by count"
