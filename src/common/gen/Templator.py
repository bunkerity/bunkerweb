#!/usr/bin/env python3

from concurrent.futures import ProcessPoolExecutor
from contextlib import suppress
from importlib import import_module
from glob import glob
from math import ceil
from os import cpu_count, getenv
from os.path import basename, join, sep
from pathlib import Path
from random import choice
from string import ascii_letters, digits
from sys import path as sys_path
from typing import Any, Dict, List, Optional, Type

# Correct the sys.path modification logic
deps_path = join("usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

from jinja2 import Environment, FileSystemBytecodeCache, FileSystemLoader, Undefined

# Configure logging
logger = setup_logger("Templator", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))


class ConfigurableCustomUndefined(Undefined):
    """A custom undefined class that can access configuration values."""

    # Class variable to store the config dictionary
    _config_dict = {}

    @classmethod
    def set_config(cls, config_dict: Dict[str, Any]):
        """Set the configuration dictionary for this class."""
        cls._config_dict = config_dict

    def __getattr__(self, name: str) -> Any:
        # First check if the original undefined name exists in config_dict
        if self._undefined_name and self._undefined_name in self._config_dict:
            base_value = self._config_dict[self._undefined_name]
            if hasattr(base_value, name):
                return getattr(base_value, name)

        # Check if the attribute access creates a valid config key
        if self._undefined_name:
            attr_key = f"{self._undefined_name}.{name}"
        else:
            attr_key = name

        if attr_key in self._config_dict:
            return self._config_dict[attr_key]

        # Return a new instance for chaining
        return self.__class__(name=attr_key)

    def __getitem__(self, key: str) -> Any:
        # First check if the original undefined name exists in config_dict
        if self._undefined_name and self._undefined_name in self._config_dict:
            base_value = self._config_dict[self._undefined_name]
            if hasattr(base_value, "__getitem__"):
                with suppress(KeyError, TypeError, IndexError):
                    return base_value[key]

        # Check if the item access creates a valid config key
        if self._undefined_name:
            item_key = f"{self._undefined_name}[{key}]"
        else:
            item_key = f"[{key}]"

        if item_key in self._config_dict:
            return self._config_dict[item_key]

        # Return a new instance for chaining
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
        self._jinja_env = self._load_jinja_env()
        self.__all_templates = frozenset(self._jinja_env.list_templates())
        self._template_path_cache = {}

        # Pre-categorize templates for faster lookup
        self._categorized_templates = self._categorize_templates()

        # Cache common template variables to avoid recreation
        self._base_template_vars = {
            "is_custom_conf": Templator.is_custom_conf,
            "has_variable": Templator.has_variable,
            "random": Templator.random,
            "read_lines": Templator.read_lines,
            "import": import_module,
        }

    def render(self) -> None:
        """Render the templates based on the provided configuration."""
        self._render_global()
        servers = [self._config.get("SERVER_NAME", "www.example.com").strip()]
        if self._config.get("MULTISITE", "no") == "yes":
            servers = self._config.get("SERVER_NAME", "www.example.com").strip().split(" ")

        max_workers = min(ceil(max(1, (cpu_count() or 1) * 0.75)), len(servers))
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._render_server, server) for server in servers]
            for future in futures:
                future.result()

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

        # Use pre-categorized templates for faster lookup
        for context in contexts:
            if context in self._categorized_templates:
                templates.extend(self._categorized_templates[context])

        # Remove duplicates while preserving order
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
            # Use more efficient string joining for large configs
            config_lines = [f"{k}={v}\n" for k, v in self._full_config.items()]
            real_path.write_text("".join(config_lines))
        except IOError as e:
            logger.error(f"Error writing configuration to {real_path}: {e}")

    def _get_server_config(self, server: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get the configuration for a specific server.

        Args:
            server (str): Server name.

        Returns:
            Dict[str, Any]: Configuration dictionary for the server.
        """
        prefix = f"{server}_"
        prefix_len = len(prefix)
        config["NGINX_PREFIX"] = f"{join(self._target, server)}/"

        # Efficient single-pass override of server-specific values
        for key, value in ((k, v) for k, v in config.copy().items() if k.startswith(prefix)):
            config[key[prefix_len:]] = value

        # Set default SERVER_NAME if not explicitly defined
        if f"{prefix}SERVER_NAME" not in config:
            config["SERVER_NAME"] = server

        return config

    def _render_global(self) -> None:
        """Render global templates."""
        self._write_config()
        templates = self._find_templates(
            [
                "global",
                "http",
                "stream",
                "default-server-http",
            ]
        )

        # Create template variables once and reuse
        template_vars = self._base_template_vars
        template_vars["all"] = self._full_config
        template_vars.update(self._config)

        max_workers = min(ceil(max(1, (cpu_count() or 1) * 0.75)), len(templates))
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self._render_template, template, template_vars) for template in templates]
            for future in futures:
                future.result()

    def _render_server(self, server: str) -> None:
        """Render templates for a specific server.

        Args:
            server (str): Server name.
        """
        # Step 1: Find all relevant templates
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

        # Step 2: Handle multisite configuration if applicable
        subpath = None
        config = self._config.copy()
        full_config = self._full_config.copy()
        default_config = self._default_config.copy()
        if self._config.get("MULTISITE", "no") == "yes":
            subpath = server
            config = self._get_server_config(server, config)
            full_config = self._get_server_config(server, full_config)
            default_config = self._get_server_config(server, default_config)

        server_custom_undefined = create_custom_undefined_class(default_config)

        template_vars = self._base_template_vars
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
                temp_env = Environment(
                    loader=self._jinja_env.loader,
                    lstrip_blocks=True,
                    trim_blocks=True,
                    keep_trailing_newline=True,
                    bytecode_cache=self._jinja_env.bytecode_cache,
                    auto_reload=False,
                    cache_size=-1,
                    undefined=custom_undefined,
                )
                jinja_template = temp_env.get_template(template)
            else:
                jinja_template = self._jinja_env.get_template(template)

            real_path.parent.mkdir(parents=True, exist_ok=True)
            with real_path.open("w") as f:
                f.write(jinja_template.render(template_vars))
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
