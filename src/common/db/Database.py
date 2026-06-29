#!/usr/bin/env python3

from contextlib import contextmanager, suppress
from datetime import datetime
from logging import Logger
from os import _exit, getenv, sep
from os.path import join as os_join
from pathlib import Path
from re import Match, compile as re_compile
from sys import path as sys_path
from typing import Any, Optional, Tuple
from time import sleep
from uuid import uuid4

for deps_path in [os_join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Shared db-layer infrastructure (lock, retry decorator, engine event hooks, pool
# defaults). Importing db_methods.common also triggers the install_as_MySQLdb(),
# sqlite PRAGMA listener and SAWarning filter side effects — before any engine is
# created, exactly as when they lived at module level here. Names are re-exported
# to keep the module surface of `Database` backward compatible.
from db_methods.common import (  # noqa: F401
    DEFAULT_POOL_MAX_OVERFLOW,
    DEFAULT_POOL_PRE_PING,
    DEFAULT_POOL_RECYCLE,
    DEFAULT_POOL_SIZE,
    DEFAULT_POOL_TIMEOUT,
    LOCK,
    retry_on_transient_db_errors,
    set_sqlite_pragma,
)

from db_methods.metadata import DatabaseMetadataMixin
from db_methods.initialization import DatabaseInitTablesMixin
from db_methods.config_save import DatabaseConfigSaveMixin
from db_methods.config_read import DatabaseConfigReadMixin
from db_methods.custom_configs import DatabaseCustomConfigsMixin
from db_methods.services import DatabaseServicesMixin
from db_methods.jobs import DatabaseJobsMixin
from db_methods.plugins import DatabasePluginsMixin
from db_methods.plugins_update import DatabasePluginsUpdateMixin
from db_methods.instances import DatabaseInstancesMixin
from db_methods.templates import DatabaseTemplatesMixin
from db_methods.resource_groups import DatabaseResourceGroupsMixin
from db_methods.ui_users import DatabaseUIUsersMixin
from db_methods.metrics import DatabaseMetricsMixin

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool


class Database(
    DatabaseMetadataMixin,
    DatabaseInitTablesMixin,
    DatabaseConfigSaveMixin,
    DatabaseConfigReadMixin,
    DatabaseCustomConfigsMixin,
    DatabaseServicesMixin,
    DatabaseJobsMixin,
    DatabasePluginsMixin,
    DatabasePluginsUpdateMixin,
    DatabaseInstancesMixin,
    DatabaseTemplatesMixin,
    DatabaseResourceGroupsMixin,
    DatabaseUIUsersMixin,
    DatabaseMetricsMixin,
):
    DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?|oracle(\+oracledb)?):/+(?P<path>/[^\s]+)")
    READONLY_ERROR = ("readonly", "read-only", "command denied", "Access denied")
    TRANSIENT_CONNECTION_ERROR_HINTS = (
        "connection refused",
        "can't connect",
        "lost connection",
        "server has gone away",
        "connection reset",
        "connection aborted",
        "timed out",
        "timeout",
        "connection is closed",
    )
    RESTRICTED_TEMPLATE_SETTINGS = ("USE_TEMPLATE", "IS_DRAFT")
    MULTISITE_CUSTOM_CONFIG_TYPES = ("server_http", "modsec_crs", "modsec", "server_stream", "crs_plugins_before", "crs_plugins_after")
    GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR = (
        "Service-scoped modsec-crs configs are not supported when USE_MODSECURITY_GLOBAL_CRS is enabled. "
        "Create a global modsec-crs config and scope it with a Host rule instead."
    )
    SUFFIX_RX = re_compile(r"(?P<setting>.+)_(?P<suffix>\d+)$")

    def __init__(
        self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, external: bool = False, pool: Optional[bool] = None, log: bool = True, **kwargs
    ) -> None:
        """Initialize the database"""
        self.logger = logger
        self.readonly = False
        self.last_connection_retry = None
        # single underscore on purpose: name-mangled (__) attributes break once the
        # methods that read them move to mixin classes
        self._ignore_regex_check = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"
        self._request_retry_attempts = 2
        self._request_retry_delay = 0.25

        request_retry_attempts = getenv("DATABASE_REQUEST_RETRY_ATTEMPTS", "2")
        if request_retry_attempts.isdigit() and int(request_retry_attempts) > 0:
            self._request_retry_attempts = int(request_retry_attempts)
        else:
            self.logger.warning(f"Invalid DATABASE_REQUEST_RETRY_ATTEMPTS value: {request_retry_attempts}, using default value (2)")

        request_retry_delay = getenv("DATABASE_REQUEST_RETRY_DELAY", "0.25")
        try:
            self._request_retry_delay = max(0.0, float(request_retry_delay))
        except ValueError:
            self.logger.warning(f"Invalid DATABASE_REQUEST_RETRY_DELAY value: {request_retry_delay}, using default value (0.25)")

        if pool:
            self.logger.warning("The pool parameter is deprecated, it will be removed in the next version")

        self._session_factory = None
        self.sql_engine = None

        if not sqlalchemy_string:
            sqlalchemy_string = getenv("DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3")

        sqlalchemy_string_readonly = getenv("DATABASE_URI_READONLY", "")

        if not sqlalchemy_string:
            sqlalchemy_string = sqlalchemy_string_readonly or "sqlite:////var/lib/bunkerweb/db.sqlite3"

            if sqlalchemy_string == sqlalchemy_string_readonly:
                self.readonly = True
                if log:
                    self.logger.warning("The database connection is set to read-only, the changes will not be saved")

        def validate_and_update_db_string(db_string: str) -> Tuple[str, Optional[Match]]:
            """Validate and update database connection string."""
            if not db_string:
                return db_string, None

            match = self.DB_STRING_RX.search(db_string)
            if not match:
                self.logger.error(f"Invalid database string provided: {db_string}, exiting...")
                _exit(1)

            db_type = match.group("database")
            db_path = match.group("path")

            # Handle SQLite database
            if db_type.startswith("sqlite"):
                path = Path(db_path)
                if external:
                    while not path.is_file():
                        if log:
                            self.logger.warning(f"Waiting for the database file to be created: {path}")
                        sleep(1)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                return db_string, match

            # Inject the recommended driver via SQLAlchemy's URL parser so only the drivername component is rewritten.
            recommended_driver = {
                "postgresql": "psycopg",
                "mysql": "pymysql",
                "mariadb": "pymysql",
                "oracle": "oracledb",
            }.get(db_type)
            if recommended_driver is not None:
                try:
                    url = make_url(db_string)
                except ArgumentError:
                    self.logger.error(f"Invalid database string provided: {db_string}, exiting...")
                    _exit(1)
                if "+" not in url.drivername:
                    url = url.set(drivername=f"{url.drivername}+{recommended_driver}")
                    return url.render_as_string(hide_password=False), match

            return db_string, match

        # Validate and update both connection strings
        sqlalchemy_string, main_match = validate_and_update_db_string(sqlalchemy_string)
        sqlalchemy_string_readonly, readonly_match = validate_and_update_db_string(sqlalchemy_string_readonly)

        self.database_uri = "" if sqlalchemy_string == sqlalchemy_string_readonly else sqlalchemy_string
        self.database_uri_readonly = sqlalchemy_string_readonly
        error = False

        match = main_match
        if self.database_uri_readonly and not self.database_uri and readonly_match:
            match = readonly_match

        if main_match and main_match.group("database") == "oracle":
            self.logger.error("Oracle database is not supported yet")
            _exit(1)

        if readonly_match and readonly_match.group("database") == "oracle":
            self.logger.error("Oracle database is not supported yet")
            _exit(1)

        # Pool size
        pool_size = getenv("DATABASE_POOL_SIZE", str(DEFAULT_POOL_SIZE))
        if pool_size.isdigit() and int(pool_size) >= 0:
            pool_size = int(pool_size)
        else:
            self.logger.warning(f"Invalid DATABASE_POOL_SIZE value: {pool_size}, using default value ({DEFAULT_POOL_SIZE})")
            pool_size = DEFAULT_POOL_SIZE

        # Max overflow
        max_overflow = getenv("DATABASE_POOL_MAX_OVERFLOW", str(DEFAULT_POOL_MAX_OVERFLOW))
        try:
            max_overflow = int(max_overflow)
        except ValueError:
            self.logger.warning(f"Invalid DATABASE_POOL_MAX_OVERFLOW value: {max_overflow}, using default value ({DEFAULT_POOL_MAX_OVERFLOW})")
            max_overflow = DEFAULT_POOL_MAX_OVERFLOW

        # Pool timeout
        pool_timeout = getenv("DATABASE_POOL_TIMEOUT", str(DEFAULT_POOL_TIMEOUT))
        if pool_timeout.isdigit() and int(pool_timeout) >= 0:
            pool_timeout = int(pool_timeout)
        else:
            self.logger.warning(f"Invalid DATABASE_POOL_TIMEOUT value: {pool_timeout}, using default value ({DEFAULT_POOL_TIMEOUT})")
            pool_timeout = DEFAULT_POOL_TIMEOUT

        # Pool recycle
        pool_recycle = getenv("DATABASE_POOL_RECYCLE", str(DEFAULT_POOL_RECYCLE))
        try:
            pool_recycle = int(pool_recycle)
        except ValueError:
            self.logger.warning(f"Invalid DATABASE_POOL_RECYCLE value: {pool_recycle}, using default value ({DEFAULT_POOL_RECYCLE})")
            pool_recycle = DEFAULT_POOL_RECYCLE

        # Pool pre-ping
        pool_pre_ping = getenv("DATABASE_POOL_PRE_PING", "yes" if DEFAULT_POOL_PRE_PING else "no").lower() in ("yes", "true", "1")

        self.logger.debug(
            f"Database pool configuration: pool_size={pool_size}, max_overflow={max_overflow}, pool_timeout={pool_timeout}, pool_recycle={pool_recycle}, pool_pre_ping={pool_pre_ping}"
        )

        self._engine_kwargs = {
            "poolclass": QueuePool,
            "pool_pre_ping": pool_pre_ping,
            "pool_recycle": pool_recycle,
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": pool_timeout,
        } | kwargs

        if "pool_reset_on_return" not in kwargs:
            default_pool_reset = "rollback"
            configured_pool_reset = getenv("DATABASE_POOL_RESET_ON_RETURN", "").strip().lower() or default_pool_reset
            if configured_pool_reset in ("none", "null", "off", "false", "no"):
                self._engine_kwargs["pool_reset_on_return"] = None
            elif configured_pool_reset in ("rollback", "commit"):
                self._engine_kwargs["pool_reset_on_return"] = configured_pool_reset
            else:
                self.logger.warning(f"Invalid DATABASE_POOL_RESET_ON_RETURN value: {configured_pool_reset}, using default value ({default_pool_reset})")
                self._engine_kwargs["pool_reset_on_return"] = default_pool_reset

        try:
            self.sql_engine = create_engine(sqlalchemy_string, **self._engine_kwargs)
        except ArgumentError:
            self.logger.error(f"Invalid database URI: {sqlalchemy_string}")
            error = True
        except SQLAlchemyError as e:
            self.logger.error(f"Error when trying to create the engine: {e}")
            error = True
        finally:
            if error:
                _exit(1)

        try:
            assert self.sql_engine is not None
        except AssertionError:
            self.logger.error("The database engine is not initialized")
            _exit(1)

        DATABASE_RETRY_TIMEOUT = getenv("DATABASE_RETRY_TIMEOUT", "60")
        if not DATABASE_RETRY_TIMEOUT.isdigit():
            self.logger.warning(f"Invalid DATABASE_RETRY_TIMEOUT value: {DATABASE_RETRY_TIMEOUT}, using default value (60)")
            DATABASE_RETRY_TIMEOUT = "60"

        DATABASE_RETRY_TIMEOUT = int(DATABASE_RETRY_TIMEOUT)

        current_time = datetime.now().astimezone()
        not_connected = True
        fallback = False

        while not_connected:
            try:
                if self.readonly:
                    with self.sql_engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                else:
                    with self.sql_engine.connect() as conn:
                        table_name = uuid4().hex
                        conn.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
                        conn.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))

                not_connected = False
            except (OperationalError, DatabaseError) as e:
                if (datetime.now().astimezone() - current_time).total_seconds() > DATABASE_RETRY_TIMEOUT:
                    if not fallback and self.database_uri_readonly:
                        self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds. Falling back to read-only database connection")
                        self.sql_engine.dispose(close=True)
                        self.sql_engine = create_engine(self.database_uri_readonly, **self._engine_kwargs)
                        self.readonly = True
                        fallback = True
                        continue
                    self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds: {e}")
                    _exit(1)

                if any(error in str(e) for error in self.READONLY_ERROR):
                    if log:
                        self.logger.warning("The database is read-only. Retrying in read-only mode in 5 seconds ...")
                    self.sql_engine.dispose(close=True)
                    self.sql_engine = create_engine(sqlalchemy_string, **self._engine_kwargs)
                    self.readonly = True
                if "Unknown table" in str(e):
                    not_connected = False
                    continue
                elif log:
                    self.logger.warning("Can't connect to database, retrying in 5 seconds ...")
                sleep(5)
            except BaseException as e:
                self.logger.error(f"Error when trying to connect to the database: {e}")
                exit(1)

        if log:
            self.logger.info(f"✅ Database connection established{'' if not self.readonly else ' in read-only mode'}")

        self._session_factory = scoped_session(sessionmaker(bind=self.sql_engine, autoflush=True, expire_on_commit=False))

        if match.group("database").startswith("sqlite"):
            db_path = Path(match.group("path"))
            try:
                current_mode = db_path.stat().st_mode & 0o777
                if current_mode != 0o660:
                    db_path.chmod(0o660)
            except (OSError, IOError) as e:
                self.logger.warning(f"Could not set file permissions on {db_path}: {e}")

    def close(self) -> None:
        """Explicitly close all sessions and dispose the engine pool.
        Only call during controlled shutdown when no other threads are using this instance."""
        if getattr(self, "_session_factory", None):
            self._session_factory.remove()

        if getattr(self, "sql_engine", None):
            self.sql_engine.dispose(close=True)

    def __del__(self) -> None:
        """Best-effort close on GC so reloaded jobs still send COM_QUIT."""
        with suppress(Exception):
            self.close()

    def ext(self, plugin_id: str):
        """Return the DB-methods accessor for a plugin's ``db/methods.py`` extension.

        Lazily discovers plugin-shipped db-methods mixins (security-gated + checksum
        verified for pro/external) once, then binds the matching mixin to this live
        ``Database`` instance so its query helpers reuse ``_db_session``/``readonly``/
        retry config. Raises ``KeyError`` when the plugin ships no db-methods extension.
        """
        cache = self.__dict__.setdefault("_ext_proxy_cache", {})
        if plugin_id in cache:
            return cache[plugin_id]

        if self.__dict__.get("_ext_mixins") is None:
            try:
                from plugin_extensions import discover_db_methods  # type: ignore

                self._ext_mixins = discover_db_methods(self.logger, db=self)
            except Exception as e:
                self.logger.error(f"Failed to discover plugin DB methods: {e}")
                self._ext_mixins = {}

        mixin_cls = self._ext_mixins.get(plugin_id)
        if mixin_cls is None:
            raise KeyError(f"No DB extension methods registered for plugin '{plugin_id}'")

        from plugin_extensions import make_db_ext  # type: ignore

        proxy = make_db_ext(self, mixin_cls)
        cache[plugin_id] = proxy
        return proxy

    def _empty_if_none(self, value: Any) -> Any:
        """Return an empty string if the value is None or convert None values in collections"""
        if value is None:
            return ""
        elif isinstance(value, dict):
            return {k: self._empty_if_none(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._empty_if_none(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._empty_if_none(item) for item in value)
        return value

    def _split_setting_key(self, key: str) -> Tuple[str, Optional[int]]:
        """Split a setting key into its base id and optional numeric suffix."""
        match = self.SUFFIX_RX.search(key)
        if match:
            return match.group("setting"), int(match.group("suffix"))
        return key, None

    def _normalize_template_config_reference(self, reference: str) -> Optional[str]:
        """Normalize a config reference to the canonical type/name.conf representation."""
        if not reference:
            return None
        ref = reference.strip()
        if not ref:
            return None
        if "/" not in ref:
            return None
        cfg_type_raw, cfg_name_raw = ref.split("/", 1)
        cfg_type = cfg_type_raw.strip().replace("-", "_").lower()
        if cfg_type not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
            return None
        cfg_name = cfg_name_raw.strip().removesuffix(".conf")
        if not cfg_name:
            return None
        return f"{cfg_type}/{cfg_name}.conf"

    @staticmethod
    def _methods_are_compatible(new_method: Optional[str], current_method: Optional[str], *, allow_scheduler_override: bool = False) -> bool:
        """
        Compatibility rules for overwriting a setting's existing method:
        - autoconf wins over everything (and only autoconf overwrites autoconf).
        - ui and api are interchangeable.
        - scheduler (env-var origin) overwrites ui/api only when the caller asserts the
          setting was explicitly declared in the environment (allow_scheduler_override),
          so config-as-code stays authoritative without default-filled scheduler passes
          wiping UI/API customizations; the reverse stays blocked to protect in-session
          UI edits.
        """
        if new_method is None:
            return True
        if current_method is None:
            return True
        if new_method == "autoconf":
            return True
        if current_method == "autoconf":
            return new_method == "autoconf"
        if {new_method, current_method} <= {"ui", "api"}:
            return True
        if new_method == "scheduler" and current_method in ("ui", "api"):
            return allow_scheduler_override
        return new_method == current_method

    def _is_transient_connection_error(self, error: BaseException) -> bool:
        """Return True if the exception looks like a temporary DB connectivity issue."""
        if isinstance(error, ConnectionRefusedError):
            return True

        if isinstance(error, OperationalError) and getattr(error, "connection_invalidated", False):
            return True

        if not isinstance(error, (OperationalError, DatabaseError)):
            return False

        error_text = str(getattr(error, "orig", error)).lower()
        if not error_text:
            error_text = str(error).lower()

        return any(hint in error_text for hint in self.TRANSIENT_CONNECTION_ERROR_HINTS)

    def test_read(self):
        """Test the read access to the database"""
        self.logger.debug("Testing read access to the database ...")
        with self._db_session() as session:
            session.execute(text("SELECT 1"))

    def test_write(self):
        """Test the write access to the database"""
        self.logger.debug("Testing write access to the database ...")
        with self._db_session() as session:
            table_name = uuid4().hex
            session.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
            session.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))
            session.commit()

    def retry_connection(self, *, readonly: bool = False, fallback: bool = False, log: bool = True, **kwargs) -> None:
        """Retry the connection to the database"""
        self.last_connection_retry = datetime.now().astimezone()

        if log:
            self.logger.debug(f"Retrying the connection to the database{' in read-only mode' if readonly else ''}{' with fallback' if fallback else ''} ...")

        assert self.sql_engine is not None

        if fallback and not self.database_uri_readonly:
            raise ValueError("The fallback parameter is set to True but the read-only database URI is not set")

        self.sql_engine.dispose(close=True)
        self.sql_engine = create_engine(self.database_uri_readonly if fallback else self.database_uri, **self._engine_kwargs | kwargs)

        with LOCK:
            if self._session_factory is not None:
                self._session_factory.remove()
            self._session_factory = scoped_session(sessionmaker(bind=self.sql_engine, autoflush=True, expire_on_commit=False))

        if fallback or readonly:
            with self.sql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return

        table_name = uuid4().hex
        with self.sql_engine.connect() as conn:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
            conn.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))

    @contextmanager
    def _db_session(self) -> Any:
        try:
            assert self.sql_engine is not None
        except AssertionError:
            self.logger.error("The database engine is not initialized")
            _exit(1)

        session = None
        try:
            session = self._session_factory
            yield session
        except BaseException as e:
            if session:
                with suppress(Exception):
                    session.rollback()

            if any(error in str(e) for error in self.READONLY_ERROR):
                self.logger.warning("The database is read-only, retrying in read-only mode ...")
                with LOCK:
                    try:
                        self.retry_connection(readonly=True, pool_timeout=1)
                        self.retry_connection(readonly=True, log=False)
                    except (OperationalError, DatabaseError):
                        if self.database_uri_readonly:
                            self.logger.warning("Can't connect to the database in read-only mode, falling back to read-only one")
                            with suppress(OperationalError, DatabaseError):
                                self.retry_connection(fallback=True, pool_timeout=1)
                            self.retry_connection(fallback=True, log=False)
                    self.readonly = True
            elif isinstance(e, (ConnectionRefusedError, OperationalError)) and self.database_uri_readonly:
                self.logger.warning("Can't connect to the database, falling back to read-only one ...")
                with LOCK:
                    with suppress(OperationalError, DatabaseError):
                        self.retry_connection(fallback=True, pool_timeout=1)
                        self.retry_connection(fallback=True, log=False)
                        self.readonly = True
            raise
        finally:
            if session:
                with suppress(Exception):
                    session.remove()
