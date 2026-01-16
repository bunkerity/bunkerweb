#!/usr/bin/env python3

from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import suppress
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
from sys import path as sys_path
from time import perf_counter
from typing import Any, Dict, List, Optional, Type

deps_path = join("usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from common_utils import effective_cpu_count  # type: ignore
from logger import getLogger  # type: ignore

from jinja2 import Environment, FileSystemBytecodeCache, FileSystemLoader, Undefined

logger = getLogger("TEMPLATOR")


@lru_cache(maxsize=32)
def _supports_tls_group(name: str) -> bool:
    try:
        ctx = SSLContext(PROTOCOL_TLS_SERVER)
        ctx.set_ecdh_curve(name)
        return True
    except BaseException:
        return False


@lru_cache(maxsize=1)
def _best_ssl_ecdh_curve() -> Optional[str]:
    preferred = ("X25519MLKEM768", "X25519", "prime256v1", "secp384r1")
    aliases = {"prime256v1": ("P-256",), "secp384r1": ("P-384",)}

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


def resolve_ssl_ecdh_curve(value: str, fallback: str = "X25519:prime256v1:secp384r1") -> str:
    if value and value != "auto":
        return value

    best_curve = _best_ssl_ecdh_curve()
    if best_curve:
        return best_curve

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

        self._base_template_vars = {
            "is_custom_conf": Templator.is_custom_conf,
            "has_variable": Templator.has_variable,
            "random": Templator.random,
            "read_lines": Templator.read_lines,
            "import": import_module,
            "resolve_ssl_ecdh_curve": resolve_ssl_ecdh_curve,
        }

        self._server_env_cache: Dict[str, Environment] = {}

    def render(self) -> None:
        """Render the templates based on the provided configuration."""
        _ensure_fork_start_method()
        self._render_global()
        servers = [self._config.get("SERVER_NAME", "www.example.com").strip()]
        if self._config.get("MULTISITE", "no") == "yes":
            servers = self._config.get("SERVER_NAME", "www.example.com").strip().split()

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

    def _load_jinja_env(self) -> Environment:
        """Load the Jinja2 environment with the appropriate search paths.

        Returns:
            Environment: The Jinja2 environment.
        """
        searchpath = [self._templates]
        searchpath.extend(p.as_posix() for p in (*self._core.glob("*/confs"), *self._plugins.glob("*/confs"), *self._pro_plugins.glob("*/confs")) if p.is_dir())
        return Environment(
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

    def _write_config(self) -> None:
        """Write the configuration to a variables.env file."""
        real_path = self._output / "variables.env"
        try:
            real_path.parent.mkdir(parents=True, exist_ok=True)
            config_lines = [f"{k}={v}\n" for k, v in self._full_config.items()]
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

        filtered_config["NGINX_PREFIX"] = f"{join(self._target, server)}/"

        if "SERVER_NAME" not in filtered_config:
            filtered_config["SERVER_NAME"] = server

        return filtered_config

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
                    self._server_env_cache[cache_key] = Environment(
                        loader=self._jinja_env.loader,
                        lstrip_blocks=True,
                        trim_blocks=True,
                        keep_trailing_newline=True,
                        bytecode_cache=self._jinja_env.bytecode_cache,
                        auto_reload=False,
                        cache_size=-1,
                        undefined=custom_undefined,
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
