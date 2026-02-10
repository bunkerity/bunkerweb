#!/usr/bin/env python3

from json import dumps, loads
from typing import Any, Optional
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Identity, Integer, LargeBinary, String, Text, TypeDecorator, UnicodeText
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.schema import UniqueConstraint

# Large text type that maps to MEDIUMTEXT on MySQL/MariaDB, TEXT elsewhere
LargeText = Text().with_variant(MEDIUMTEXT, "mysql").with_variant(MEDIUMTEXT, "mariadb")

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("password", "text", "number", "check", "select", "multiselect", "multivalue", name="settings_types_enum")
METHODS_ENUM = Enum("api", "ui", "scheduler", "autoconf", "manual", "wizard", name="methods_enum")
SCHEDULES_ENUM = Enum("once", "minute", "hour", "day", "week", name="schedules_enum")
CUSTOM_CONFIGS_TYPES_ENUM = Enum(
    "http",
    "stream",
    "server_http",
    "server_stream",
    "default_server_http",
    "default_server_stream",
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
    data = Column(LargeBinary(length=(2**32) - 1), default=None, nullable=True)
    checksum = Column(String(128), default=None, nullable=True)
    config_changed = Column(Boolean, default=False, nullable=True)
    last_config_change = Column(DateTime(timezone=True), nullable=True)

    settings = relationship("Settings", back_populates="plugin", cascade="all, delete-orphan")
    jobs = relationship("Jobs", back_populates="plugin", cascade="all, delete-orphan")
    pages = relationship("Plugin_pages", back_populates="plugin", cascade="all")
    commands = relationship("Bw_cli_commands", back_populates="plugin", cascade="all")
    templates = relationship("Templates", back_populates="plugin", cascade="all")


class Settings(Base):
    __tablename__ = "bw_settings"

    id = Column(String(256), primary_key=True)
    name = Column(String(256), unique=True, nullable=False)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    context = Column(CONTEXTS_ENUM, nullable=False)
    default = Column(Text, nullable=True, default="")
    help = Column(String(512), nullable=False)
    label = Column(String(256), nullable=True)
    regex = Column(String(1024), nullable=False)
    type = Column(SETTINGS_TYPES_ENUM, nullable=False)
    multiple = Column(String(128), nullable=True)
    separator = Column(String(10), nullable=True)
    order = Column(Integer, default=0, nullable=False)

    selects = relationship("Selects", back_populates="setting", cascade="all")
    multiselects = relationship("Multiselects", back_populates="setting", cascade="all")
    services = relationship("Services_settings", back_populates="setting", cascade="all")
    global_value = relationship("Global_values", back_populates="setting", cascade="all")
    templates = relationship("Template_settings", back_populates="setting", cascade="all")
    plugin = relationship("Plugins", back_populates="settings")


class Selects(Base):
    __tablename__ = "bw_selects"
    __table_args__ = (
        UniqueConstraint("setting_id", "value"),
        UniqueConstraint("setting_id", "order"),
    )

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    value = Column(String(256), nullable=True, default="")
    order = Column(Integer, default=0, nullable=False)

    setting = relationship("Settings", back_populates="selects")


class Multiselects(Base):
    __tablename__ = "bw_multiselects"
    __table_args__ = (
        UniqueConstraint("setting_id", "option_id"),
        UniqueConstraint("setting_id", "order"),
    )

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    option_id = Column(String(256), nullable=False)
    label = Column(String(256), nullable=False)
    value = Column(Text, nullable=True, default="")
    order = Column(Integer, default=0, nullable=False)

    setting = relationship("Settings", back_populates="multiselects")


class Global_values(Base):
    __tablename__ = "bw_global_values"
    __table_args__ = (UniqueConstraint("setting_id", "suffix"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    value = Column(LargeText, nullable=True, default="")
    suffix = Column(Integer, nullable=True, default=0)
    method = Column(METHODS_ENUM, nullable=False)

    setting = relationship("Settings", back_populates="global_value")


class Services(Base):
    __tablename__ = "bw_services"

    id = Column(String(256), primary_key=True)
    method = Column(METHODS_ENUM, nullable=False)
    is_draft = Column(Boolean, default=False, nullable=False)
    creation_date = Column(DateTime(timezone=True), nullable=False)
    last_update = Column(DateTime(timezone=True), nullable=False)

    settings = relationship("Services_settings", back_populates="service", cascade="all")
    custom_configs = relationship("Custom_configs", back_populates="service", cascade="all")
    jobs_cache = relationship("Jobs_cache", back_populates="service", cascade="all")


class Services_settings(Base):
    __tablename__ = "bw_services_settings"
    __table_args__ = (UniqueConstraint("service_id", "setting_id", "suffix"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    service_id = Column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    value = Column(LargeText, nullable=True, default="")
    suffix = Column(Integer, nullable=True, default=0)
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
    run_async = Column(Boolean, default=False, nullable=False)

    plugin = relationship("Plugins", back_populates="jobs")
    cache = relationship("Jobs_cache", back_populates="job", cascade="all")
    runs = relationship("Jobs_runs", back_populates="job", cascade="all")


class Plugin_pages(Base):
    __tablename__ = "bw_plugin_pages"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), unique=True, nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)

    plugin = relationship("Plugins", back_populates="pages")


class Jobs_cache(Base):
    __tablename__ = "bw_jobs_cache"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    job_name = Column(String(128), ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"), nullable=False)
    service_id = Column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    file_name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    last_update = Column(DateTime(timezone=True), nullable=True)
    checksum = Column(String(128), nullable=True)

    job = relationship("Jobs", back_populates="cache")
    service = relationship("Services", back_populates="jobs_cache")


class Jobs_runs(Base):
    __tablename__ = "bw_jobs_runs"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    job_name = Column(String(128), ForeignKey("bw_jobs.name", onupdate="cascade", ondelete="cascade"), nullable=False)
    success = Column(Boolean, nullable=True, default=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    job = relationship("Jobs", back_populates="runs")


class Custom_configs(Base):
    __tablename__ = "bw_custom_configs"
    __table_args__ = (UniqueConstraint("service_id", "type", "name"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    service_id = Column(String(256), ForeignKey("bw_services.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    type = Column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)
    method = Column(METHODS_ENUM, nullable=False)
    is_draft = Column(Boolean, nullable=False, default=False, server_default="0")

    service = relationship("Services", back_populates="custom_configs")


class Instances(Base):
    __tablename__ = "bw_instances"

    hostname = Column(String(256), primary_key=True)
    name = Column(String(256), nullable=False, default="manual instance")
    port = Column(Integer, nullable=False)
    listen_https = Column(Boolean, nullable=False, default=False)
    https_port = Column(Integer, nullable=False, default=5443)
    server_name = Column(String(256), nullable=False)
    type = Column(INSTANCE_TYPE_ENUM, nullable=False, default="static")
    status = Column(INSTANCE_STATUS_ENUM, nullable=False, default="loading")
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    creation_date = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)


class Bw_cli_commands(Base):
    __tablename__ = "bw_cli_commands"
    __table_args__ = (UniqueConstraint("plugin_id", "name"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    name = Column(String(64), nullable=False)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    file_name = Column(String(256), nullable=False)

    plugin = relationship("Plugins", back_populates="commands")


class Templates(Base):
    __tablename__ = "bw_templates"

    id = Column(String(256), primary_key=True)
    name = Column(String(256), unique=True, nullable=False)
    plugin_id = Column(String(64), ForeignKey("bw_plugins.id", onupdate="cascade", ondelete="cascade"), nullable=True)
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    creation_date = Column(DateTime(timezone=True), nullable=False)
    last_update = Column(DateTime(timezone=True), nullable=False)

    plugin = relationship("Plugins", back_populates="templates")
    steps = relationship("Template_steps", back_populates="template", cascade="all")
    settings = relationship("Template_settings", back_populates="template", cascade="all")
    custom_configs = relationship("Template_custom_configs", back_populates="template", cascade="all")


class Template_steps(Base):
    __tablename__ = "bw_template_steps"

    id = Column(Integer, primary_key=True)
    template_id = Column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), primary_key=True)
    title = Column(Text, nullable=False)
    subtitle = Column(Text, nullable=True)

    template = relationship("Templates", back_populates="steps")


class Template_settings(Base):
    __tablename__ = "bw_template_settings"
    __table_args__ = (
        UniqueConstraint("template_id", "setting_id", "step_id", "suffix"),
        UniqueConstraint("template_id", "setting_id", "order"),
    )

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    template_id = Column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    setting_id = Column(String(256), ForeignKey("bw_settings.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    step_id = Column(Integer, nullable=False)
    default = Column(Text, nullable=True, default="")
    suffix = Column(Integer, nullable=True, default=0)
    order = Column(Integer, nullable=False, default=0)

    template = relationship("Templates", back_populates="settings")
    setting = relationship("Settings", back_populates="templates")


class Template_custom_configs(Base):
    __tablename__ = "bw_template_custom_configs"
    __table_args__ = (
        UniqueConstraint("template_id", "step_id", "type", "name"),
        UniqueConstraint("template_id", "order"),
    )

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    template_id = Column(String(256), ForeignKey("bw_templates.id", onupdate="cascade", ondelete="cascade"), nullable=False)
    step_id = Column(Integer, nullable=False)
    type = Column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name = Column(String(256), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)
    order = Column(Integer, default=0, nullable=False)

    template = relationship("Templates", back_populates="custom_configs")


class Metadata(Base):
    __tablename__ = "bw_metadata"

    id = Column(Integer, primary_key=True, default=1)
    is_initialized = Column(Boolean, nullable=False)
    is_pro = Column(Boolean, default=False, nullable=False)
    pro_license = Column(String(128), default="", nullable=True)
    pro_expire = Column(DateTime(timezone=True), nullable=True)
    pro_status = Column(PRO_STATUS_ENUM, default="invalid", nullable=False)
    pro_services = Column(Integer, default=0, nullable=False)
    non_draft_services = Column(Integer, default=0, nullable=False)
    pro_overlapped = Column(Boolean, default=False, nullable=False)
    last_pro_check = Column(DateTime(timezone=True), nullable=True)
    first_config_saved = Column(Boolean, nullable=False)
    autoconf_loaded = Column(Boolean, default=False, nullable=True)
    scheduler_first_start = Column(Boolean, nullable=True)
    custom_configs_changed = Column(Boolean, default=False, nullable=True)
    last_custom_configs_change = Column(DateTime(timezone=True), nullable=True)
    external_plugins_changed = Column(Boolean, default=False, nullable=True)
    last_external_plugins_change = Column(DateTime(timezone=True), nullable=True)
    pro_plugins_changed = Column(Boolean, default=False, nullable=True)
    last_pro_plugins_change = Column(DateTime(timezone=True), nullable=True)
    instances_changed = Column(Boolean, default=False, nullable=True)
    last_instances_change = Column(DateTime(timezone=True), nullable=True)
    reload_ui_plugins = Column(Boolean, default=False, nullable=True)
    force_pro_update = Column(Boolean, default=False, nullable=True)
    failover = Column(Boolean, default=None, nullable=True)
    failover_message = Column(Text, nullable=True, default="")
    integration = Column(INTEGRATIONS_ENUM, default="Unknown", nullable=False)
    version = Column(String(32), default="1.6.8", nullable=False)


## UI Models

THEMES_ENUM = Enum("light", "dark", name="themes_enum")


class JSONText(TypeDecorator):
    """
    Custom JSON type to serialize/deserialize dictionaries as strings.
    Compatible with all databases (MariaDB, MySQL, PostgreSQL, SQLite).
    Ensures JSON strings are sorted by keys for consistent storage.
    """

    impl = Text  # Stores JSON as a TEXT field in the database

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

    username = Column(String(256), primary_key=True)
    email = Column(String(256), unique=True, nullable=True)
    password = Column(String(60), nullable=False)
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    admin = Column(Boolean, nullable=False, default=False)
    theme = Column(THEMES_ENUM, nullable=False, default="light")
    language = Column(String(2), nullable=False, default="en")

    # 2FA
    totp_secret = Column(String(256), nullable=True)

    creation_date = Column(DateTime(timezone=True), nullable=False)
    update_date = Column(DateTime(timezone=True), nullable=False)

    roles = relationship("RolesUsers", back_populates="user", cascade="all")
    recovery_codes = relationship("UserRecoveryCodes", back_populates="user", cascade="all")
    sessions = relationship("UserSessions", back_populates="user", cascade="all")
    columns_preferences = relationship("UserColumnsPreferences", back_populates="user", cascade="all")
    list_roles: list[str] = []
    list_permissions: list[str] = []
    list_recovery_codes: list[str] = []


class Roles(Base):
    __tablename__ = "bw_ui_roles"

    name = Column(String(64), primary_key=True)
    description = Column(String(256), nullable=False)
    update_datetime = Column(DateTime(timezone=True), nullable=False)

    users = relationship("RolesUsers", back_populates="role", cascade="all")
    permissions = relationship("RolesPermissions", back_populates="role", cascade="all")


class RolesUsers(Base):
    __tablename__ = "bw_ui_roles_users"

    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), primary_key=True)
    role_name = Column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True)

    user = relationship("Users", back_populates="roles")
    role = relationship("Roles", back_populates="users")


class UserRecoveryCodes(Base):
    __tablename__ = "bw_ui_user_recovery_codes"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    code = Column(UnicodeText, nullable=False)

    user = relationship("Users", back_populates="recovery_codes")


class RolesPermissions(Base):
    __tablename__ = "bw_ui_roles_permissions"

    role_name = Column(String(64), ForeignKey("bw_ui_roles.name", onupdate="cascade", ondelete="cascade"), primary_key=True)
    permission_name = Column(String(64), ForeignKey("bw_ui_permissions.name", onupdate="cascade", ondelete="cascade"), primary_key=True)

    role = relationship("Roles", back_populates="permissions")
    permission = relationship("Permissions", back_populates="roles")


class Permissions(Base):
    __tablename__ = "bw_ui_permissions"

    name = Column(String(64), primary_key=True)

    roles = relationship("RolesPermissions", back_populates="permission", cascade="all")


class UserSessions(Base):
    __tablename__ = "bw_ui_user_sessions"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    ip = Column(String(39), nullable=False)
    user_agent = Column(Text, nullable=True, default="")
    creation_date = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False)

    user = relationship("Users", back_populates="sessions")


class UserColumnsPreferences(Base):
    __tablename__ = "bw_ui_user_columns_preferences"
    __table_args__ = (UniqueConstraint("user_name", "table_name"),)

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name = Column(String(256), ForeignKey("bw_ui_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    table_name = Column(String(256), nullable=False)
    columns = Column(JSONText, nullable=False)

    user = relationship("Users", back_populates="columns_preferences")


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

    username = Column(String(256), primary_key=True)
    password = Column(String(60), nullable=False)
    method = Column(METHODS_ENUM, nullable=False, default="manual")
    admin = Column(Boolean, nullable=False, default=False)
    creation_date = Column(DateTime(timezone=True), nullable=False)
    update_date = Column(DateTime(timezone=True), nullable=False)

    permissions = relationship("API_permissions", back_populates="user", cascade="all, delete-orphan")


class API_permissions(Base):
    __tablename__ = "bw_api_user_permissions"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    api_user = Column(String(256), ForeignKey("bw_api_users.username", onupdate="cascade", ondelete="cascade"), nullable=False)
    resource_type = Column(API_RESOURCE_ENUM, nullable=False)
    resource_id = Column(String(256), nullable=True)
    permission = Column(String(512), nullable=False)
    granted = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("API_users", back_populates="permissions")
