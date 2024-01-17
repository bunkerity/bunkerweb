#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, LargeBinary, PrimaryKeyConstraint, Sequence, String, func
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.schema import UniqueConstraint

Base = declarative_base()

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("password", "text", "check", "select", name="settings_types_enum")
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


class Actions(Base):
    __tablename__ = "bw_actions"

    id = Column(Integer, Sequence("action_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), nullable=False)
    api_method = Column(String(32), nullable=False)
    method = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(LargeBinary(length=2**14), nullable=False)
    status = Column(String(32), default="success", nullable=True)

    tags = relationship("Actions_tags", back_populates="action")


class Actions_tags(Base):
    __tablename__ = "bw_actions_tags"

    id = Column(Integer, Sequence("action_tag_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    action_id = Column(Integer, ForeignKey("bw_actions.id"), nullable=False)
    tag_id = Column(String(64), ForeignKey("bw_tags.id"), nullable=False)

    action = relationship("Actions", back_populates="tags")
    tag = relationship("Tags", back_populates="actions")


class Custom_configs(Base):
    __tablename__ = "bw_custom_configs"
    __table_args__ = (UniqueConstraint("service_id", "type", "name"),)

    id = Column(Integer, Sequence("custom_config_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    service_id = Column(
        String(64),
        ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"),
        nullable=True,
    )
    type = Column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)
    method = Column(String(32), nullable=False)

    service = relationship("Services", back_populates="custom_configs")


class Global_values(Base):
    __tablename__ = "bw_global_values"
    __table_args__ = (UniqueConstraint("setting_id", "suffix"),)

    id = Column(Integer, Sequence("global_value_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    setting_id = Column(
        String(256),
        ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    value = Column(String(4000), nullable=True)
    suffix = Column(Integer, nullable=True, default=0)
    method = Column(String(32), nullable=False)

    setting = relationship("Settings", back_populates="global_value")


class Instances(Base):
    __tablename__ = "bw_instances"

    hostname = Column(String(256), primary_key=True)
    port = Column(Integer, nullable=False)
    server_name = Column(String(256), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    method = Column(String(32), nullable=False)


class Jobs(Base):
    __tablename__ = "bw_jobs"
    __table_args__ = (UniqueConstraint("name", "plugin_id"),)

    name = Column(String(128), primary_key=True)
    plugin_id = Column(
        String(64),
        ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"),
    )
    file_name = Column(String(256), nullable=False)
    every = Column(String(256), nullable=False)
    reload = Column(Boolean, default=True, nullable=False)

    plugin = relationship("Plugins", back_populates="jobs")
    cache = relationship("Jobs_cache", back_populates="job", cascade="all")
    runs = relationship("Jobs_runs", back_populates="job", cascade="all")


class Jobs_cache(Base):
    __tablename__ = "bw_jobs_cache"
    __table_args__ = (UniqueConstraint("job_name", "service_id", "file_name"),)

    id = Column(Integer, Sequence("job_cache_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    job_name = Column(
        String(128),
        ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    service_id = Column(
        String(64),
        ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"),
        nullable=True,
    )
    file_name = Column(
        String(256),
        nullable=False,
    )
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    last_update = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    checksum = Column(String(128), nullable=True)

    job = relationship("Jobs", back_populates="cache")
    service = relationship("Services", back_populates="jobs_cache")


class Jobs_runs(Base):
    __tablename__ = "bw_jobs_runs"

    id = Column(Integer, Sequence("job_run_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    job_name = Column(
        String(128),
        ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    success = Column(Boolean, nullable=True, default=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True, server_default=func.now())

    job = relationship("Jobs", back_populates="runs")


class Metadata(Base):
    __tablename__ = "bw_metadata"

    id = Column(Integer, primary_key=True, default=1)
    is_initialized = Column(Boolean, nullable=False)
    scheduler_initialized = Column(Boolean, nullable=True, default=False)
    integration = Column(INTEGRATIONS_ENUM, nullable=True, default="Unknown")
    version = Column(String(32), nullable=True, default="2.0.0")


class Plugin_pages(Base):
    __tablename__ = "bw_plugin_pages"

    id = Column(Integer, Sequence("plugin_page_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    plugin_id = Column(
        String(64),
        ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    template_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    template_checksum = Column(String(128), nullable=False)
    actions_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    actions_checksum = Column(String(128), nullable=False)

    plugin = relationship("Plugins", back_populates="pages")


class Plugins(Base):
    __tablename__ = "bw_plugins"

    id = Column(String(64), primary_key=True)
    version = Column(String(32), nullable=False)
    stream = Column(String(16), nullable=False)
    external = Column(Boolean, nullable=True, default=False)
    method = Column(String(32), nullable=True, default="static")
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    checksum = Column(String(128), nullable=True)

    settings = relationship("Settings", back_populates="plugin", cascade="all, delete-orphan")
    jobs = relationship("Jobs", back_populates="plugin", cascade="all, delete-orphan")
    pages = relationship("Plugin_pages", back_populates="plugin", cascade="all, delete-orphan")
    translations = relationship("Plugins_translations", back_populates="plugin", cascade="all, delete-orphan")


class Plugins_translations(Base):
    __tablename__ = "bw_plugins_translations"

    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    language = Column(String(2), primary_key=True)
    name = Column(String(256), nullable=True)
    description = Column(String(512), nullable=True)

    plugin = relationship("Plugins", back_populates="translations")


class Selects(Base):
    __tablename__ = "bw_selects"
    __table_args__ = (UniqueConstraint("setting_id", "value"),)

    id = Column(Integer, Sequence("select_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    value = Column(String(256), nullable=True)

    setting = relationship("Settings", back_populates="selects")


class Services(Base):
    __tablename__ = "bw_services"

    id = Column(String(64), primary_key=True)
    method = Column(String(32), nullable=False)

    settings = relationship("Services_settings", back_populates="service", cascade="all")
    custom_configs = relationship("Custom_configs", back_populates="service", cascade="all")
    jobs_cache = relationship("Jobs_cache", back_populates="service", cascade="all")


class Services_settings(Base):
    __tablename__ = "bw_services_settings"
    __table_args__ = (UniqueConstraint("service_id", "setting_id", "suffix"),)

    id = Column(Integer, Sequence("service_setting_id_seq", start=1, increment=1, optional=True), primary_key=True, autoincrement=True)
    service_id = Column(
        String(64),
        ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    setting_id = Column(
        String(256),
        ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    value = Column(String(4000), nullable=False)
    suffix = Column(Integer, nullable=True, default=0)
    method = Column(String(32), nullable=False)

    service = relationship("Services", back_populates="settings")
    setting = relationship("Settings", back_populates="services")


class Settings(Base):
    __tablename__ = "bw_settings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "name"),
        UniqueConstraint("id"),
        UniqueConstraint("name"),
    )

    id = Column(String(256), primary_key=True)
    name = Column(String(256), primary_key=True)
    plugin_id = Column(
        String(64),
        ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"),
        nullable=False,
    )
    context = Column(CONTEXTS_ENUM, nullable=False)
    default = Column(String(4000), nullable=True, default="")
    regex = Column(String(1024), nullable=False)
    type = Column(SETTINGS_TYPES_ENUM, nullable=False)
    multiple = Column(String(128), nullable=True)

    selects = relationship("Selects", back_populates="setting", cascade="all")
    services = relationship("Services_settings", back_populates="setting", cascade="all")
    global_value = relationship("Global_values", back_populates="setting", cascade="all")
    plugin = relationship("Plugins", back_populates="settings")
    translations = relationship("Settings_translations", back_populates="setting", cascade="all")


class Settings_translations(Base):
    __tablename__ = "bw_settings_translations"

    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    language = Column(String(2), primary_key=True)
    help = Column(String(1024), nullable=True)
    label = Column(String(512), nullable=True)

    setting = relationship("Settings", back_populates="translations")


class Tags(Base):
    __tablename__ = "bw_tags"

    id = Column(String(64), primary_key=True)

    actions = relationship("Actions_tags", back_populates="tag")


class Users(Base):
    __tablename__ = "bw_ui_users"

    id = Column(Integer, primary_key=True, default=1)
    username = Column(String(256), nullable=False, unique=True)
    password = Column(String(60), nullable=False)
    is_two_factor_enabled = Column(Boolean, nullable=False, default=False)
    secret_token = Column(String(32), nullable=True, unique=True, default=None)
    method = Column(String(32), nullable=False, default="manual")