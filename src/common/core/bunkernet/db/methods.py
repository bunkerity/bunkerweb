#!/usr/bin/env python3
"""Plugin-shipped DB query helpers for the BunkerNet effectiveness pilot.

Auto-discovered by the 1.7 plugin DB-extension mechanism and reachable from routers
and jobs as ``db.ext("bunkernet").<method>()``. Subclasses ``DatabaseMixinBase`` so it
reuses the core ``_db_session``/``readonly``/``@retry_on_transient_db_errors`` machinery
of the live ``Database`` it is bound to — exactly like the built-in ``db_methods`` mixins.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, select

from db_methods.common import DatabaseMixinBase, retry_on_transient_db_errors  # type: ignore
from model import Requests  # type: ignore  # core metrics table, joined for the "blocks" side

from .models import BunkernetStats

# Metrics whose latest bucket value is what the dashboard wants ("how many pending",
# "how big is the blocklist") rather than a sum over time.
_LATEST_METRICS = ("reports_pending", "blocklist_size", "registered")
# Metrics that accumulate and are summed over the window.
_SUM_METRICS = ("reports_sent",)


def _floor_hour(value: Optional[datetime] = None) -> datetime:
    value = value or datetime.now().astimezone()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.replace(minute=0, second=0, microsecond=0)


class DatabaseBunkernetMixin(DatabaseMixinBase):
    """BunkerNet effectiveness stats persistence (``bw_bunkernet_stats``)."""

    @retry_on_transient_db_errors
    def upsert_stats(self, rows: List[Dict[str, Any]], *, bucket: Optional[datetime] = None) -> str:
        """Upsert one hourly bucket of stat rows.

        Each row is ``{"metric": str, "value": int, "instance_hostname": str}``. Idempotent
        on ``(bucket, instance_hostname, metric)`` so a re-run within the same hour overwrites
        rather than duplicates. Returns "" on success or an error message.
        """
        if not rows:
            return ""

        bucket = _floor_hour(bucket)
        now = datetime.now().astimezone()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            for row in rows:
                metric = str(row.get("metric") or "")
                if not metric:
                    continue
                hostname = str(row.get("instance_hostname") or "")
                value = int(row.get("value") or 0)
                existing = session.scalars(
                    select(BunkernetStats).where(
                        BunkernetStats.bucket == bucket,
                        BunkernetStats.instance_hostname == hostname,
                        BunkernetStats.metric == metric,
                    )
                ).first()
                if existing is not None:
                    existing.value = value
                else:
                    session.add(BunkernetStats(bucket=bucket, instance_hostname=hostname, metric=metric, value=value, created_at=now))

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    @retry_on_transient_db_errors
    def get_effectiveness(self, *, since: Optional[int] = None) -> Dict[str, Any]:
        """Joined effectiveness view: BunkerNet *contribution/health* (this plugin's table)
        plus *blocks* (requests blocked by BunkerNet intel, from ``bw_metrics_requests``).

        ``since`` is an epoch-seconds lower bound for the time window (default: last 24h).
        """
        window_start = datetime.fromtimestamp(since, tz=timezone.utc) if since else (datetime.now().astimezone() - timedelta(days=1))

        with self._db_session() as session:
            # Blocks side — already persisted by the metrics pull. A request blocked by
            # BunkerNet carries reason='bunkernet'.
            blocked_by_intel = (
                session.scalar(select(func.count()).select_from(Requests).where(Requests.reason == "bunkernet", Requests.date >= window_start)) or 0
            )

            data: Dict[str, Any] = {"blocked_by_intel": int(blocked_by_intel)}

            # Latest deployment-level value for "current state" metrics.
            for metric in _LATEST_METRICS:
                row = session.scalars(
                    select(BunkernetStats)
                    .where(BunkernetStats.metric == metric, BunkernetStats.instance_hostname == "")
                    .order_by(BunkernetStats.bucket.desc())
                    .limit(1)
                ).first()
                data[metric] = int(row.value) if row is not None else 0

            # Summed contribution over the window.
            for metric in _SUM_METRICS:
                total = (
                    session.scalar(
                        select(func.coalesce(func.sum(BunkernetStats.value), 0)).where(
                            BunkernetStats.metric == metric, BunkernetStats.bucket >= _floor_hour(window_start)
                        )
                    )
                    or 0
                )
                data[metric] = int(total)

            # Per-instance connectivity from the latest bucket carrying a "connected" row.
            latest_connected_bucket = session.scalar(select(func.max(BunkernetStats.bucket)).where(BunkernetStats.metric == "connected"))
            connected = {}
            if latest_connected_bucket is not None:
                for row in session.scalars(
                    select(BunkernetStats).where(BunkernetStats.metric == "connected", BunkernetStats.bucket == latest_connected_bucket)
                ).all():
                    connected[row.instance_hostname] = bool(row.value)
            data["connected"] = connected

        return data

    @retry_on_transient_db_errors
    def get_stats(
        self, *, metric: Optional[str] = None, instance_hostname: Optional[str] = None, since: Optional[int] = None, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Raw time-series rows for charting, newest first."""
        conditions = []
        if metric:
            conditions.append(BunkernetStats.metric == metric)
        if instance_hostname is not None:
            conditions.append(BunkernetStats.instance_hostname == instance_hostname)
        if since:
            conditions.append(BunkernetStats.bucket >= datetime.fromtimestamp(since, tz=timezone.utc))

        stmt = select(BunkernetStats)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(BunkernetStats.bucket.desc()).limit(max(1, min(limit, 10000)))

        with self._db_session() as session:
            rows = session.scalars(stmt).all()
            return [
                {
                    "bucket": int(row.bucket.timestamp()),
                    "instance_hostname": row.instance_hostname,
                    "metric": row.metric,
                    "value": row.value,
                }
                for row in rows
            ]

    @retry_on_transient_db_errors
    def cleanup_bunkernet_by_age(self, days: int) -> str:
        """Delete stat rows older than ``days``. Returns ``"Removed N bunkernet stats by age"``."""
        removed = 0
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            cutoff = datetime.now().astimezone() - timedelta(days=days)
            removed = session.execute(delete(BunkernetStats).where(BunkernetStats.bucket < cutoff), execution_options={"synchronize_session": False}).rowcount
            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return f"Removed {removed} bunkernet stats by age"
