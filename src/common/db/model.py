from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    TIMESTAMP,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.schema import UniqueConstraint

CONTEXTS_ENUM = Enum("global", "multisite", name="contexts_enum")
SETTINGS_TYPES_ENUM = Enum("text", "check", "select", name="settings_types_enum")
METHODS_ENUM = Enum("ui", "scheduler", "autoconf", "manual", name="methods_enum")
SCHEDULES_ENUM = Enum("once", "minute", "hour", "day", "week", name="schedules_enum")
CUSTOM_CONFIGS_TYPES_ENUM = Enum(
    "http",
    "default_server_http",
    "server_http",
    "modsec",
    "modsec_crs",
    "stream",
    "stream_http",
    name="custom_configs_types_enum",
)
LOG_LEVELS_ENUM = Enum(
    "CRITICAL",
    "ERROR",
    "WARNING",
    "INFO",
    "DEBUG",
    "NOTSET",
    name="log_levels_enum",
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
Base = declarative_base()


class Plugins(Base):
    __tablename__ = "plugins"

    id = Column(String(64), primary_key=True)
    order = Column(Integer, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=False)
    version = Column(String(32), nullable=False)
    external = Column(Boolean, default=False, nullable=False)

    settings = relationship(
        "Settings", back_populates="plugin", cascade="all, delete, delete-orphan"
    )
    jobs = relationship(
        "Jobs", back_populates="plugin", cascade="all, delete, delete-orphan"
    )
    pages = relationship("Plugin_pages", back_populates="plugin", cascade="all, delete")


class Settings(Base):
    __tablename__ = "settings"
    __table_args__ = (
        PrimaryKeyConstraint("id", "name"),
        UniqueConstraint("id"),
        UniqueConstraint("name"),
    )

    id = Column(String(255), primary_key=True)
    name = Column(String(255), primary_key=True)
    plugin_id = Column(
        String(64),
        ForeignKey("plugins.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    context = Column(CONTEXTS_ENUM, nullable=False)
    default = Column(String(1023), nullable=True, default="")
    help = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    regex = Column(String(255), nullable=False)
    type = Column(SETTINGS_TYPES_ENUM, nullable=False)
    multiple = Column(String(255), nullable=True)

    selects = relationship("Selects", back_populates="setting", cascade="all, delete")
    services = relationship(
        "Services_settings", back_populates="setting", cascade="all, delete"
    )
    global_value = relationship(
        "Global_values", back_populates="setting", cascade="all, delete"
    )
    plugin = relationship("Plugins", back_populates="settings")


class Global_values(Base):
    __tablename__ = "global_values"

    setting_id = Column(
        String(255),
        ForeignKey("settings.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    value = Column(String(1023), nullable=False)
    suffix = Column(SmallInteger, primary_key=True, nullable=True, default=0)
    method = Column(METHODS_ENUM, nullable=False)

    setting = relationship("Settings", back_populates="global_value")


class Services(Base):
    __tablename__ = "services"

    id = Column(String(64), primary_key=True)
    method = Column(METHODS_ENUM, nullable=False)

    settings = relationship(
        "Services_settings", back_populates="service", cascade="all, delete"
    )
    custom_configs = relationship(
        "Custom_configs", back_populates="service", cascade="all, delete"
    )
    jobs_cache = relationship(
        "Jobs_cache", back_populates="service", cascade="all, delete"
    )


class Services_settings(Base):
    __tablename__ = "services_settings"

    service_id = Column(
        String(64),
        ForeignKey("services.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    setting_id = Column(
        String(255),
        ForeignKey("settings.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    value = Column(String(1023), nullable=False)
    suffix = Column(SmallInteger, primary_key=True, nullable=True, default=0)
    method = Column(METHODS_ENUM, nullable=False)

    service = relationship("Services", back_populates="settings")
    setting = relationship("Settings", back_populates="services")


class Jobs(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("name", "plugin_id"),)

    name = Column(String(128), primary_key=True)
    plugin_id = Column(
        String(64),
        ForeignKey("plugins.id", onupdate="CASCADE", ondelete="CASCADE"),
    )
    file_name = Column(String(255), nullable=False)
    every = Column(SCHEDULES_ENUM, nullable=False)
    reload = Column(Boolean, nullable=False)
    success = Column(Boolean, nullable=True)
    last_run = Column(DateTime, nullable=True)

    plugin = relationship("Plugins", back_populates="jobs")
    cache = relationship("Jobs_cache", back_populates="job", cascade="all, delete")


class Plugin_pages(Base):
    __tablename__ = "plugin_pages"

    id = Column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    plugin_id = Column(
        String(64),
        ForeignKey("plugins.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    template_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    template_checksum = Column(String(128), nullable=False)
    actions_file = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    actions_checksum = Column(String(128), nullable=False)

    plugin = relationship("Plugins", back_populates="pages")


class Jobs_cache(Base):
    __tablename__ = "jobs_cache"
    __table_args__ = (UniqueConstraint("job_name", "service_id", "file_name"),)

    id = Column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    job_name = Column(
        String(128),
        ForeignKey("jobs.name", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    service_id = Column(
        String(64),
        ForeignKey("services.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
    )
    file_name = Column(
        String(255),
        nullable=False,
    )
    data = Column(LargeBinary(length=(2**32) - 1), nullable=True)
    last_update = Column(DateTime, nullable=True)
    checksum = Column(String(128), nullable=True)

    job = relationship("Jobs", back_populates="cache")
    service = relationship("Services", back_populates="jobs_cache")


class Custom_configs(Base):
    __tablename__ = "custom_configs"
    __table_args__ = (UniqueConstraint("service_id", "type", "name"),)

    id = Column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    service_id = Column(
        String(64),
        ForeignKey("services.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
    )
    type = Column(CUSTOM_CONFIGS_TYPES_ENUM, nullable=False)
    name = Column(String(255), nullable=False)
    data = Column(LargeBinary(length=(2**32) - 1), nullable=False)
    checksum = Column(String(128), nullable=False)
    method = Column(METHODS_ENUM, nullable=False)

    service = relationship("Services", back_populates="custom_configs")


class Selects(Base):
    __tablename__ = "selects"

    setting_id = Column(
        String(255),
        ForeignKey("settings.id", onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True,
    )
    value = Column(String(255), primary_key=True)

    setting = relationship("Settings", back_populates="selects")


class Logs(Base):
    __tablename__ = "logs"

    id = Column(TIMESTAMP, primary_key=True)
    message = Column(String(1023), nullable=False)
    level = Column(LOG_LEVELS_ENUM, nullable=False)
    component = Column(String(255), nullable=False)


class Instances(Base):
    __tablename__ = "instances"

    hostname = Column(String(255), primary_key=True)
    port = Column(Integer, nullable=False)
    server_name = Column(String(255), nullable=False)


class Metadata(Base):
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, default=1)
    is_initialized = Column(Boolean, nullable=False)
    first_config_saved = Column(Boolean, nullable=False)
    autoconf_loaded = Column(Boolean, default=False, nullable=True)
    integration = Column(INTEGRATIONS_ENUM, default="Unknown", nullable=False)
    version = Column(String(5), default="1.5.0", nullable=False)
