#!/usr/bin/env python3

from sqlalchemy import (
    TEXT,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.schema import UniqueConstraint

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("password", "text", "check", "select", name="settings_types_enum")
METHODS_ENUM = Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")
SCHEDULES_ENUM = Enum("once", "minute", "hour", "day", "week", name="schedules_enum")
CUSTOM_CONFIGS_TYPES_ENUM = Enum(
    "http",
    "default_server_http",
    "server_http",
    "modsec",
    "modsec_crs",
    "stream",
    "server_stream",
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
PLUGIN_TYPES_ENUM = Enum("core", "external", "pro", name="plugin_types_enum")
PRO_STATUS_ENUM = Enum("active", "invalid", "expired", "suspended", name="pro_status_enum")
Base = declarative_base()


class Plugins(Base):
    __tablename__ = "bw_plugins"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(String(256), nullable=False)
    version = Column(String(32), nullable=False)
    stream = Column(STREAM_TYPES_ENUM, default="no", nullable=False)
    type = Column(PLUGIN_TYPES_ENUM, default="core", nullable=False)
    method = Column(METHODS_ENUM, default="manual", nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    checksum = Column(String(128), nullable=True)
    config_changed = Column(Boolean, default=False, nullable=True)
    last_config_change = Column(DateTime, nullable=True)

    settings = relationship("Settings", back_populates="plugin", cascade="all, delete-orphan")
    jobs = relationship("Jobs", back_populates="plugin", cascade="all, delete-orphan")
    pages = relationship("Plugin_pages", back_populates="plugin", cascade="all")
    commands = relationship("BwcliCommands", back_populates="plugin", cascade="all")


class Settings(Base):
    __tablename__ = "bw_settings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "name"),
        UniqueConstraint("id"),
    )

    id = Column(String(256), primary_key=True)
    name = Column(String(256), primary_key=True)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    context = Column(CONTEXTS_ENUM, nullable=False)
    default = Column(String(4096), nullable=True, default="")
    help = Column(String(512), nullable=False)
    label = Column(String(256), nullable=True)
    regex = Column(String(1024), nullable=False)
    type = Column(SETTINGS_TYPES_ENUM, nullable=False)
    multiple = Column(String(128), nullable=True)
    order = Column(Integer, default=0, nullable=False)

    selects = relationship("Selects", back_populates="setting", cascade="all")
    services = relationship("Services_settings", back_populates="setting", cascade="all")
    global_value = relationship("Global_values", back_populates="setting", cascade="all")
    plugin = relationship("Plugins", back_populates="settings")


class Selects(Base):
    __tablename__ = "bw_selects"

    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    value = Column(String(256), primary_key=True)

    setting = relationship("Settings", back_populates="selects")


class Global_values(Base):
    __tablename__ = "bw_global_values"

    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    value = Column(TEXT, nullable=False)
    suffix = Column(Integer, primary_key=True, nullable=True, default=0)
    method = Column(METHODS_ENUM, nullable=False)

    setting = relationship("Settings", back_populates="global_value")


class Services(Base):
    __tablename__ = "bw_services"

    id = Column(String(64), primary_key=True)
    method = Column(METHODS_ENUM, nullable=False)
    is_draft = Column(Boolean, default=False, nullable=False)

    settings = relationship("Services_settings", back_populates="service", cascade="all")
    custom_configs = relationship("Custom_configs", back_populates="service", cascade="all")
    jobs_cache = relationship("Jobs_cache", back_populates="service", cascade="all")


class Services_settings(Base):
    __tablename__ = "bw_services_settings"

    service_id = Column(String(64), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    value = Column(TEXT, nullable=False)
    suffix = Column(Integer, primary_key=True, nullable=True, default=0)
    method = Column(METHODS_ENUM, nullable=False)

    service = relationship("Services", back_populates="settings")
    setting = relationship("Settings", back_populates="services")


class Jobs(Base):
    __tablename__ = "bw_jobs"

    name = Column(String(128), primary_key=True)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"))
    file_name = Column(String(256), nullable=False)
    every = Column(SCHEDULES_ENUM, nullable=False)
    reload = Column(Boolean, default=False, nullable=False)
    success = Column(Boolean, nullable=True)
    last_run = Column(DateTime, nullable=True)

    plugin = relationship("Plugins", back_populates="jobs")
    cache = relationship("Jobs_cache", back_populates="job", cascade="all")


class Plugin_pages(Base):
    __tablename__ = "bw_plugin_pages"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    template_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    template_checksum = Column(String(128), nullable=False)
    actions_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    actions_checksum = Column(String(128), nullable=False)
    obfuscation_file = Column(LargeBinary(length=(2**32) - 1), default=None, nullable=True)
    obfuscation_checksum = Column(String(128), default=None, nullable=True)

    plugin = relationship("Plugins", back_populates="pages")


class Jobs_cache(Base):
    __tablename__ = "bw_jobs_cache"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    job_name = Column(String(128), ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"), nullable=False)
    service_id = Column(String(64), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    file_name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    last_update = Column(DateTime, nullable=True)
    checksum = Column(String(128), nullable=True)

    job = relationship("Jobs", back_populates="cache")
    service = relationship("Services", back_populates="jobs_cache")


class Custom_configs(Base):
    __tablename__ = "bw_custom_configs"
    __table_args__ = (UniqueConstraint("service_id", "type", "name"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    service_id = Column(String(64), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    type = Column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)
    method = Column(METHODS_ENUM, nullable=False)

    service = relationship("Services", back_populates="custom_configs")


class Instances(Base):
    __tablename__ = "bw_instances"

    hostname = Column(String(256), primary_key=True)
    port = Column(Integer, nullable=False)
    server_name = Column(String(256), nullable=False)


class Users(Base):
    __tablename__ = "bw_ui_users"

    id = Column(Integer, primary_key=True, default=1)
    username = Column(String(256), nullable=False, unique=True)
    password = Column(String(60), nullable=False)
    is_two_factor_enabled = Column(Boolean, nullable=False, default=False)
    secret_token = Column(String(32), nullable=True, unique=True, default=None)
    method = Column(METHODS_ENUM, nullable=False, default="manual")


class BwcliCommands(Base):
    __tablename__ = "bw_cli_commands"
    __table_args__ = (UniqueConstraint("plugin_id", "name"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    name = Column(String(64), nullable=False)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    file_name = Column(String(256), nullable=False)

    plugin = relationship("Plugins", back_populates="commands")


class Metadata(Base):
    __tablename__ = "bw_metadata"

    id = Column(Integer, primary_key=True, default=1)
    is_initialized = Column(Boolean, nullable=False)
    is_pro = Column(Boolean, default=False, nullable=False)
    pro_license = Column(String(128), default="", nullable=True)
    pro_expire = Column(DateTime, nullable=True)
    pro_status = Column(PRO_STATUS_ENUM, default="invalid", nullable=False)
    pro_services = Column(Integer, default=0, nullable=False)
    non_draft_services = Column(Integer, default=0, nullable=False)
    pro_overlapped = Column(Boolean, default=False, nullable=False)
    last_pro_check = Column(DateTime, nullable=True)
    first_config_saved = Column(Boolean, nullable=False)
    autoconf_loaded = Column(Boolean, default=False, nullable=True)
    scheduler_first_start = Column(Boolean, nullable=True)
    custom_configs_changed = Column(Boolean, default=False, nullable=True)
    last_custom_configs_change = Column(DateTime, nullable=True)
    external_plugins_changed = Column(Boolean, default=False, nullable=True)
    last_external_plugins_change = Column(DateTime, nullable=True)
    pro_plugins_changed = Column(Boolean, default=False, nullable=True)
    last_pro_plugins_change = Column(DateTime, nullable=True)
    instances_changed = Column(Boolean, default=False, nullable=True)
    last_instances_change = Column(DateTime, nullable=True)
    failover = Column(Boolean, default=None, nullable=True)
    integration = Column(INTEGRATIONS_ENUM, default="Unknown", nullable=False)
    version = Column(String(32), default="1.5.12", nullable=False)
