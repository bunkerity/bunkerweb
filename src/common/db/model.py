#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from typing import Any, ClassVar, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    UnicodeText,
    false,
    true,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates
from sqlalchemy.schema import UniqueConstraint

# Large text type that maps to MEDIUMTEXT on MySQL/MariaDB, TEXT elsewhere
LargeText = Text().with_variant(MEDIUMTEXT, "mysql").with_variant(MEDIUMTEXT, "mariadb")

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("password", "text", "number", "file", "check", "select", "multiselect", "multivalue", "size", "duration", name="settings_types_enum")
METHODS_ENUM = Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum")
SCHEDULES_ENUM = Enum("once", "minute", "hour", "day", "week", name="schedules_enum")
CUSTOM_CONFIGS_TYPES_ENUM = Enum(
    "http",
    "stream",
    "server_http",
    "server_stream",
    "default_server_http",
    "modsec",
    "modsec_crs",
    "crs_plugins_before",
    "crs_plugins_after",
    name="custom_configs_types_enum",
)
INTEGRATIONS_ENUM = Enum(
    "Linux",
    "Docker",
    "Swarm",
    "Kubernetes",
    "Autoconf",
    "Windows",
    "Unknown",
    name="integrations_enum",
)
STREAM_TYPES_ENUM = Enum("no", "yes", "partial", name="stream_types_enum")
PLUGIN_TYPES_ENUM = Enum("core", "external", "ui", "pro", name="plugin_types_enum")
PRO_STATUS_ENUM = Enum("active", "invalid", "expired", "suspended", name="pro_status_enum")
INSTANCE_TYPE_ENUM = Enum("static", "container", "pod", name="instance_type_enum")
INSTANCE_STATUS_ENUM = Enum("loading", "up", "down", "failover", name="instance_status_enum")
INSTANCE_TLS_MODE_ENUM = Enum("off", "pinned", name="instance_tls_mode_enum")
RESOURCE_KINDS_ENUM = Enum("ip", "country", "asn", "rdns", "user_agent", "uri", name="resource_kinds_enum")
# Attachable resource types shipped in the image. Not an enum: every new typed vertical
# (redirects, then upstreams) would otherwise cost a schema migration on four engines just
# to widen a constraint, and PostgreSQL enum values cannot be dropped on downgrade. Writes
# validate against this tuple instead.
CORE_RESOURCE_TYPES = ("certificate", "redirect", "upstream", "workflow")
# Load-balancing methods an upstream pool can use. "round_robin" is NGINX's default and emits
# no directive; the other two are plain http upstream directives, no third-party module needed.
UPSTREAM_METHODS = ("round_robin", "least_conn", "ip_hash")
# What consumes the pool. "http" and "grpc" both live in the http context and share a service's
# location namespace (proxy_pass / grpc_pass); "stream" lives in the stream context and has no
# path at all. Orthogonal to backend_ssl, so grpc-over-TLS stays expressible.
UPSTREAM_PROTOCOLS = ("http", "grpc", "stream")


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base.

    No ``type_annotation_map`` on purpose: every ``mapped_column()`` receives its
    SQL type explicitly, so annotation-driven type inference is never exercised
    and the emitted schema stays byte-identical to the legacy declarative one.
    """


class Plugins(Base):
    __tablename__ = "bw_plugins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    stream: Mapped[str] = mapped_column(STREAM_TYPES_ENUM, default="no", nullable=False)
    type: Mapped[str] = mapped_column(PLUGIN_TYPES_ENUM, default="core", nullable=False)
    method: Mapped[str] = mapped_column(METHODS_ENUM, default="manual", nullable=False)
    data: Mapped[Optional[bytes]] = mapped_column(LargeBinary(length=(2**32) - 1), default=None, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), default=None, nullable=True)
    config_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True, index=True)
    last_config_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    # Optional display icon (1.7). Convention: "@file/<name>" -> allowlisted icon file the plugin
    # ships (core: auto-detected in its own dir, served off disk from CORE_PLUGINS_ROOT/<id>/<name>;
    # external/ui/pro: inside the archive blob) via GET /plugins/{id}/icon; "*.svg" -> a shipped static
    # asset under the UI's img/plugins/; otherwise a Boxicons class name. NULL -> the consumer falls
    # back. Core plugins auto-detect the marker from their directory; the plugin.json ``icon`` field is
    # an optional override (fixed 4-name root-only allowlist -> no path-traversal surface).
    icon: Mapped[Optional[str]] = mapped_column(String(256), default=None, nullable=True)

    settings: Mapped[List["Settings"]] = relationship("Settings", back_populates="plugin", cascade="all, delete-orphan")
    jobs: Mapped[List["Jobs"]] = relationship("Jobs", back_populates="plugin", cascade="all, delete-orphan")
    pages: Mapped[List["Plugin_pages"]] = relationship("Plugin_pages", back_populates="plugin", cascade="all")
    commands: Mapped[List["Bw_cli_commands"]] = relationship("Bw_cli_commands", back_populates="plugin", cascade="all")
    templates: Mapped[List["Templates"]] = relationship("Templates", back_populates="plugin", cascade="all")
    resource_groups: Mapped[List["ResourceGroups"]] = relationship("ResourceGroups", back_populates="plugin", cascade="all")


class Settings(Base):
    __tablename__ = "bw_settings"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    plugin_id: Mapped[str] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    context: Mapped[str] = mapped_column(CONTEXTS_ENUM, nullable=False)
    default: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    help: Mapped[str] = mapped_column(String(512), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    regex: Mapped[str] = mapped_column(String(1024), nullable=False)
    type: Mapped[str] = mapped_column(SETTINGS_TYPES_ENUM, nullable=False)
    multiple: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    separator: Mapped[Optional[str]] = mapped_column(String(10), default=" ", nullable=True)
    accept: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # A3 opt-in (per setting, default off): when True, select/multiselect option matching is
    # case-insensitive and the value is canonicalized to the declared option casing. Most
    # selects are case-sensitive by nature (ModSecurity On/DetectionOnly, headers, TLS), so
    # this stays False unless a plugin.json explicitly sets it.
    case_insensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)

    selects: Mapped[List["Selects"]] = relationship("Selects", back_populates="setting", cascade="all")
    multiselects: Mapped[List["Multiselects"]] = relationship("Multiselects", back_populates="setting", cascade="all")
    services: Mapped[List["Services_settings"]] = relationship("Services_settings", back_populates="setting", cascade="all")
    global_value: Mapped[List["Global_values"]] = relationship("Global_values", back_populates="setting", cascade="all")
    templates: Mapped[List["Template_settings"]] = relationship("Template_settings", back_populates="setting", cascade="all")
    plugin: Mapped["Plugins"] = relationship("Plugins", back_populates="settings")


class Selects(Base):
    __tablename__ = "bw_selects"
    __table_args__ = (
        UniqueConstraint("setting_id", "value"),
        UniqueConstraint("setting_id", "order"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, default="")
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    setting: Mapped["Settings"] = relationship("Settings", back_populates="selects")


class Multiselects(Base):
    __tablename__ = "bw_multiselects"
    __table_args__ = (
        UniqueConstraint("setting_id", "option_id"),
        UniqueConstraint("setting_id", "order"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    option_id: Mapped[str] = mapped_column(String(256), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    setting: Mapped["Settings"] = relationship("Settings", back_populates="multiselects")


class Global_values(Base):
    __tablename__ = "bw_global_values"
    __table_args__ = (UniqueConstraint("setting_id", "suffix"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, default=None)
    suffix: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False)

    setting: Mapped["Settings"] = relationship("Settings", back_populates="global_value")


class Services(Base):
    __tablename__ = "bw_services"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    settings: Mapped[List["Services_settings"]] = relationship("Services_settings", back_populates="service", cascade="all")
    custom_configs: Mapped[List["Custom_configs"]] = relationship("Custom_configs", back_populates="service", cascade="all")
    jobs_cache: Mapped[List["Jobs_cache"]] = relationship("Jobs_cache", back_populates="service", cascade="all")
    resource_attachments: Mapped[List["ResourceAttachments"]] = relationship("ResourceAttachments", back_populates="service", cascade="all")


class Services_settings(Base):
    __tablename__ = "bw_services_settings"
    __table_args__ = (UniqueConstraint("service_id", "setting_id", "suffix"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    service_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    setting_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, default=None)
    suffix: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False)

    service: Mapped["Services"] = relationship("Services", back_populates="settings")
    setting: Mapped["Settings"] = relationship("Settings", back_populates="services")


class Jobs(Base):
    __tablename__ = "bw_jobs"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    # nullable=True was implicit before the SQLAlchemy 2.0 typed rewrite — made explicit, same schema
    plugin_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    every: Mapped[str] = mapped_column(SCHEDULES_ENUM, nullable=False)
    reload: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    run_async: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plugin: Mapped[Optional["Plugins"]] = relationship("Plugins", back_populates="jobs")
    cache: Mapped[List["Jobs_cache"]] = relationship("Jobs_cache", back_populates="job", cascade="all")
    runs: Mapped[List["Jobs_runs"]] = relationship("Jobs_runs", back_populates="job", cascade="all")


class Plugin_pages(Base):
    __tablename__ = "bw_plugin_pages"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    plugin_id: Mapped[str] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), unique=True, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)

    plugin: Mapped["Plugins"] = relationship("Plugins", back_populates="pages")


class Jobs_cache(Base):
    __tablename__ = "bw_jobs_cache"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    job_name: Mapped[str] = mapped_column(String(128), ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    service_id: Mapped[Optional[str]] = mapped_column(
        String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True, index=True
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    data: Mapped[Optional[bytes]] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    job: Mapped["Jobs"] = relationship("Jobs", back_populates="cache")
    service: Mapped[Optional["Services"]] = relationship("Services", back_populates="jobs_cache")


class Jobs_runs(Base):
    __tablename__ = "bw_jobs_runs"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    job_name: Mapped[str] = mapped_column(String(128), ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped["Jobs"] = relationship("Jobs", back_populates="runs")


class Requests(Base):
    """Persisted blocked-request reports (metrics), HTTP requests and TCP/UDP sessions alike.

    One row per blocked/detected event, mirroring the per-request record the
    metrics Lua endpoint exposes. Rows are scraped from instances and deduplicated
    on ``(instance_hostname, request_id)``. No FK: instance-agnostic / multi-instance.

    ``protocol`` is the discriminator. An HTTP request fills the HTTP columns
    (``method``, ``url``, ``user_agent``) and leaves the L4 ones null; a TCP/UDP session does
    the exact opposite. Both are kept in one table so retention, permissions, API and UI stay
    single-pathed — but neither is ever described in the other's vocabulary, which is why the
    HTTP columns are nullable and why a session status is not an HTTP status code.
    """

    __tablename__ = "bw_metrics_requests"
    __table_args__ = (
        UniqueConstraint("instance_hostname", "request_id", name="uq_bw_metrics_requests_instance_request"),
        Index("ix_bw_metrics_requests_date_server", "date", "server_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instance_hostname: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # "http", "tcp" or "udp". Defaulted rather than enumerated: a new L4 protocol must not need a
    # schema change on four engines, and rows written by an instance that predates this column
    # land as HTTP, which is what they were.
    protocol: Mapped[str] = mapped_column(String(8), nullable=False, default="http", server_default="http", index=True)
    ip: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # HTTP-only, hence nullable: a raw L4 session has no method, no URL and no user agent. They
    # used to be NOT NULL, which forced the stream path to fabricate "TCP" and "tcp://host:port".
    method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # HTTP response code for a request, NGINX session status (200/400/403/500/502/503) for a
    # stream session. Read it against ``protocol``, never as an HTTP code on its own.
    status: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    server_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    security_mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    asn_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asn_org: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # Stream-only dimensions, all free NGINX log-phase variables ($server_port, $remote_port,
    # $bytes_sent, $bytes_received, $session_time). Null for HTTP rows.
    listen_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    client_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bytes_sent: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bytes_received: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    session_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Baseline(Base):
    """Sampled records of NORMAL (non-blocked) traffic, for anomaly detection.

    Deliberately a separate table from ``bw_metrics_requests``: that one is filtered on read
    by ``_report_clause()`` (4xx or detect), so a baseline row stored there would be invisible
    to every existing query — and dropping the clause to expose it would break every count,
    facet, timeseries and retention path that depends on it.

    Rows are sampled in Lua, scraped from instances and deduplicated on
    ``(instance_hostname, request_id)`` like the blocked table. No FK: multi-instance.

    **No client IP column, by design.** This models traffic *shape*, not identity; recording
    every ordinary visitor's address is a far larger privacy commitment than recording the
    ones that were blocked. ``request_id`` is NGINX-generated and carries no identity.
    """

    __tablename__ = "bw_metrics_baseline"
    __table_args__ = (
        UniqueConstraint("instance_hostname", "request_id", name="uq_bw_metrics_baseline_instance_request"),
        Index("ix_bw_metrics_baseline_date_server", "date", "server_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    instance_hostname: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    server_name: Mapped[str] = mapped_column(String(256), nullable=False, default="", index=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # Templated in Lua (ids collapsed to <n>/<uuid>/<hex>) before it ever reaches here: a raw
    # path is one distinct value per request and a poor feature.
    uri: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    request_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    request_length: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    body_bytes_sent: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    upstream_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    connection_requests: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    http_version: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    scheme: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    content_length: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ssl_protocol: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    ssl_cipher: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    asn_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Bans(Base):
    """Durable ban records — the source of truth for the ban lifecycle.

    Each instance's ``datastore`` shared dict stays the local enforcement cache and Redis stays an
    optional distributed projection; neither is authoritative. The ``sync-bans`` job learns from
    both, writes here, and projects back.

    ``expires_at`` is an absolute instant, never a TTL. ``GET /bans`` reports ``exp = 0`` both for a
    permanent ban and for one less than a second from expiry (``ngx.shared:ttl()`` cannot tell them
    apart), while ``POST /ban`` reads ``exp = 0`` as permanent — so a stored TTL would silently
    promote an almost-expired ban to a permanent one on the next projection.

    Revocation keeps the row and stamps ``revoked_at``. That tombstone is what stops an instance
    which missed a ``POST /unban`` (its API path was down while NGINX kept serving) from re-teaching
    the ban on its next scrape.
    """

    __tablename__ = "bw_bans"
    __table_args__ = (
        UniqueConstraint("ip", "ban_scope", "service_id", name="uq_bw_bans_ip_scope_service"),
        Index("ix_bw_bans_active", "revoked_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    # Normalized through str(ip_address(x)) so it matches the compressed form nginx's $remote_addr
    # produces — the runtime builds its shm key from that, and an uncompressed "2001:0DB8::1" would
    # never match.
    ip: Mapped[str] = mapped_column(String(39), nullable=False, index=True)
    ban_scope: Mapped[str] = mapped_column(String(8), nullable=False, default="global")
    # "" for a global ban, never NULL: every supported engine treats NULLs as distinct inside a
    # UNIQUE constraint, so a nullable column would let one IP hold several global bans. No FK
    # either — a ban outlives the service it was scoped to.
    service_id: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    reason_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class Custom_configs(Base):
    __tablename__ = "bw_custom_configs"
    __table_args__ = (UniqueConstraint("service_id", "type", "name"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    service_id: Mapped[Optional[str]] = mapped_column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    type: Mapped[str] = mapped_column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    service: Mapped[Optional["Services"]] = relationship("Services", back_populates="custom_configs")


class Instances(Base):
    __tablename__ = "bw_instances"

    hostname: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="manual instance")
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    listen_https: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    https_port: Mapped[int] = mapped_column(Integer, nullable=False, default=5443)
    server_name: Mapped[str] = mapped_column(String(256), nullable=False)
    type: Mapped[str] = mapped_column(INSTANCE_TYPE_ENUM, nullable=False, default="static")
    status: Mapped[str] = mapped_column(INSTANCE_STATUS_ENUM, nullable=False, default="loading")
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False, default="manual")
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Per-instance control-plane→instance credential (opaque API token), encrypted at
    # rest with the shared AES-256-GCM keyring (certificate_utils); the hostname is the
    # AAD. Nullable: rows without one fall back to the global API_TOKEN when dialing.
    credential_ciphertext: Mapped[Optional[bytes]] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=True)
    credential_nonce: Mapped[Optional[bytes]] = mapped_column(LargeBinary(12), nullable=True)
    credential_key_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    credential_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-instance TLS trust for control-plane dials: "off" keeps today's behavior
    # (unverified + silent HTTP fallback); "pinned" requires the presented leaf's
    # SHA-256 to equal tls_fingerprint and disables the HTTPS→HTTP downgrade.
    tls_mode: Mapped[str] = mapped_column(INSTANCE_TLS_MODE_ENUM, nullable=False, default="off", server_default="off")
    tls_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Bw_cli_commands(Base):
    __tablename__ = "bw_cli_commands"
    __table_args__ = (UniqueConstraint("plugin_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    plugin_id: Mapped[str] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)

    plugin: Mapped["Plugins"] = relationship("Plugins", back_populates="commands")


class Templates(Base):
    __tablename__ = "bw_templates"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    plugin_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=True, index=True)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False, default="manual")
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plugin: Mapped[Optional["Plugins"]] = relationship("Plugins", back_populates="templates")
    steps: Mapped[List["Template_steps"]] = relationship("Template_steps", back_populates="template", cascade="all")
    settings: Mapped[List["Template_settings"]] = relationship("Template_settings", back_populates="template", cascade="all")
    custom_configs: Mapped[List["Template_custom_configs"]] = relationship("Template_custom_configs", back_populates="template", cascade="all")


class Template_steps(Base):
    __tablename__ = "bw_template_steps"

    # composite PK without Identity (autoincrement resolves to False) — keep exactly as before
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    template: Mapped["Templates"] = relationship("Templates", back_populates="steps")


class Template_settings(Base):
    __tablename__ = "bw_template_settings"
    __table_args__ = (
        UniqueConstraint("template_id", "setting_id", "step_id", "suffix"),
        UniqueConstraint("template_id", "setting_id", "order"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    setting_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    default: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    suffix: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template: Mapped["Templates"] = relationship("Templates", back_populates="settings")
    setting: Mapped["Settings"] = relationship("Settings", back_populates="templates")


class Template_custom_configs(Base):
    __tablename__ = "bw_template_custom_configs"
    __table_args__ = (
        UniqueConstraint("template_id", "step_id", "type", "name"),
        UniqueConstraint("template_id", "order"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    template: Mapped["Templates"] = relationship("Templates", back_populates="custom_configs")


class ResourceGroups(Base):
    __tablename__ = "bw_resource_groups"

    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False, default="ui")
    plugin_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=True, index=True)
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plugin: Mapped[Optional["Plugins"]] = relationship("Plugins", back_populates="resource_groups")
    entries: Mapped[List["ResourceGroup_entries"]] = relationship("ResourceGroup_entries", back_populates="group", cascade="all")


class ResourceGroup_entries(Base):
    __tablename__ = "bw_resource_group_entries"
    # NOTE: ``value`` is intentionally left out of any unique index — it is a (MEDIUM)TEXT column
    # and MySQL/MariaDB reject TEXT columns in a key without a prefix length. Deduplication on
    # (kind, value) is enforced in the DB-layer validator instead.
    __table_args__ = (UniqueConstraint("group_id", "order"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_resource_groups.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(RESOURCE_KINDS_ENUM, nullable=False)
    value: Mapped[str] = mapped_column(LargeText, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    group: Mapped["ResourceGroups"] = relationship("ResourceGroups", back_populates="entries")


class ResourceGroupUsages(Base):
    """Which plugin-owned object references a resource group, structurally.

    The ``@name`` tokens in list settings are found by scanning setting values
    (``_get_resource_group_references``); that scan cannot see a group referenced from
    inside a plugin's own payload — a workflow rule tree, for instance. This table is that
    missing half: it makes "who uses this group" answerable without parsing every plugin's
    documents, so deleting a used group can be refused with the consumer named, and editing
    one can flag exactly the plugins whose generated configuration must be recompiled.
    """

    __tablename__ = "bw_resource_group_usages"
    __table_args__ = (UniqueConstraint("group_id", "plugin_id", "consumer_type", "consumer_id"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_resource_groups.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    # Free-form, owned by the declaring plugin (e.g. "workflow"): the core never interprets
    # it, it only reports it, so a new consumer needs no schema change.
    consumer_type: Mapped[str] = mapped_column(String(32), nullable=False)
    consumer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)


class Resources(Base):
    __tablename__ = "bw_resources"
    __table_args__ = (UniqueConstraint("type", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Validated against CORE_RESOURCE_TYPES on write rather than by the database.
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    certificate: Mapped[Optional["Certificates"]] = relationship("Certificates", back_populates="resource", cascade="all, delete-orphan", uselist=False)
    redirect: Mapped[Optional["Redirects"]] = relationship("Redirects", back_populates="resource", cascade="all, delete-orphan", uselist=False)
    upstream: Mapped[Optional["Upstreams"]] = relationship("Upstreams", back_populates="resource", cascade="all, delete-orphan", uselist=False)
    workflow: Mapped[Optional["Workflows"]] = relationship("Workflows", back_populates="resource", cascade="all, delete-orphan", uselist=False)
    attachments: Mapped[List["ResourceAttachments"]] = relationship("ResourceAttachments", back_populates="resource", cascade="all, delete-orphan")

    @validates("type")
    def validate_type(self, _, value: str) -> str:
        if value not in CORE_RESOURCE_TYPES:
            raise ValueError(f"Unsupported resource type: {value}")
        return value


class Certificates(Base):
    __tablename__ = "bw_certificates"

    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("bw_resources.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    # Not an enum: any plugin declaring ``extensions.certificate_source`` in its plugin.json
    # can own certificates, so a new PRO or external provider must not require a schema
    # migration. Accepted values are validated against that registry on write.
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    certificate_pem: Mapped[str] = mapped_column(LargeText, nullable=False)
    private_key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary(length=(2**32) - 1), nullable=False)
    private_key_nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    private_key_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    common_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    sans: Mapped[str] = mapped_column(LargeText, nullable=False, default="[]")
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_type: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    renewal_metadata: Mapped[str] = mapped_column(LargeText, nullable=False, default="{}")
    last_renewal: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_renewal: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default="")
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    resource: Mapped["Resources"] = relationship("Resources", back_populates="certificate")


class Redirects(Base):
    __tablename__ = "bw_redirects"

    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("bw_resources.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    # Mirrors the REDIRECT_* settings of the redirect core plugin: values are validated
    # against that plugin.json's regexes so an inline rule and a resource rule can never
    # diverge on what they accept.
    from_path: Mapped[str] = mapped_column(String(256), nullable=False, default="/")
    to_url: Mapped[str] = mapped_column(String(512), nullable=False)
    status_code: Mapped[str] = mapped_column(String(3), nullable=False, default="301")
    append_request_uri: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    resource: Mapped["Resources"] = relationship("Resources", back_populates="redirect")


class Workflows(Base):
    __tablename__ = "bw_workflows"

    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("bw_resources.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    # Format of ``definition``. Bumping it is a breaking change: the compiler refuses a
    # version it does not know rather than guessing, so the bump must ship its own migrator.
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Canonical JSON (sorted keys, no whitespace): ordered rules, each with a typed condition
    # tree, an optional rate threshold and exactly one terminal action. Validated by
    # utils/workflow_schema.py on every write — the column is deliberately opaque to SQL,
    # since a rule tree is nested and only ever read as a whole.
    definition: Mapped[str] = mapped_column(LargeText, nullable=False, default='{"rules":[],"schema_version":1}')

    resource: Mapped["Resources"] = relationship("Resources", back_populates="workflow")


class Upstreams(Base):
    __tablename__ = "bw_upstreams"

    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("bw_resources.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    # Not an enum, for the same reason as ``Certificates.source``: widening a DB enum costs a
    # migration on four engines. Validated against UPSTREAM_METHODS on write.
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="round_robin")
    # Which directive consumes the pool; validated against UPSTREAM_PROTOCOLS on write.
    protocol: Mapped[str] = mapped_column(String(16), nullable=False, default="http", server_default="http")
    # Talk TLS to the members: picks https:// over http:// and grpcs:// over grpc://. Kept
    # orthogonal to protocol so gRPC over TLS does not need its own protocol value.
    backend_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # ``keepalive N`` in the rendered block; NULL means the directive is not emitted at all,
    # which is not the same as 0 (NGINX rejects 0).
    keepalive: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    resource: Mapped["Resources"] = relationship("Resources", back_populates="upstream")
    servers: Mapped[List["UpstreamServers"]] = relationship(
        "UpstreamServers", back_populates="upstream", cascade="all, delete-orphan", order_by="UpstreamServers.order"
    )


class UpstreamServers(Base):
    __tablename__ = "bw_upstream_servers"
    # Uniqueness of ``host`` inside a pool is enforced by the DB-layer validator, not here:
    # a String(256) column in a key exceeds the index byte limit of older MySQL/MariaDB row
    # formats, the same constraint ResourceGroupEntries works around.
    __table_args__ = (UniqueConstraint("resource_id", "order"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    resource_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bw_upstreams.resource_id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True
    )
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_fails: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fail_timeout: Mapped[str] = mapped_column(String(16), nullable=False, default="10s")
    backup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    down: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    upstream: Mapped["Upstreams"] = relationship("Upstreams", back_populates="servers")


class ResourceAttachments(Base):
    __tablename__ = "bw_resource_attachments"
    __table_args__ = (
        UniqueConstraint("resource_id", "service_id", "match_path"),
        Index("ix_bw_resource_attachments_service_primary", "service_id", "is_primary"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey("bw_resources.id", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    service_id: Mapped[str] = mapped_column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    # Where the resource applies inside the service. Only upstreams use it (the reverse-proxy
    # location path); certificates and redirects attach to the whole service and keep "".
    # Empty string rather than NULL on purpose: it is part of the unique constraint, and on
    # most engines NULL never equals NULL, which would silently allow duplicate certificate
    # attachments on one service.
    match_path: Mapped[str] = mapped_column(String(256), nullable=False, default="", server_default="")
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    resource: Mapped["Resources"] = relationship("Resources", back_populates="attachments")
    service: Mapped["Services"] = relationship("Services", back_populates="resource_attachments")


class Metadata(Base):
    __tablename__ = "bw_metadata"

    # singleton row: client-side default=1, no Identity — keep exactly as before
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    is_initialized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_pro: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pro_license: Mapped[Optional[str]] = mapped_column(String(128), default="", nullable=True)
    pro_expire: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pro_status: Mapped[str] = mapped_column(PRO_STATUS_ENUM, default="invalid", nullable=False)
    pro_services: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    non_draft_services: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pro_overlapped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_pro_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_config_saved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    autoconf_loaded: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    scheduler_first_start: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    custom_configs_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    last_custom_configs_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    external_plugins_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    last_external_plugins_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pro_plugins_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    last_pro_plugins_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    instances_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    last_instances_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    certificates_changed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    last_certificates_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reload_ui_plugins: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    force_pro_update: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    failover: Mapped[Optional[bool]] = mapped_column(Boolean, default=None, nullable=True)
    failover_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    integration: Mapped[str] = mapped_column(INTEGRATIONS_ENUM, default="Unknown", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.7.0~beta", nullable=False)
    # AES-256-GCM keyring protecting stored private keys (bw_certificates) and per-instance
    # credentials (bw_instances). Only consulted when CERTIFICATE_ENCRYPTION_KEYS and
    # CERTIFICATE_ENCRYPTION_ACTIVE_KEY are absent from the environment: an operator-provided
    # keyring always wins and keeps the key outside the database. Never exposed by
    # get_metadata() and rejected by set_metadata().
    certificate_keyring: Mapped[Optional[str]] = mapped_column(LargeText, nullable=True, default=None)
    certificate_keyring_active: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default=None)


## UI Models

THEMES_ENUM = Enum("light", "dark", name="themes_enum")


class JSONText(TypeDecorator):
    """
    Custom JSON type to serialize/deserialize dictionaries as strings.
    Compatible with all databases (MariaDB, MySQL, PostgreSQL, SQLite).
    Ensures JSON strings are sorted by keys for consistent storage.
    """

    impl = Text  # Stores JSON as a TEXT field in the database
    cache_ok = True  # stateless/deterministic type: safe for SQLAlchemy's compiled-statement cache

    def process_bind_param(self, value: Optional[dict], dialect: Any) -> Optional[str]:
        """
        Convert a dictionary to a JSON string before saving to the database.
        Sorts dictionary keys for consistent serialization.
        """
        if value is None:
            return None
        # Serialize dictionary to a sorted JSON string
        return dumps(dict(sorted(value.items())))

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[dict]:
        """
        Convert a JSON string back to a dictionary after retrieving from the database.
        """
        if value is None:
            return None
        # Deserialize JSON string to dictionary
        return loads(value)


class Users(Base):
    __tablename__ = "bw_ui_users"

    username: Mapped[str] = mapped_column(String(256), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(256), unique=True, nullable=True)
    password: Mapped[str] = mapped_column(String(60), nullable=False)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False, default="manual")
    admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    theme: Mapped[str] = mapped_column(THEMES_ENUM, nullable=False, default="light")
    language: Mapped[str] = mapped_column(String(2), nullable=False, default="en")

    # 2FA
    totp_secret: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    update_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    roles: Mapped[List["RolesUsers"]] = relationship("RolesUsers", back_populates="user", cascade="all")
    recovery_codes: Mapped[List["UserRecoveryCodes"]] = relationship("UserRecoveryCodes", back_populates="user", cascade="all")
    sessions: Mapped[List["UserSessions"]] = relationship("UserSessions", back_populates="user", cascade="all")
    columns_preferences: Mapped[List["UserColumnsPreferences"]] = relationship("UserColumnsPreferences", back_populates="user", cascade="all")
    # plain (non-ORM) class attributes filled in by the UI layer; ClassVar keeps
    # DeclarativeBase from rejecting them as unmapped annotations
    list_roles: ClassVar[List[str]] = []
    list_permissions: ClassVar[List[str]] = []
    list_recovery_codes: ClassVar[List[str]] = []


class Roles(Base):
    __tablename__ = "bw_ui_roles"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(256), nullable=False)
    update_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    users: Mapped[List["RolesUsers"]] = relationship("RolesUsers", back_populates="role", cascade="all")
    permissions: Mapped[List["RolesPermissions"]] = relationship("RolesPermissions", back_populates="role", cascade="all")


class RolesUsers(Base):
    __tablename__ = "bw_ui_roles_users"

    user_name: Mapped[str] = mapped_column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True, index=True)

    user: Mapped["Users"] = relationship("Users", back_populates="roles")
    role: Mapped["Roles"] = relationship("Roles", back_populates="users")


class UserRecoveryCodes(Base):
    __tablename__ = "bw_ui_user_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(UnicodeText, nullable=False)

    user: Mapped["Users"] = relationship("Users", back_populates="recovery_codes")


class RolesPermissions(Base):
    __tablename__ = "bw_ui_roles_permissions"

    role_name: Mapped[str] = mapped_column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True)
    permission_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("bw_ui_permissions.name", onupdate="cascade", ondelete="cascade"), primary_key=True, index=True
    )

    role: Mapped["Roles"] = relationship("Roles", back_populates="permissions")
    permission: Mapped["Permissions"] = relationship("Permissions", back_populates="roles")


class Permissions(Base):
    __tablename__ = "bw_ui_permissions"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)

    roles: Mapped[List["RolesPermissions"]] = relationship("RolesPermissions", back_populates="permission", cascade="all")


class UserSessions(Base):
    __tablename__ = "bw_ui_user_sessions"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    ip: Mapped[str] = mapped_column(String(39), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["Users"] = relationship("Users", back_populates="sessions")


class UserColumnsPreferences(Base):
    __tablename__ = "bw_ui_user_columns_preferences"
    __table_args__ = (UniqueConstraint("user_name", "table_name"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    table_name: Mapped[str] = mapped_column(String(256), nullable=False)
    columns: Mapped[dict] = mapped_column(JSONText, nullable=False)

    user: Mapped["Users"] = relationship("Users", back_populates="columns_preferences")


## API Models

API_PERMISSION_ENUM = Enum(
    # Instance permissions
    "instances_create",
    "instances_read",
    "instances_update",
    "instances_delete",
    "instances_execute",
    # Global config permissions
    "global_config_read",
    "global_config_update",
    # Service permissions
    "service_create",
    "service_read",
    "service_update",
    "service_delete",
    "service_convert",
    "service_export",
    # Config permissions
    "config_create",
    "configs_read",
    "config_read",
    "config_update",
    "config_delete",
    # Plugin permissions
    "plugin_create",
    "plugin_read",
    "plugin_delete",
    # Cache permissions
    "cache_read",
    "cache_delete",
    # Web cache (proxy_cache) permissions
    "web_cache_read",
    "web_cache_purge",
    # Ban permissions
    "ban_created",
    "ban_read",
    "ban_update",
    "ban_delete",
    # Job permissions
    "job_read",
    "job_run",
    # Resource group permissions
    "resource_group_read",
    "resource_group_create",
    "resource_group_update",
    "resource_group_delete",
    "resource_group_clone",
    # Certificate permissions
    "certificate_read",
    "certificate_create",
    "certificate_update",
    "certificate_delete",
    "certificate_assign",
    "certificate_renew",
    "certificate_revoke",
    "certificate_download",
    # Redirect resource permissions
    "redirect_read",
    "redirect_create",
    "redirect_update",
    "redirect_delete",
    "redirect_assign",
    # Upstream resource permissions
    "upstream_read",
    "upstream_create",
    "upstream_update",
    "upstream_delete",
    "upstream_assign",
    # Security workflow resource permissions
    "workflow_read",
    "workflow_create",
    "workflow_update",
    "workflow_delete",
    "workflow_assign",
    name="api_permission_enum",
)

API_RESOURCE_ENUM = Enum(
    "instances",
    "global_config",
    "services",
    "configs",
    "plugins",
    "cache",
    "web_cache",
    "bans",
    "jobs",
    "resource_groups",
    "certificates",
    "redirects",
    "upstreams",
    "workflows",
    name="api_resource_enum",
)


class API_users(Base):
    __tablename__ = "bw_api_users"

    username: Mapped[str] = mapped_column(String(256), primary_key=True)
    password: Mapped[str] = mapped_column(String(60), nullable=False)
    method: Mapped[str] = mapped_column(METHODS_ENUM, nullable=False, default="manual")
    admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    update_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    permissions: Mapped[List["API_permissions"]] = relationship("API_permissions", back_populates="user", cascade="all, delete-orphan")


class API_permissions(Base):
    __tablename__ = "bw_api_user_permissions"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    api_user: Mapped[str] = mapped_column(String(256), ForeignKey("bw_api_users.username", onupdate="cascade", ondelete="cascade"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(API_RESOURCE_ENUM, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    permission: Mapped[str] = mapped_column(String(512), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["API_users"] = relationship("API_users", back_populates="permissions")
