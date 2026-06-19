#!/usr/bin/env python3

from datetime import datetime
from json import dumps, loads
from typing import Any, ClassVar, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Identity, Integer, LargeBinary, String, Text, TypeDecorator, UnicodeText
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint

# Large text type that maps to MEDIUMTEXT on MySQL/MariaDB, TEXT elsewhere
LargeText = Text().with_variant(MEDIUMTEXT, "mysql").with_variant(MEDIUMTEXT, "mariadb")

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("password", "text", "number", "file", "check", "select", "multiselect", "multivalue", name="settings_types_enum")
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
RESOURCE_KINDS_ENUM = Enum("ip", "country", "asn", "rdns", "user_agent", "uri", name="resource_kinds_enum")


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
    reload_ui_plugins: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    force_pro_update: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    failover: Mapped[Optional[bool]] = mapped_column(Boolean, default=None, nullable=True)
    failover_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    integration: Mapped[str] = mapped_column(INTEGRATIONS_ENUM, default="Unknown", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.6.12~rc1", nullable=False)


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
    # Ban permissions
    "ban_created",
    "ban_read",
    "ban_update",
    "ban_delete",
    # Job permissions
    "job_read",
    "job_run",
    name="api_permission_enum",
)

API_RESOURCE_ENUM = Enum(
    "instances",
    "global_config",
    "services",
    "configs",
    "plugins",
    "cache",
    "bans",
    "jobs",
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
