#!/usr/bin/env python3

from abc import abstractmethod
from contextlib import suppress
from os import getenv
from pathlib import Path
from threading import Lock, Thread, get_ident
from time import monotonic, sleep
from traceback import format_exc

from Config import Config
from Database import DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url

from logger import getLogger  # type: ignore

# Minimum stall budget; the runtime budget also covers the effective database timeouts.
LOCK_WATCHDOG_INTERVAL = 30
LOCK_MAX_HOLD = 600


class HoldTimeLock:
    """A Lock that remembers when it was taken, so a watchdog can spot a holder stuck on a dead connection."""

    def __init__(self):
        self._lock = Lock()
        self._acquired_at = None
        self._last_progress_at = None
        self._owner = None

    def acquire(self, *args, **kwargs) -> bool:
        acquired = self._lock.acquire(*args, **kwargs)
        if acquired:
            self._acquired_at = monotonic()
            self._last_progress_at = self._acquired_at
            self._owner = get_ident()
        return acquired

    def release(self) -> None:
        self._acquired_at = None
        self._last_progress_at = None
        self._owner = None
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()

    def held_for(self) -> float:
        acquired_at = self._acquired_at
        return 0.0 if acquired_at is None else monotonic() - acquired_at

    def progress(self, *, database: bool = False):
        if self._owner is not None and (database or self._owner == get_ident()):
            self._last_progress_at = monotonic()

    def stalled_for(self) -> float:
        last_progress_at = self._last_progress_at
        return 0.0 if last_progress_at is None else monotonic() - last_progress_at


class Controller(Config):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reverse_proxy_suffix_start = 1
        self._loaded = False
        self._instances = []
        self._services = []
        self._configs = {config_type: {} for config_type in self._supported_config_types}
        self._extra_config = {}
        self._logger = getLogger(f"{self._type.upper()}-CONTROLLER")
        self._namespaces = None
        self._first_start = True

        # Periodic re-check interval (seconds) for the settings recheck worker. <= 0 disables it.
        recheck_interval = getenv("AUTOCONF_SETTINGS_RECHECK_INTERVAL", "300").strip()
        if not recheck_interval.lstrip("-").isdigit():
            self._logger.warning(f"Invalid AUTOCONF_SETTINGS_RECHECK_INTERVAL value {recheck_interval!r}, defaulting to 300")
            recheck_interval = "300"
        self._settings_recheck_interval = int(recheck_interval)

        namespaces = getenv("NAMESPACES")
        if namespaces:
            self._namespaces = namespaces.strip().split()
            self._logger.info(
                "Only instances and services in the "
                + ", ".join(f"{namespace!r}" for namespace in self._namespaces)
                + f" namespace{'s' if len(self._namespaces) > 1 else ''} will be managed."
            )

    def wait(self, wait_time: int) -> list:
        all_ready = False
        while not all_ready:
            if self.have_to_wait():
                self._logger.info(f"Waiting for the database to be ready, retrying in {wait_time}s ...")
                sleep(wait_time)
                continue

            try:
                self._instances = self.get_instances()
            except Exception:
                self._logger.error(f"Error while fetching instances:\n{format_exc()}")
                self._instances = []
            if not self._instances:
                self._logger.warning(f"No instance found, waiting {wait_time}s ...")
                sleep(wait_time)
                continue

            all_ready = True
            for instance in self._instances:
                if not instance["health"]:
                    self._logger.warning(f"Instance {instance['name']} is not ready, waiting {wait_time}s ...")
                    sleep(wait_time)
                    all_ready = False
                    break
        return self._instances

    @abstractmethod
    def _get_controller_instances(self):
        raise NotImplementedError

    @abstractmethod
    def _to_instances(self, controller_instance):
        raise NotImplementedError

    def get_instances(self):
        instances = []
        for controller_instance in self._get_controller_instances():
            instances.extend(self._to_instances(controller_instance))

        if not instances and self._first_start:
            for db_instance in self._db.get_instances(autoconf=True):
                if not any(db_instance["hostname"] == instance["hostname"] for instance in instances):
                    instances.append(db_instance)

        return instances

    @abstractmethod
    def _get_controller_services(self):
        raise NotImplementedError

    @abstractmethod
    def _to_services(self, controller_service):
        raise NotImplementedError

    def _set_autoconf_load_db(self):
        if not self._loaded:
            ret = self._db.set_metadata({"autoconf_loaded": True})
            if ret:
                self._logger.warning(f"Can't set autoconf loaded metadata to true in database: {ret}")
            else:
                self._loaded = True

    def get_services(self):
        services = []
        for controller_service in self._get_controller_services():
            services.extend(self._to_services(controller_service))
        return services

    @abstractmethod
    def get_configs(self):
        raise NotImplementedError

    @abstractmethod
    def apply_config(self, force: bool = False):
        raise NotImplementedError

    def initial_apply(self) -> bool:
        """Force a first apply with the current cluster state (first=True)."""
        self._update_settings()
        self._instances = self.get_instances()
        self._services = self.get_services()
        configs_result = self.get_configs()
        # Kubernetes returns (extra_config, configs); others return configs.
        if isinstance(configs_result, tuple) and len(configs_result) == 2:
            self._extra_config, self._configs = configs_result
        else:
            self._configs = configs_result

        self._logger.info("Applying initial autoconf configuration ...")
        try:
            success = self.apply_config()
        except BaseException as e:
            self._logger.error(f"Exception during initial autoconf apply: {e}")
            success = False

        if success:
            self._set_autoconf_load_db()
            self._logger.info("Initial autoconf configuration applied 🚀")
        else:
            self._logger.error("Initial autoconf apply failed, scheduler may start with stale configuration")
        return success

    def _start_settings_recheck_worker(self):
        """Start the background settings recheck worker (no-op if disabled via interval <= 0)."""
        if self._settings_recheck_interval <= 0:
            self._logger.info("Settings recheck worker disabled (AUTOCONF_SETTINGS_RECHECK_INTERVAL <= 0)")
            return
        self._logger.info(f"Starting settings recheck worker (every {self._settings_recheck_interval}s)")
        Thread(target=self._settings_recheck_worker, daemon=True).start()

    def _settings_recheck_worker(self):
        """Periodically re-apply the current labels when the set of valid settings changed.

        AUTOCONF only reacts to orchestrator events, so a PRO license becoming valid (or any other
        out-of-band settings change) would otherwise never trigger a re-evaluation of labels that
        were dropped while invalid. This worker fills that gap. It is cheap in steady state: each
        tick is a single get_plugins() read plus a set comparison; the orchestrator queries and the
        forced apply only run when the settings set actually changed.
        """
        while True:
            sleep(self._settings_recheck_interval)
            try:
                with self._internal_lock:
                    if self.have_to_wait():
                        continue
                    self._update_settings()
                    if not self.settings_changed():
                        continue

                    self._logger.info("Available settings changed (e.g. PRO license now valid), re-checking autoconf labels...")
                    self._instances = self.get_instances()
                    self._services = self.get_services()
                    configs_result = self.get_configs()
                    # Kubernetes returns (extra_config, configs); others return configs.
                    if isinstance(configs_result, tuple) and len(configs_result) == 2:
                        self._extra_config, self._configs = configs_result
                    else:
                        self._configs = configs_result

                    # Re-check: the scheduler may have started applying since the first check above.
                    if self.have_to_wait():
                        continue

                    if self.apply_config(force=True):
                        self._set_autoconf_load_db()
                        self._logger.info("Successfully re-applied autoconf configuration after settings change 🚀")
                    else:
                        self._logger.error("Error while re-applying autoconf configuration after settings change")
            except BaseException:
                self._logger.error(f"Exception in settings recheck worker:\n{format_exc()}")

    def _configure_lock_watchdog(self):
        db = self._db
        request_budget = 0
        for uri in (db.database_uri, db.database_uri_readonly):
            if not uri:
                continue
            options = (
                {
                    "connect_timeout": db._connect_timeout,
                    "read_timeout": db._read_timeout,
                    "write_timeout": db._read_timeout,
                }
                | dict(make_url(uri).query)
                | db._engine_kwargs.get("connect_args", {})
            )
            # Disabled driver timeouts still need a finite watchdog fallback.
            request_budget = max(
                request_budget,
                sum(
                    float(options.get(key) or default)
                    for key, default in (
                        ("connect_timeout", DEFAULT_CONNECT_TIMEOUT),
                        ("read_timeout", DEFAULT_READ_TIMEOUT),
                        ("write_timeout", DEFAULT_READ_TIMEOUT),
                    )
                ),
            )
        # Three pool pre-ping attempts plus one statement per retry, pool waits, retry sleeps and a scheduling margin.
        attempts = db._request_retry_attempts
        self._lock_max_hold = max(
            LOCK_MAX_HOLD, attempts * (4 * request_budget + db._engine_kwargs["pool_timeout"]) + (attempts - 1) * db._request_retry_delay + 60
        )
        # Class listener also covers replacement engines after a read-only fallback.
        if not event.contains(Engine, "after_cursor_execute", self._database_progress):
            event.listen(Engine, "after_cursor_execute", self._database_progress)

    def _database_progress(self, connection, *_):
        # save_config also queries from its executor workers; other engines must not hide a stuck apply.
        if connection.engine is self._db.sql_engine:
            self._internal_lock.progress(database=True)

    def _check_lock_hold(self, healthy_path: Path, max_hold: float = None) -> bool:
        """Remove the healthy marker after a lock holder stops making progress, allowing a liveness probe to restart it."""
        if max_hold is None:
            max_hold = self._lock_max_hold
        held = self._internal_lock.stalled_for()
        if held <= max_hold:
            return False
        if healthy_path.exists():
            self._logger.error(
                f"The internal lock holder has made no progress for {int(held)}s (limit {int(max_hold)}s), a call is likely stuck: marking autoconf unhealthy"
            )
            with suppress(OSError):
                healthy_path.unlink(missing_ok=True)
        return True

    def _lock_watchdog(self, healthy_path: Path):
        while True:
            sleep(LOCK_WATCHDOG_INTERVAL)
            self._check_lock_hold(healthy_path)

    def _start_lock_watchdog(self, healthy_path: Path):
        self._configure_lock_watchdog()
        Thread(target=self._lock_watchdog, args=(healthy_path,), daemon=True).start()

    @abstractmethod
    def process_events(self):
        raise NotImplementedError

    def _is_service_present(self, server_name):
        if not isinstance(server_name, str):
            return False

        normalized_server_name = server_name.strip().split(" ")[0]
        if not normalized_server_name:
            return False

        for service in self._services:
            service_name = service.get("SERVER_NAME", "")
            if not service_name:
                continue
            if normalized_server_name == service_name.strip().split(" ")[0]:
                return True

        db_services = self._db.get_services()
        for service in db_services:
            db_service_name = service.get("id", "")
            if normalized_server_name == db_service_name:
                return True

        return False
