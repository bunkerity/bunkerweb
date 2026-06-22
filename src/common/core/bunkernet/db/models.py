#!/usr/bin/env python3
"""Plugin-shipped DB model for the BunkerNet effectiveness pilot.

Demonstrates the 1.7 plugin DB-extension mechanism: this module is auto-discovered
and its table registered on the shared ``Base.metadata`` before ``create_all`` — no
core edit, no Alembic migration. The table name stays inside the enforced
``bw_bunkernet_`` namespace.

``bw_bunkernet_stats`` is an hourly time-series of BunkerNet *contribution/health*
metrics (reports contributed upstream, blocklist size, registration/connectivity).
The *blocks* side of effectiveness — requests actually blocked by BunkerNet intel —
already lives in ``bw_metrics_requests`` (``reason='bunkernet'``) and is joined in at
read time, so no request-hot-path change is needed here.
"""

from datetime import datetime

from model import Base  # type: ignore  # shared SQLAlchemy declarative base
from sqlalchemy import DateTime, Identity, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import UniqueConstraint


class BunkernetStats(Base):
    """One row per (hour bucket, instance, metric)."""

    __tablename__ = "bw_bunkernet_stats"
    __table_args__ = (
        UniqueConstraint("bucket", "instance_hostname", "metric", name="uq_bw_bunkernet_stats"),
        Index("ix_bw_bunkernet_stats_metric", "metric"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # "" = deployment-level metric (shared blocklist / single BunkerNet identity);
    # a hostname = per-instance metric (e.g. connectivity).
    instance_hostname: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    # reports_sent | reports_pending | blocklist_size | registered | connected
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
