#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from glob import glob
from os import getenv
from os.path import basename, join, sep
from pathlib import Path
from random import choice
from string import ascii_letters, digits
from sys import path as sys_path
from typing import Any, Dict, List, Optional

# Correct the sys.path modification logic
deps_path = join("usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

from jinja2 import Environment, FileSystemBytecodeCache, FileSystemLoader

# Configure logging
logger = setup_logger("Templator", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))


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
        self._global_templates = [template.name for template in Path(self._templates).glob("**/*.conf")]
        self._core = Path(core)
        self._plugins = Path(plugins)
        self._pro_plugins = Path(pro_plugins)
        self._output = output
        self._target = target
        self._config = config
        self._jinja_env = self._load_jinja_env()

    def render(self) -> None:
        """Render the templates based on the provided configuration."""
        self._render_global()
        servers = [self._config.get("SERVER_NAME", "").strip()]
        if self._config.get("MULTISITE", "no") == "yes":
            servers = self._config.get("SERVER_NAME", "").strip().split(" ")
        for server in servers:
            self._render_server(server)

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
        )

    def _find_templates(self, contexts: List[str]) -> List[str]:
        """Find templates matching the given contexts.

        Args:
            contexts (List[str]): List of context names.

        Returns:
            List[str]: List of template names.
        """
        templates = set()
        all_templates = frozenset(self._jinja_env.list_templates())

        # Handle global context specially for better performance
        if "global" in contexts:
            templates.update(t for t in all_templates if "/" not in t)
            contexts.remove("global")

        # Process remaining contexts
        if contexts:
            prefix_set = tuple(context + "/" for context in contexts)
            templates.update(t for t in all_templates if any(t.startswith(prefix) for prefix in prefix_set))

        return list(templates)

    def _write_config(self, subpath: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Write the configuration to a variables.env file.

        Args:
            subpath (Optional[str], optional): Subpath under the output directory. Defaults to None.
            config (Optional[Dict[str, Any]], optional): Configuration dictionary. Defaults to None.
        """
        real_config = config if config is not None else self._config
        real_path = Path(self._output, subpath or "", "variables.env")
        try:
            real_path.parent.mkdir(parents=True, exist_ok=True)
            real_path.write_text("".join(f"{k}={v}\n" for k, v in real_config.items()))
        except IOError as e:
            logger.error(f"Error writing configuration to {real_path}: {e}")

    def _get_server_config(self, server: str) -> Dict[str, Any]:
        """Get the configuration for a specific server.

        Args:
            server (str): Server name.

        Returns:
            Dict[str, Any]: Configuration dictionary for the server.
        """
        config = {}
        prefix = f"{server}_"
        prefix_len = len(prefix)

        # Pre-populate with base config and handle NGINX_PREFIX
        config.update(self._config)
        config["NGINX_PREFIX"] = join(self._target, server) + "/"

        # Efficient single-pass override of server-specific values
        for key, value in ((k, v) for k, v in self._config.items() if k.startswith(prefix)):
            config[key[prefix_len:]] = value

        # Set default SERVER_NAME if not explicitly defined
        if f"{prefix}SERVER_NAME" not in self._config:
            config["SERVER_NAME"] = server

        return config

    def _render_global(self) -> None:
        """Render global templates."""
        self._write_config()
        templates = self._find_templates(["global", "http", "stream", "default-server-http"])
        with ThreadPoolExecutor(max_workers=min(32, len(templates))) as executor:
            executor.map(self._render_template, templates)

    def _render_server(self, server: str) -> None:
        """Render templates for a specific server.

        Args:
            server (str): Server name.
        """
        # Step 1: Find all relevant templates
        templates = self._find_templates(["modsec", "modsec-crs", "crs-plugins-before", "crs-plugins-after", "server-http", "server-stream"])

        # Step 2: Handle multisite configuration if applicable
        subpath = None
        config = None
        if self._config.get("MULTISITE", "no") == "yes":
            subpath = server
            config = self._get_server_config(server)
            self._write_config(subpath=subpath, config=config)

        # Step 3: Precompute 'name' for each template
        global_templates_set = set(self._global_templates)  # Faster lookups
        template_info = []
        for template in templates:
            # Check if the template ends with any of the global configurations
            name = basename(template) if any(template.endswith(root_conf) for root_conf in global_templates_set) else None
            template_info.append((template, name))

        # Separate templates into two groups
        priority_templates = [info for info in template_info if any(info[0].startswith(prefix) for prefix in ["modsec", "modsec-crs", "crs-plugins-before", "crs-plugins-after"])]
        other_templates = [info for info in template_info if info not in priority_templates]

        # Step 4: Define the rendering function
        def render_template(info):
            template, name = info
            self._render_template(template, subpath=subpath, config=config, name=name)

        # Step 5: Use ThreadPoolExecutor with optimized settings
        max_workers = min(32, len(template_info))  # Example: Limit to 32 or number of templates
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # First, render priority templates
            executor.map(render_template, priority_templates)
            # Then, render other templates
            executor.map(render_template, other_templates)

    def _render_template(
        self,
        template: str,
        subpath: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> None:
        """Render a single template.

        Args:
            template (str): Template name.
            subpath (Optional[str], optional): Subpath under the output directory. Defaults to None.
            config (Optional[Dict[str, Any]], optional): Configuration dictionary. Defaults to None.
            name (Optional[str], optional): Output file name. Defaults to None.
        """
        real_config = config.copy() if config else self._config.copy()
        real_config["all"] = real_config.copy()
        real_config.update(
            {
                "is_custom_conf": Templator.is_custom_conf,
                "has_variable": Templator.has_variable,
                "random": Templator.random,
                "read_lines": Templator.read_lines,
                # TODO: Remove 'import' to avoid security risks
                "import": import_module,
            }
        )
        real_path = Path(self._output, subpath or "", name or template)
        try:
            jinja_template = self._jinja_env.get_template(template)
            real_path.parent.mkdir(parents=True, exist_ok=True)
            with real_path.open("w") as f:
                f.write(jinja_template.render(real_config))
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
