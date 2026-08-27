#!/usr/bin/env python3

from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import suppress
from ctypes import CDLL, c_char_p, c_int, c_long, c_void_p
from ctypes.util import find_library
from functools import lru_cache
from importlib import import_module
from glob import glob
from math import ceil
import multiprocessing as mp
from os.path import basename, join, sep
from pathlib import Path
from random import choice
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from string import ascii_letters, digits
from re import search as re_search, escape as re_escape
from subprocess import run
from sys import path as sys_path
from time import perf_counter
from typing import Any, Dict, List, Optional, Type

deps_path = join("usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from common_utils import effective_cpu_count  # type: ignore
from logger import getLogger  # type: ignore
from common_utils import get_integration  # type: ignore
from ports import (  # type: ignore
    HTTPS_PORT_SETTING,
    HTTP_PORT_SETTING,
    check_ports,
    drop_inherited_ports,
    inherited_port_keys,
    reserved_ports,
    stream_reuseport_owners,
    union_ports,
)

from jinja2 import Environment, FileSystemBytecodeCache, FileSystemLoader, Undefined

logger = getLogger("TEMPLATOR")
_ssl_ecdh_curve_resolution_logged = False


@lru_cache(maxsize=1)
def _set1_groups_list_probe():
    """Return a callable(group)->bool using the SAME call nginx makes for ssl_ecdh_curve
    (SSL_CTX_set1_groups_list), or None if libssl can't be bound. Faithful oracle:
    ssl.set_ecdh_curve() uses a different name table and ignores provider/FIPS policy, so it
    can pass a group nginx then refuses; set1_groups_list mirrors the active provider exactly.
    """
    try:
        SSL_CTRL_SET_GROUPS_LIST = 92  # == SSL_CTRL_SET_CURVES_LIST

        # find_library() returns None on musl/Alpine and slim images often lack the unversioned
        # libssl.so, so try the versioned sonames too.
        lib = None
        for _cand in (find_library("ssl"), "libssl.so.3", "libssl.so", "libssl.so.1.1"):
            if not _cand:
                continue
            try:
                lib = CDLL(_cand)
                break
            except OSError:
                continue
        if lib is None:
            logger.warning(
                "ssl_ecdh_curve: could not bind libssl for the faithful set1_groups_list probe; "
                "falling back to the looser ssl.set_ecdh_curve detection (FIPS-blind)"
            )
            return None
        lib.TLS_server_method.restype = c_void_p
        lib.SSL_CTX_new.restype = c_void_p
        lib.SSL_CTX_new.argtypes = [c_void_p]
        lib.SSL_CTX_ctrl.restype = c_long
        lib.SSL_CTX_ctrl.argtypes = [c_void_p, c_int, c_long, c_char_p]
        lib.SSL_CTX_free.argtypes = [c_void_p]

        def _probe(group: str) -> bool:
            try:
                method = lib.TLS_server_method()
                ctx = lib.SSL_CTX_new(method) if method else None
                if not ctx:
                    return False
                try:
                    return lib.SSL_CTX_ctrl(ctx, SSL_CTRL_SET_GROUPS_LIST, 0, group.encode("ascii")) == 1
                finally:
                    lib.SSL_CTX_free(ctx)
            except BaseException:
                return False

        # Smoke test: a real group must pass and a bogus one fail, else the binding is wrong.
        if not _probe("prime256v1") or _probe("bunkerweb-not-a-real-group"):
            logger.warning(
                "ssl_ecdh_curve: set1_groups_list smoke test failed (unexpected libssl/ctrl); "
                "falling back to the looser ssl.set_ecdh_curve detection (FIPS-blind)"
            )
            return None
        return _probe
    except BaseException:
        logger.warning("ssl_ecdh_curve: faithful set1_groups_list probe unavailable; using ssl.set_ecdh_curve (FIPS-blind)")
        return None


@lru_cache(maxsize=64)
def _supports_tls_group(name: str) -> bool:
    probe = _set1_groups_list_probe()
    if probe is not None:
        return probe(name)

    # Degraded fallback (libssl unbindable): looser, FIPS-blind, but better than nothing.
    with suppress(BaseException):
        ctx = SSLContext(PROTOCOL_TLS_SERVER)
        ctx.set_ecdh_curve(name)
        return True

    # set_ecdh_curve() misses PQC hybrids (e.g. X25519MLKEM768); try the CLI listing last.
    try:
        result = run(["openssl", "list", "-kem-algorithms"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and re_search(r"\b" + re_escape(name) + r"\b", result.stdout):
            return True
    except BaseException:
        logger.debug(f"OpenSSL CLI fallback failed for TLS group '{name}'")

    return False


@lru_cache(maxsize=1)
def _best_ssl_ecdh_curve() -> Optional[str]:
    # PQC-hybrid first, then classical CFRG/NIST. Keep every probed-supported group, so a
    # FIPS OpenSSL (rejects X25519/X448) lands on its NIST subset automatically.
    preferred = ("X25519MLKEM768", "X25519", "prime256v1", "secp384r1", "secp521r1", "X448")
    aliases = {"prime256v1": ("P-256",), "secp384r1": ("P-384",), "secp521r1": ("P-521",)}

    selected = []
    for name in preferred:
        if _supports_tls_group(name):
            selected.append(name)
            continue
        for alias in aliases.get(name, []):
            if _supports_tls_group(alias):
                selected.append(alias)
                break

    if not selected:
        return None

    return ":".join(selected)


def resolve_ssl_ecdh_curve(value: str, fallback: str = "prime256v1:secp384r1") -> str:
    global _ssl_ecdh_curve_resolution_logged

    if value and value != "auto":
        return value

    best_curve = _best_ssl_ecdh_curve()
    if best_curve:
        if not _ssl_ecdh_curve_resolution_logged:
            logger.debug(f"Resolved ssl_ecdh_curve (auto-detect): {best_curve}")
            _ssl_ecdh_curve_resolution_logged = True
        return best_curve

    if not _ssl_ecdh_curve_resolution_logged:
        logger.warning(f"Resolved ssl_ecdh_curve (fallback): {fallback}")
        _ssl_ecdh_curve_resolution_logged = True
    return fallback


class ConfigurableCustomUndefined(Undefined):
    """A custom undefined class that can access configuration values."""

    _config_dict = {}

    @classmethod
    def set_config(cls, config_dict: Dict[str, Any]):
        """Set the configuration dictionary for this class."""
        cls._config_dict = config_dict

    def __getattr__(self, name: str) -> Any:
        if self._undefined_name and self._undefined_name in self._config_dict:
            base_value = self._config_dict[self._undefined_name]
            if hasattr(base_value, name):
                return getattr(base_value, name)

        if self._undefined_name:
            attr_key = f"{self._undefined_name}.{name}"
        else:
            attr_key = name

        if attr_key in self._config_dict:
            return self._config_dict[attr_key]

        return self.__class__(name=attr_key)

    def __getitem__(self, key: str) -> Any:
        if self._undefined_name and self._undefined_name in self._config_dict:
            base_value = self._config_dict[self._undefined_name]
            if hasattr(base_value, "__getitem__"):
                with suppress(KeyError, TypeError, IndexError):
                    return base_value[key]

        if self._undefined_name:
            item_key = f"{self._undefined_name}[{key}]"
        else:
            item_key = f"[{key}]"

        if item_key in self._config_dict:
            return self._config_dict[item_key]

        return self.__class__(name=item_key)

    def __eq__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                if other == "" and isinstance(value, str):
                    value = value.strip()
                return value == other
        return super().__eq__(other)

    def __ne__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                if other == "" and isinstance(value, str):
                    value = value.strip()
                return value != other
        return super().__ne__(other)

    def __repr__(self) -> str:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                return repr(value)
        return super().__repr__()

    def __lt__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                with suppress(TypeError):
                    return value < other
        return super().__lt__(other)

    def __le__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                with suppress(TypeError):
                    return value <= other
        return super().__le__(other)

    def __gt__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                with suppress(TypeError):
                    return value > other
        return super().__gt__(other)

    def __ge__(self, other: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                with suppress(TypeError):
                    return value >= other
        return super().__ge__(other)

    def __str__(self) -> str:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                return str(value)
        return super().__str__()

    def __len__(self) -> int:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None and hasattr(value, "__len__"):
                return len(value)
        return super().__len__()

    def __iter__(self):
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None and hasattr(value, "__iter__"):
                return iter(value)
        return super().__iter__()

    def __bool__(self) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None:
                if isinstance(value, str):
                    value = value.strip()
                return bool(value)
        return super().__bool__()

    def __contains__(self, item: Any) -> bool:
        if self._undefined_name:
            value = self._config_dict.get(self._undefined_name)
            if value is not None and hasattr(value, "__contains__"):
                return item in value
        return False


def create_custom_undefined_class(default_config: Dict[str, Any]):
    """Factory function that returns ConfigurableCustomUndefined with the config set."""
    ConfigurableCustomUndefined.set_config(default_config)
    return ConfigurableCustomUndefined


def _ensure_fork_start_method() -> None:
    """Force fork start method when available so child processes inherit globals."""
    with suppress(RuntimeError):
        if mp.get_start_method(allow_none=True) != "fork":
            mp.set_start_method("fork")


class Templator:
    """A class to render configuration files using Jinja2 templates."""

    def __init__(
        self,
        templates: str,
        core: str,
        plugins: str,
        pro_plugins: str,
        output: str,
        target: str,
        config: Dict[str, Any],
        default_config: Dict[str, Any],
        full_config: Dict[str, Any],
    ):
        """Initialize the Templator with paths and configuration.

        Args:
            templates (str): Path to the templates directory.
            core (str): Path to the core directory.
            plugins (str): Path to the plugins directory.
            pro_plugins (str): Path to the pro plugins directory.
            output (str): Path to the output directory.
            target (str): Target path.
            config (Dict[str, Any]): Configuration dictionary.
        """
        if not isinstance(templates, str):
            raise TypeError("templates must be a string")
        if not isinstance(core, str):
            raise TypeError("core must be a string")
        if not isinstance(plugins, str):
            raise TypeError("plugins must be a string")
        if not isinstance(pro_plugins, str):
            raise TypeError("pro_plugins must be a string")
        if not isinstance(output, str):
            raise TypeError("output must be a string")
        if not isinstance(target, str):
            raise TypeError("target must be a string")
        if not isinstance(config, dict):
            raise TypeError("config must be a dictionary")

        self._jinja_cache_dir = Path(sep, "var", "cache", "bunkerweb", "jinja_cache")
        self._jinja_cache_dir.mkdir(parents=True, exist_ok=True)
        self._templates = templates
        self._global_templates = frozenset(template.name for template in Path(self._templates).rglob("*.conf"))
        self._core = Path(core)
        self._plugins = Path(plugins)
        self._pro_plugins = Path(pro_plugins)
        self._output = Path(output)  # Convert to Path for efficiency
        self._target = target
        self._config = config
        self._default_config = default_config
        self._full_config = full_config
        self._custom_undefined = create_custom_undefined_class(default_config)

        if config.get("MULTISITE", "no") == "yes":
            server_names = config.get("SERVER_NAME", "www.example.com").strip().split()
            self._server_prefixes = frozenset(f"{s}_" for s in server_names)
            self._server_names_set = frozenset(server_names)

            def is_global_key(key: str) -> bool:
                """Check if a key is a global setting (not prefixed by any server name)."""
                idx = 0
                while True:
                    underscore_pos = key.find("_", idx)
                    if underscore_pos == -1:
                        return True
                    potential_server = key[:underscore_pos]
                    if potential_server in self._server_names_set:
                        return False
                    idx = underscore_pos + 1

            self._global_only_config = {k: v for k, v in config.items() if is_global_key(k)}
            self._global_only_full_config = {k: v for k, v in full_config.items() if is_global_key(k)}
            self._global_only_default_config = {k: v for k, v in default_config.items() if is_global_key(k)}

            self._server_specific_config: Dict[str, Dict[str, Any]] = {s: {} for s in server_names}
            self._server_specific_full_config: Dict[str, Dict[str, Any]] = {s: {} for s in server_names}
            self._server_specific_default_config: Dict[str, Dict[str, Any]] = {s: {} for s in server_names}

            def extract_server_and_key(key: str) -> tuple:
                """Efficiently extract server name and stripped key from a prefixed config key."""
                idx = 0
                while True:
                    underscore_pos = key.find("_", idx)
                    if underscore_pos == -1:
                        return None, None
                    potential_server = key[:underscore_pos]
                    if potential_server in self._server_names_set:
                        return potential_server, key[underscore_pos + 1 :]  # noqa: E203
                    idx = underscore_pos + 1

            for key, value in config.items():
                server, stripped_key = extract_server_and_key(key)
                if server:
                    self._server_specific_config[server][stripped_key] = value

            for key, value in full_config.items():
                server, stripped_key = extract_server_and_key(key)
                if server:
                    self._server_specific_full_config[server][stripped_key] = value

            for key, value in default_config.items():
                server, stripped_key = extract_server_and_key(key)
                if server:
                    self._server_specific_default_config[server][stripped_key] = value
        else:
            self._server_prefixes = frozenset()
            self._server_names_set = frozenset()
            self._global_only_config = config
            self._global_only_full_config = full_config
            self._global_only_default_config = default_config
            self._server_specific_config = {}
            self._server_specific_full_config = {}
            self._server_specific_default_config = {}

        self._jinja_env = self._load_jinja_env()
        self.__all_templates = frozenset(self._jinja_env.list_templates())

        self._template_path_cache = {}

        self._categorized_templates = self._categorize_templates()

        # `reuseport` is a listen OPTION and NGINX binds listen options to the addr:port, not to the
        # server block: a second block setting one on the same addr:port is fatal
        # (src/deps/src/nginx/src/stream/ngx_stream.c:489-497). A template only ever sees its own
        # block, so the owner of each stream addr:port is elected HERE, where every service is
        # visible, and handed to the template as STREAM_REUSEPORT_PORTS.
        service_configs = self._service_configs()
        self._stream_reuseport_ports = stream_reuseport_owners(service_configs)

        # The default server is rendered globally, with the global configuration, so it used to
        # listen on the global ports only. Now that a service can declare a port of its own, a port
        # nobody else covers has NO default_server -- and the first block declared on it silently
        # becomes the implicit default, which takes DISABLE_DEFAULT_SERVER and the strict-SNI
        # rejection off that port. Measured, not assumed: spike S2 in the ports report shows an
        # unknown SNI completing the handshake with that service's certificate. The union closes it.
        self._all_http_ports = union_ports(self._full_config, service_configs, HTTP_PORT_SETTING)
        self._all_https_ports = union_ports(self._full_config, service_configs, HTTPS_PORT_SETTING)

        self._report_port_issues(service_configs)

        self._base_template_vars = {
            "is_custom_conf": Templator.is_custom_conf,
            "has_variable": Templator.has_variable,
            "random": Templator.random,
            "read_lines": Templator.read_lines,
            "import": import_module,
            "resolve_ssl_ecdh_curve": resolve_ssl_ecdh_curve,
            "normalize_memory_size": Templator._normalize_memory_size,
        }

        self._server_env_cache: Dict[str, Environment] = {}

    def render(self) -> None:
        """Render the templates based on the provided configuration."""
        global _ssl_ecdh_curve_resolution_logged

        _ensure_fork_start_method()
        _ssl_ecdh_curve_resolution_logged = False
        if self._uses_auto_ssl_ecdh_curve():
            resolve_ssl_ecdh_curve("auto")
        self._render_global()
        server_name = self._config.get("SERVER_NAME", "www.example.com").strip()
        # an empty SERVER_NAME renders no server at all, like multisite already does, instead of an
        # empty server_name directive that NGINX refuses
        servers = [server_name] if server_name else []
        if self._config.get("MULTISITE", "no") == "yes":
            servers = server_name.split()

        effective_cpus = effective_cpu_count()
        if len(servers) >= effective_cpus * 2:
            worker_target = effective_cpus
        else:
            worker_target = min(effective_cpus, max(1, ceil(effective_cpus * 0.75)))
        max_workers = min(worker_target, len(servers)) or 1
        batch_size = max(1, ceil(len(servers) / max_workers))

        server_start = perf_counter()
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {}
            for i in range(0, len(servers), batch_size):
                batch = servers[i : i + batch_size]  # noqa: E203
                future = executor.submit(self._render_server_batch, batch)
                future_to_batch[future] = len(batch)

            completed_servers = 0
            show_progress = len(servers) >= 100
            for future in as_completed(future_to_batch):
                future.result()  # Raise any exceptions
                completed_servers += future_to_batch[future]
                if show_progress:
                    progress_pct = (completed_servers / len(servers)) * 100
                    elapsed = perf_counter() - server_start
                    logger.info(f"Progress: {completed_servers}/{len(servers)} servers ({progress_pct:.1f}%) in {elapsed:.1f}s")

    def __getstate__(self) -> Dict[str, Any]:
        state = self.__dict__.copy()
        state.pop("_jinja_env", None)
        state.pop("_custom_undefined", None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._custom_undefined = create_custom_undefined_class(self._default_config)
        if not hasattr(self, "_jinja_env") or self._jinja_env is None:
            self._jinja_env = self._load_jinja_env()
            self.__all_templates = frozenset(self._jinja_env.list_templates())
            self._template_path_cache = {}
            if not hasattr(self, "_categorized_templates"):
                self._categorized_templates = self._categorize_templates()
            if not hasattr(self, "_server_env_cache"):
                self._server_env_cache = {}

            self._template_basename_map = {}
            for template in self.__all_templates:
                base = basename(template)
                if base in self._global_templates:
                    self._template_basename_map[template] = base

    @staticmethod
    def _is_auto_ssl_ecdh_curve(value: Any) -> bool:
        return not value or value == "auto"

    def _uses_auto_ssl_ecdh_curve(self) -> bool:
        global_value = self._config.get("SSL_ECDH_CURVE", self._default_config.get("SSL_ECDH_CURVE"))
        if Templator._is_auto_ssl_ecdh_curve(global_value):
            return True

        if self._config.get("MULTISITE", "no") != "yes":
            return False

        global_default = self._global_only_config.get("SSL_ECDH_CURVE", self._global_only_default_config.get("SSL_ECDH_CURVE"))
        for server_config in self._server_specific_config.values():
            if Templator._is_auto_ssl_ecdh_curve(server_config.get("SSL_ECDH_CURVE", global_default)):
                return True

        return False

    @staticmethod
    def _normalize_memory_size(value: str) -> str:
        """Convert g/G suffix to megabytes for NGINX lua_shared_dict compatibility.

        NGINX's ngx_parse_size() only supports k/m suffixes. The g/G suffix is only
        supported by ngx_parse_offset() (used for file/body sizes, not memory allocations).

        Uses ``float()`` so the converter still works if the upstream regex is ever
        relaxed to accept decimal values (e.g. ``1.5g``); the result is rounded down
        to an integer megabyte count because NGINX's ``m`` suffix requires an integer.
        """
        value = value.strip()
        if value.endswith(("g", "G")):
            return f"{int(float(value[:-1]) * 1024)}m"
        return value

    def _load_jinja_env(self) -> Environment:
        """Load the Jinja2 environment with the appropriate search paths.

        Returns:
            Environment: The Jinja2 environment.
        """
        searchpath = [self._templates]
        searchpath.extend(p.as_posix() for p in (*self._core.glob("*/confs"), *self._plugins.glob("*/confs"), *self._pro_plugins.glob("*/confs")) if p.is_dir())
        return Environment(  # nosec B701 - rendering NGINX config files (not HTML); HTML autoescape would corrupt valid NGINX syntax.
            loader=FileSystemLoader(searchpath=searchpath),
            lstrip_blocks=True,
            trim_blocks=True,
            keep_trailing_newline=True,
            bytecode_cache=FileSystemBytecodeCache(directory=self._jinja_cache_dir.as_posix()),
            auto_reload=False,
            cache_size=-1,
            undefined=self._custom_undefined,
        )

    def _categorize_templates(self) -> Dict[str, List[str]]:
        """Pre-categorize templates by context for faster lookup.

        Returns:
            Dict[str, List[str]]: Dictionary mapping context names to template lists.
        """
        categories = {
            "global": [],
            "http": [],
            "stream": [],
            "default-server-http": [],
            "modsec": [],
            "modsec-crs": [],
            "crs-plugins-before": [],
            "crs-plugins-after": [],
            "server-http": [],
            "server-stream": [],
        }

        for template in self.__all_templates:
            if "/" not in template:
                categories["global"].append(template)
            else:
                context = template.split("/", 1)[0]
                if context in categories:
                    categories[context].append(template)

        return categories

    def _find_templates(self, contexts: List[str]) -> List[str]:
        """Find templates matching the given contexts.

        Args:
            contexts (List[str]): List of context names.

        Returns:
            List[str]: List of template names in the same order as contexts.
        """
        cache_key = frozenset(contexts)
        if cache_key in self._template_path_cache:
            return self._template_path_cache[cache_key]

        templates = []

        for context in contexts:
            if context in self._categorized_templates:
                templates.extend(self._categorized_templates[context])

        seen = set()
        result = []
        for template in templates:
            if template not in seen:
                seen.add(template)
                result.append(template)

        self._template_path_cache[cache_key] = result
        return result

    def _report_port_issues(self, service_configs: Dict[str, Dict[str, Any]]) -> None:
        """Log the listen-port conflicts this configuration carries, once, at generation time.

        Here rather than in ``Configurator`` because Configurator is only on the ENVIRONMENT path:
        ``src/common/core/jobs/jobs/push-configs.py:362-379`` runs ``gen/main.py`` with no
        ``--variables``, so the database render never constructs one — and the database is where
        per-service ports are declared, so the deployments that can actually collide were the ones
        getting no report. Templator is the single object both paths build.

        ``service_configs`` is the post-merge, post-``drop_inherited_ports`` view, i.e. the ports
        each block will really bind. Feeding the raw config instead would credit every service with
        the fleet's whole list and miss both directions: a collision on a port only one service
        declares, and a service that VACATED a global port.

        Warn, never ``exit(1)``: this runs on the boot path and refusing to generate over a port the
        operator may well have meant would take a whole fleet down. Refusal belongs to the write
        paths (API/UI), where an operator is in front of the error and one service is at stake.
        """
        containerized = get_integration() != "Linux"
        # /etc/supervisor.d only exists in the all-in-one image (src/all-in-one/Dockerfile:252),
        # which is the only layout where the UI (7000) and the API service (8888) share this
        # network namespace and are therefore unavailable to a service.
        all_in_one = containerized and Path(sep, "etc", "supervisor.d").is_dir()
        with suppress(Exception):
            for issue in check_ports(
                service_configs,
                reserved=reserved_ports(self._full_config, all_in_one=all_in_one),
                containerized=containerized,
            ):
                if issue.level == "fatal":
                    logger.error(f"Listen port conflict : {issue.message}")
                else:
                    logger.warning(f"Listen port warning : {issue.message}")

    def _inherited_port_keys(self) -> List[str]:
        """The ``<service>_HTTP_PORT*`` / ``<service>_HTTPS_PORT*`` keys of ``_full_config`` that
        the service did NOT declare, and that its rendered ``listen`` lines therefore do not carry.

        `variables.env` is the Lua side's only view of the configuration, and
        `utils.listen_port_override` reads a service's port list straight out of it to decide which
        port an absolute URL must carry. The full config is the INHERITED view on purpose (the
        per-service editor needs it, `config_read.py:186-210`), so without this the Lua answer is
        the global port for a service that declared only a repetition of its own -- a port its
        block does not even listen on.

        Same discriminator as :meth:`_get_server_config`: `_server_specific_config` is built from
        the non-default settings, so a key is there only if the service really declared it.
        """
        dropped: List[str] = []
        for server, inherited in self._server_specific_full_config.items():
            dropped.extend(f"{server}_{key}" for key in inherited_port_keys(inherited, self._server_specific_config.get(server, {})))
        return dropped

    def _write_config(self) -> None:
        """Write the configuration to a variables.env file."""
        real_path = self._output / "variables.env"
        try:
            real_path.parent.mkdir(parents=True, exist_ok=True)
            inherited_ports = frozenset(self._inherited_port_keys())
            config_lines = [f"{k}={v}\n" for k, v in self._full_config.items() if k not in inherited_ports]
            real_path.write_text("".join(config_lines))
        except IOError as e:
            logger.error(f"Error writing configuration to {real_path}: {e}")

    def _get_server_config(self, server: str, global_only_config: Dict[str, Any], server_specific_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get the configuration for a specific server.

        Args:
            server (str): Server name.
            global_only_config (Dict[str, Any]): Pre-filtered global-only settings.
            server_specific_config (Dict[str, Any]): Pre-grouped server-specific settings (already stripped).

        Returns:
            Dict[str, Any]: Configuration dictionary for the server (filtered).
        """
        filtered_config = global_only_config.copy()

        filtered_config.update(server_specific_config)

        # A service that declares a listen port REPLACES the global list rather than adding to it
        # (conception §2.2). This is the only place BOTH generation paths converge, and they need
        # different work: the environment path arrives pre-blanked from Configurator (every service
        # key is materialised there, so nothing is "inherited" and this is a no-op), while the
        # scheduler path runs through `src/common/core/jobs/jobs/push-configs.py:362-379`, which calls
        # gen/main.py with no `--variables` -- gen/main.py:128 therefore takes
        # `db.get_non_default_settings()` and never calls Configurator at all. Every port declared
        # through the UI, the API or autoconf comes in that way, and without this the service listened
        # on its own port AND on every global repetition.
        #
        # `_server_specific_config` is the discriminator on purpose: it is built from the
        # non-default settings, so a key is present there only if the service really declared it.
        # `_server_specific_full_config` cannot answer the question -- `get_config` fills the
        # inherited copies in (config_read.py:205-210, which the per-service editor needs), so every
        # service looks there like it declared everything.
        drop_inherited_ports(filtered_config, self._server_specific_config.get(server, {}))

        filtered_config["NGINX_PREFIX"] = f"{join(self._target, server)}/"

        if "SERVER_NAME" not in filtered_config:
            filtered_config["SERVER_NAME"] = server

        return filtered_config

    def _service_configs(self) -> Dict[str, Dict[str, Any]]:
        """``{service: effective config}`` in SERVER_NAME order, the view each block renders with.

        Same merge as :meth:`_get_server_config` because it is the same question: what a server
        block actually sees. Non-multisite has a single block, which then owns all of its ports and
        renders exactly as it did before the ownership rule existed.
        """
        # Same fallback as :meth:`render` (:474) and the prefix build (:369). A different default
        # here would hand the reuseport election and the port unions a service list the renderer
        # never renders -- not reachable today, since every caller sets SERVER_NAME, and left
        # aligned so it stays that way.
        server_name = str(self._config.get("SERVER_NAME", "www.example.com")).strip()
        if self._config.get("MULTISITE", "no") != "yes":
            return {server_name: self._full_config} if server_name else {}
        return {
            server: self._get_server_config(server, self._global_only_full_config, self._server_specific_full_config.get(server, {}))
            for server in server_name.split()
        }

    def _render_global(self) -> None:
        """Render global templates."""
        global_start = perf_counter()

        self._write_config()
        templates = self._find_templates(
            [
                "global",
                "http",
                "stream",
                "default-server-http",
            ]
        )

        template_vars = self._base_template_vars.copy()
        template_vars["all"] = self._full_config
        template_vars.update(self._config)
        # Derived, never settings: set after update() so no configuration key can shadow them.
        template_vars["ALL_HTTP_PORTS"] = self._all_http_ports
        template_vars["ALL_HTTPS_PORTS"] = self._all_https_ports

        for template in templates:
            self._render_template(template, template_vars)
        logger.debug(f"Global rendering completed in {perf_counter() - global_start:.3f}s")

    def _render_server_batch(self, servers: List[str]) -> None:
        """Render templates for a batch of servers.

        Args:
            servers (List[str]): List of server names to render.
        """
        for server in servers:
            self._render_server(server)

    def _render_server(self, server: str) -> None:
        """Render templates for a specific server.

        Args:
            server (str): Server name.
        """
        templates = self._find_templates(
            [
                "modsec",
                "modsec-crs",
                "crs-plugins-before",
                "crs-plugins-after",
                "server-http",
                "server-stream",
            ]
        )

        subpath = None
        config = self._config.copy()
        full_config = self._full_config.copy()
        default_config = self._default_config.copy()
        if self._config.get("MULTISITE", "no") == "yes":
            subpath = server
            config = self._get_server_config(server, self._global_only_config, self._server_specific_config.get(server, {}))
            full_config = self._get_server_config(server, self._global_only_full_config, self._server_specific_full_config.get(server, {}))
            default_config = self._get_server_config(server, self._global_only_default_config, self._server_specific_default_config.get(server, {}))

        server_custom_undefined = create_custom_undefined_class(default_config)

        template_vars = self._base_template_vars.copy()
        template_vars["all"] = full_config
        template_vars.update(config)
        # Set AFTER update(config) on purpose: this is a derived variable, never a setting, and a
        # configuration key must not be able to shadow it.
        template_vars["STREAM_REUSEPORT_PORTS"] = self._stream_reuseport_ports.get(server, frozenset())

        for template in templates:
            name = basename(template) if any(template.endswith(root_conf) for root_conf in self._global_templates) else None
            self._render_template(template, template_vars, subpath=subpath, name=name, custom_undefined=server_custom_undefined)

    def _render_template(
        self,
        template: str,
        template_vars: Optional[Dict[str, Any]] = None,
        subpath: Optional[str] = None,
        name: Optional[str] = None,
        custom_undefined: Optional[Type[Undefined]] = None,
    ) -> None:
        """Render a single template.

        Args:
            template (str): Template name.
            subpath (Optional[str], optional): Subpath under the output directory. Defaults to None.
            config (Optional[Dict[str, Any]], optional): Configuration dictionary. Defaults to None.
            name (Optional[str], optional): Output file name. Defaults to None.
        """
        real_path = Path(self._output, subpath or "", name or template)
        try:
            if custom_undefined:
                cache_key = "server_env"
                if cache_key not in self._server_env_cache:
                    self._server_env_cache[cache_key] = (
                        Environment(  # nosec B701 - rendering NGINX config files (not HTML); HTML autoescape would corrupt valid NGINX syntax.
                            loader=self._jinja_env.loader,
                            lstrip_blocks=True,
                            trim_blocks=True,
                            keep_trailing_newline=True,
                            bytecode_cache=self._jinja_env.bytecode_cache,
                            auto_reload=False,
                            cache_size=-1,
                            undefined=custom_undefined,
                        )
                    )
                jinja_template = self._server_env_cache[cache_key].get_template(template)
            else:
                jinja_template = self._jinja_env.get_template(template)

            real_path.parent.mkdir(parents=True, exist_ok=True)

            rendered_content = jinja_template.render(template_vars)
            real_path.write_text(rendered_content)
        except Exception as e:
            logger.error(f"Error rendering template {template}: {e}")

    @staticmethod
    def is_custom_conf(path: str) -> bool:
        """Check if the path contains any .conf files.

        Args:
            path (str): Path to check.

        Returns:
            bool: True if .conf files are found, False otherwise.
        """
        return bool(glob(join(path, "*.conf")))

    @staticmethod
    def has_variable(all_vars: Dict[str, Any], variable: str, value: Any) -> bool:
        """Check if the variable has the specified value.

        Args:
            all_vars (Dict[str, Any]): Configuration variables.
            variable (str): Variable name.
            value (Any): Value to check against.

        Returns:
            bool: True if the variable has the specified value, False otherwise.
        """
        if all_vars.get(variable) == value:
            return True
        elif all_vars.get("MULTISITE", "no") == "yes":
            server_names = all_vars.get("SERVER_NAME", "").strip().split()
            for server_name in server_names:
                if all_vars.get(f"{server_name}_{variable}") == value:
                    return True
        return False

    @staticmethod
    def random(nb: int, characters: str = ascii_letters + digits) -> str:
        """Generate a random string of specified length.

        Args:
            nb (int): Length of the random string.
            characters (str, optional): Characters to choose from. Defaults to ascii_letters + digits.

        Returns:
            str: Random string.
        """
        return "".join(choice(characters) for _ in range(nb))

    @staticmethod
    def read_lines(file: str) -> List[str]:
        """Read lines from a file.

        Args:
            file (str): Path to the file.

        Returns:
            List[str]: List of lines, or empty list if file not found.
        """
        try:
            return Path(file).read_text().splitlines()
        except FileNotFoundError:
            return []
