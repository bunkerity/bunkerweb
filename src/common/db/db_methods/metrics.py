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
        "date": int(row.date.timestamp()),  # epoch seconds, matching the Lua report contract the UI consumes
        "ip": row.ip,
        "country": row.country,
        "method": row.method,
        "url": row.url,
        "status": row.status,
        "user_agent": row.user_agent,
        "reason": row.reason,
        "server_name": row.server_name,
        "data": loads(row.data) if row.data else None,
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
