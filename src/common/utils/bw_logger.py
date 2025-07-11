import os
import sys
import time
import atexit
import inspect
import functools
import threading
from logging import (
    CRITICAL, DEBUG, ERROR, INFO, WARNING, Handler,
    FileHandler, Formatter, Logger, StreamHandler,
    addLevelName, getLogger, setLoggerClass
)
from os import getenv
from typing import Any, Dict, Optional, Set, Tuple, Union, cast, Sequence
from dataclasses import dataclass
from pathlib import Path


# Automatically detects the calling function name for logger naming.
def _get_caller_name() -> str:
    frame = None
    try:
        frame = inspect.currentframe()
        if frame is None:
            return "unknown_caller"

        if frame.f_back is None:
            return "unknown_caller"
        caller_frame = frame.f_back.f_back
        if caller_frame is None:
            return "unknown_caller"

        function_name = caller_frame.f_code.co_name
        module_name = caller_frame.f_globals.get('__name__')

        if module_name and module_name != '__main__':
            caller_name = f"{module_name}.{function_name}"
        else:
            caller_name = function_name

        if DEBUG_MODE:
            print(f"[DEBUG] Auto-detected caller: {caller_name}")
        return caller_name

    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Caller detection failed: {e}")
        return "unknown_caller"
    finally:
        if frame:
            del frame


# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL_LOGGER", "INFO").upper() == "DEBUG"


# Provides a cross-platform way to get the current user's name.
def _get_username() -> str:
    if DEBUG_MODE:
        print("[DEBUG] Getting current username")
    try:
        import pwd
        username = pwd.getpwuid(os.geteuid()).pw_name
        if DEBUG_MODE:
            print(f"[DEBUG] Username from pwd: {username}")
        return username
    except (ImportError, KeyError) as e:
        if DEBUG_MODE:
            print(f"[DEBUG] pwd failed ({e}), using fallback")
        fallback = getenv('USERNAME') or 'unknown_user'
        if DEBUG_MODE:
            print(f"[DEBUG] Fallback username: {fallback}")
        return fallback


# Immutable snapshot of handler configuration for cache-friendly analysis.
@dataclass(frozen=True)
class HandlerSnapshot:
    handler_types: Tuple[str, ...]
    file_paths: Tuple[str, ...]
    handler_count: int

    @classmethod
    def from_handlers(cls, handlers: Sequence[Handler]) -> 'HandlerSnapshot':
        types = tuple(type(h).__name__ for h in handlers)
        paths = tuple(
            os.path.abspath(getattr(h, 'baseFilename', ''))
            for h in handlers if isinstance(h, FileHandler)
        )
        return cls(types, paths, len(handlers))


# Thread-safe cache for handler analysis results.
@dataclass(frozen=True)
class HandlerAnalysis:
    has_console: bool
    file_paths: Set[str]
    handler_count: int


# EXCEPTION is a custom log level (45), between ERROR (40) and
# CRITICAL (50). It gives special visibility to handled exceptions.
EXCEPTION_LEVEL = 45

# Constants for log formatting
LOG_FORMAT: str = (
    "%(asctime)s [%(name)s] [%(process)d] "
    "[%(levelname)s] - %(message)s"
)
DATE_FORMAT: str = "[%Y-%m-%d %H:%M:%S %z]"

# Mapping of string level names to numeric values
LEVEL_MAP: Dict[str, int] = {
    "CRITICAL": CRITICAL, "FATAL": CRITICAL, "EXCEPTION": EXCEPTION_LEVEL,
    "ERROR": ERROR, "WARN": WARNING, "WARNING": WARNING, "INFO": INFO,
    "DEBUG": DEBUG, "NOTSET": 0
}

# Thread safety and configuration tracking
_init_lock: threading.Lock = threading.Lock()
_config_lock: threading.Lock = threading.Lock()
_initialized: bool = False
_configured_loggers: Set[str] = set()

# Constants for cache management
MAX_CONFIGURED_LOGGERS = 1000
MAX_HANDLER_CACHE_SIZE = 2000
MAX_PATH_LENGTH = 4096


# Custom logger class to handle the EXCEPTION log level.
class BWLog(Logger):
    def __init__(self, name: str, level: int = INFO) -> None:
        super().__init__(name, level)

    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if kwargs.get('exc_info', True):
            kwargs['exc_info'] = True
        if self.isEnabledFor(EXCEPTION_LEVEL):
            self._log(EXCEPTION_LEVEL, msg, args, **kwargs)


@functools.lru_cache(maxsize=MAX_HANDLER_CACHE_SIZE)
def _get_handler_analysis_from_snapshot(
    snapshot: HandlerSnapshot
) -> HandlerAnalysis:
    has_console = any(
        'StreamHandler' in h_type and 'FileHandler' not in h_type
        for h_type in snapshot.handler_types
    )
    file_paths = set(path for path in snapshot.file_paths if path)

    if DEBUG_MODE:
        print(f"[DEBUG] Handler analysis: console={has_console}, "
              f"files={len(file_paths)}, total={snapshot.handler_count}")

    return HandlerAnalysis(
        has_console=has_console,
        file_paths=file_paths,
        handler_count=snapshot.handler_count
    )


def _analyze_handlers(logger: Logger) -> HandlerAnalysis:
    if DEBUG_MODE:
        print(f"[DEBUG] Analyzing handlers for logger '{logger.name}' "
              f"({len(logger.handlers)} handlers)")

    snapshot = HandlerSnapshot.from_handlers(logger.handlers)

    if DEBUG_MODE:
        print(f"[DEBUG] Handler snapshot: types={snapshot.handler_types}, "
              f"files={len(snapshot.file_paths)}")

    result = _get_handler_analysis_from_snapshot(snapshot)

    if DEBUG_MODE:
        print(f"[DEBUG] Analysis result: console={result.has_console}, "
              f"file_paths={len(result.file_paths)}")

    return result


# Validates and sanitizes file path input.
def _validate_file_path(log_file_path: str) -> str:
    if DEBUG_MODE:
        print(f"[DEBUG] Validating file path: '{log_file_path}'")

    if not log_file_path.strip():
        error_msg = "log_file_path must be a non-empty string"
        if DEBUG_MODE:
            print(f"[DEBUG] Validation failed: {error_msg}")
        raise ValueError(error_msg)

    try:
        abs_path = os.path.abspath(log_file_path.strip())
        if DEBUG_MODE:
            print(f"[DEBUG] Absolute path: '{abs_path}' "
                  f"(length: {len(abs_path)})")

        if len(abs_path) > MAX_PATH_LENGTH:
            error_msg = f"log_file_path too long (max {MAX_PATH_LENGTH})"
            if DEBUG_MODE:
                print(f"[DEBUG] Validation failed: {error_msg}")
            raise ValueError(error_msg)

        if DEBUG_MODE:
            print("[DEBUG] Path validation successful")
        return abs_path

    except (OSError, ValueError) as e:
        error_msg = f"Invalid log_file_path: {e}"
        if DEBUG_MODE:
            print(f"[DEBUG] Validation failed: {error_msg}")
        raise ValueError(error_msg) from e


# Creates a file handler with comprehensive error handling and fallbacks.
def _create_file_handler(
    log_file_path: str, level: int, logger: Logger
) -> bool:
    abs_log_path = _validate_file_path(log_file_path)

    if DEBUG_MODE:
        print(f"[DEBUG] Creating file handler for: {abs_log_path}")

    try:
        Path(abs_log_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = FileHandler(abs_log_path)
        formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

        if DEBUG_MODE:
            print("[DEBUG] File handler created successfully")
        return True

    except OSError:
        # FIX: Removed 'as e' as the variable was not explicitly used.
        # logger.exception automatically captures and logs the exception info.
        logger.exception(f"Failed to create primary log file: {abs_log_path}")
        fallback_paths = [
            f"/tmp/bunkerweb_fallback_{os.getpid()}.log",
            f"/var/tmp/bw_{os.getpid()}.log"
        ]
        formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        for fallback in fallback_paths:
            try:
                if DEBUG_MODE:
                    print(f"[DEBUG] Trying fallback: {fallback}")
                Path(fallback).parent.mkdir(parents=True, exist_ok=True)
                fallback_handler = FileHandler(fallback)
                fallback_handler.setFormatter(formatter)
                fallback_handler.setLevel(level)
                logger.addHandler(fallback_handler)
                logger.warning(f"Using fallback log file: {fallback}")
                if DEBUG_MODE:
                    print("[DEBUG] Fallback handler successful")
                return True
            except OSError as fallback_error:
                if DEBUG_MODE:
                    print(f"[DEBUG] Fallback failed for {fallback}: "
                          f"{fallback_error}")
                continue
        logger.warning(
            f"All file logging failed for user '{_get_username()}'. "
            f"Original path: {abs_log_path}. Using console only."
        )
        return False


def _get_level_from_env(
    env_vars: list[str], default_str: str, default_int: int
) -> int:
    if DEBUG_MODE:
        print(f"[DEBUG] Looking for level in env vars: {env_vars}")

    level_str = default_str
    found_var = None

    for var in env_vars:
        if env_val := getenv(var):
            level_str = env_val
            found_var = var
            if DEBUG_MODE:
                print(f"[DEBUG] Found {var}={env_val}")
            break

    if not found_var and DEBUG_MODE:
        print(f"[DEBUG] No env vars found, using default: {default_str}")

    level = LEVEL_MAP.get(level_str.upper(), default_int)

    if DEBUG_MODE:
        print(f"[DEBUG] Level resolution: '{level_str}' -> {level} "
              f"(from {found_var or 'default'})")

    return level


def _get_default_level() -> int:
    return _get_level_from_env(
        ["CUSTOM_LOG_LEVEL", "LOG_LEVEL"], "INFO", INFO
    )


def _get_database_level() -> int:
    return _get_level_from_env(
        ["DATABASE_LOG_LEVEL"], "WARNING", WARNING
    )


def _configure_sqlalchemy_loggers() -> None:
    if DEBUG_MODE:
        print("[DEBUG] Configuring SQLAlchemy loggers")

    database_level: int = _get_database_level()
    sqlalchemy_loggers: Tuple[str, ...] = (
        "sqlalchemy.orm.mapper.Mapper",
        "sqlalchemy.orm.relationships.RelationshipProperty",
        "sqlalchemy.orm.strategies.LazyLoader",
        "sqlalchemy.pool.impl.QueuePool",
        "sqlalchemy.pool.impl.SingletonThreadPool",
        "sqlalchemy.engine.Engine",
    )
    configured_count = 0
    for logger_name in sqlalchemy_loggers:
        if DEBUG_MODE:
            current_level = getLogger(logger_name).level
            print(f"[DEBUG] Setting {logger_name}: "
                  f"{current_level} -> {database_level}")

        getLogger(logger_name).setLevel(database_level)
        configured_count += 1

    if DEBUG_MODE:
        print(f"[DEBUG] Configured {configured_count} SQLAlchemy loggers "
              f"with level {database_level}")


# Cleans up resources and provides debug information on shutdown.
def _cleanup_resources() -> None:
    if DEBUG_MODE:
        print("[DEBUG] Starting logger resource cleanup")

    try:
        if DEBUG_MODE:
            cache_info = _get_handler_analysis_from_snapshot.cache_info()
            print(f"[DEBUG] Final cache stats: hits={cache_info.hits}, "
                  f"misses={cache_info.misses}, "
                  f"current_size={cache_info.currsize}")
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Could not get cache info: {e}")

    try:
        _get_handler_analysis_from_snapshot.cache_clear()
        if DEBUG_MODE:
            print("[DEBUG] Cache cleared successfully")
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Cache clear failed: {e}")

    if DEBUG_MODE:
        print("[DEBUG] Logger resource cleanup completed")


# Initializes logging configuration for the entire application.
def _initialize_logging() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return

        if DEBUG_MODE:
            print("[DEBUG] Initializing logging system")

        setLoggerClass(BWLog)
        addLevelName(EXCEPTION_LEVEL, "EXCEPTION")
        root_logger = getLogger()
        if getenv("LOG_TO_FILES_ONLY", "no").lower() != "yes":
            if not root_logger.handlers:
                root_handler = StreamHandler(sys.stderr)
                formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
                root_handler.setFormatter(formatter)
                root_logger.addHandler(root_handler)
                root_logger.setLevel(_get_default_level())

        level_emojis: Dict[int, str] = {
            CRITICAL: "🚨", EXCEPTION_LEVEL: "⚡", ERROR: "❌",
            INFO: "ℹ️ ", WARNING: "⚠️ ", DEBUG: "🐛"
        }
        for level, emoji in level_emojis.items():
            addLevelName(level, emoji)

        _configure_sqlalchemy_loggers()
        _initialized = True

        if DEBUG_MODE:
            print("[DEBUG] Logging system initialized successfully")


def setup_logger(
    title: str = "",
    level: Optional[Union[str, int]] = None,
    log_file_path: Optional[str] = None
) -> BWLog:
    if not title:
        if DEBUG_MODE:
            print("[DEBUG] Empty title provided, auto-detecting caller")
        title = _get_caller_name()

    if not title:
        error_msg = "title must be a non-empty string"
        if DEBUG_MODE:
            print(f"[DEBUG] Input validation failed: {error_msg}")
        raise ValueError(error_msg)

    start_time = time.time() if DEBUG_MODE else 0
    if DEBUG_MODE:
        print(f"[DEBUG] setup_logger called: title='{title}', "
              f"level={level}, file='{log_file_path}'")

    _initialize_logging()

    if DEBUG_MODE:
        print(f"[DEBUG] Converting level parameter: {level}")

    if level is None:
        numeric_level = _get_default_level()
        if DEBUG_MODE:
            print(f"[DEBUG] Using default level: {numeric_level}")
    elif isinstance(level, str):
        numeric_level = LEVEL_MAP.get(level.upper(), _get_default_level())
        if DEBUG_MODE:
            print(f"[DEBUG] String level '{level}' -> {numeric_level}")
    else:
        if level < 0:
            error_msg = "level must be a non-negative integer"
            if DEBUG_MODE:
                print(f"[DEBUG] Level validation failed: {error_msg}")
            raise ValueError(error_msg)
        numeric_level = level
        if DEBUG_MODE:
            print(f"[DEBUG] Using numeric level: {numeric_level}")

    abs_log_path = None
    if log_file_path:
        abs_log_path = _validate_file_path(log_file_path)

    with _config_lock:
        if DEBUG_MODE:
            print(f"[DEBUG] Acquired config lock, checking cache size "
                  f"({len(_configured_loggers)} loggers)")

        if len(_configured_loggers) > MAX_CONFIGURED_LOGGERS:
            if DEBUG_MODE:
                print(f"[DEBUG] Cache limit reached "
                      f"({len(_configured_loggers)} > "
                      f"{MAX_CONFIGURED_LOGGERS}), clearing caches")
            _configured_loggers.clear()
            _get_handler_analysis_from_snapshot.cache_clear()

        logger = cast(BWLog, getLogger(title))
        if title in _configured_loggers:
            if DEBUG_MODE:
                print(f"[DEBUG] Returning existing logger for '{title}'")
            return logger

        if DEBUG_MODE:
            print(f"[DEBUG] Configuring new logger '{title}' "
                  f"with level {numeric_level}")

        logger.setLevel(numeric_level)
        logger.propagate = False
        _configured_loggers.add(title)

        if DEBUG_MODE:
            print(f"[DEBUG] Logger '{title}' configured, cache size now: "
                  f"{len(_configured_loggers)}")

    if DEBUG_MODE:
        print("[DEBUG] Released config lock, starting handler analysis")

    handler_analysis = _analyze_handlers(logger)

    log_to_files_only = getenv("LOG_TO_FILES_ONLY", "no").lower() == "yes"
    if DEBUG_MODE:
        print(f"[DEBUG] LOG_TO_FILES_ONLY={log_to_files_only}, "
              f"has_console={handler_analysis.has_console}")

    if not log_to_files_only and not handler_analysis.has_console:
        if DEBUG_MODE:
            print("[DEBUG] Creating console handler")
        try:
            console_handler = StreamHandler(sys.stderr)
            formatter = Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(numeric_level)
            logger.addHandler(console_handler)
            if DEBUG_MODE:
                print("[DEBUG] Console handler added successfully")
        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] Console handler creation failed: {e}")
            try:
                sys.stderr.write(
                    f"[LOGGER SETUP WARNING] Failed to create console "
                    f"handler: {e}\n"
                )
            except Exception:
                if DEBUG_MODE:
                    print("[DEBUG] Even stderr.write failed")

    if abs_log_path:
        if DEBUG_MODE:
            print(f"[DEBUG] Checking if file handler "
                  f"needed for: {abs_log_path}")
            print(f"[DEBUG] Current file paths: "
                  f"{handler_analysis.file_paths}")

        if abs_log_path not in handler_analysis.file_paths:
            if DEBUG_MODE:
                print("[DEBUG] File handler needed, creating...")
            success = _create_file_handler(
                abs_log_path, numeric_level, logger
            )
            if DEBUG_MODE:
                print(f"[DEBUG] File handler result: "
                      f"{'success' if success else 'failed'}")
        else:
            if DEBUG_MODE:
                print("[DEBUG] File handler already exists for this path")

    if DEBUG_MODE:
        elapsed = time.time() - start_time
        try:
            cache_info = _get_handler_analysis_from_snapshot.cache_info()
            print(f"[DEBUG] setup_logger completed in {elapsed:.3f}s, "
                  f"cache hits={cache_info.hits}, "
                  f"misses={cache_info.misses}")
        except Exception:
            print(f"[DEBUG] setup_logger completed in {elapsed:.3f}s")

    return logger


# Register cleanup function to run on exit
atexit.register(_cleanup_resources)

# Run the global initialization when this module is first imported
if DEBUG_MODE:
    print("[DEBUG] BunkerWeb logger module loaded")

_initialize_logging()
