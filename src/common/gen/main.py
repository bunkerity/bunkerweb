#!/usr/bin/env python3

from argparse import ArgumentParser
from glob import glob
from os import R_OK, W_OK, X_OK, access, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from Configurator import Configurator
from Templator import Templator

DB_PATH = Path(sep, "usr", "share", "bunkerweb", "db")

LOGGER = setup_logger("Generator", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

if __name__ == "__main__":
    try:
        # Parse arguments
        parser = ArgumentParser(description="BunkerWeb config generator")
        parser.add_argument("--settings", default=join(sep, "usr", "share", "bunkerweb", "settings.json"), type=str, help="file containing the main settings")
        parser.add_argument(
            "--templates", default=join(sep, "usr", "share", "bunkerweb", "confs"), type=str, help="directory containing the main template files"
        )
        parser.add_argument("--core", default=join(sep, "usr", "share", "bunkerweb", "core"), type=str, help="directory containing the core plugins")
        parser.add_argument("--plugins", default=join(sep, "etc", "bunkerweb", "plugins"), type=str, help="directory containing the external plugins")
        parser.add_argument("--pro-plugins", default=join(sep, "etc", "bunkerweb", "pro", "plugins"), type=str, help="directory containing the pro plugins")
        parser.add_argument("--output", default=join(sep, "etc", "nginx"), type=str, help="where to write the rendered files")
        parser.add_argument("--target", default=join(sep, "etc", "nginx"), type=str, help="where nginx will search for configurations files")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        settings_path = Path(args.settings)
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        templates_path = Path(args.templates)
        templates_path.mkdir(parents=True, exist_ok=True)

        core_path = Path(args.core)
        core_path.mkdir(parents=True, exist_ok=True)

        plugins_path = Path(args.plugins)
        plugins_path.mkdir(parents=True, exist_ok=True)

        pro_plugins_path = Path(args.pro_plugins)
        pro_plugins_path.mkdir(parents=True, exist_ok=True)

        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)

        target_path = Path(args.target)
        target_path.mkdir(parents=True, exist_ok=True)

        LOGGER.info("Generator started ...")
        LOGGER.info(f"Settings : {settings_path}")
        LOGGER.info(f"Templates : {templates_path}")
        LOGGER.info(f"Core : {core_path}")
        LOGGER.info(f"Plugins : {plugins_path}")
        LOGGER.info(f"Pro plugins : {pro_plugins_path}")
        LOGGER.info(f"Output : {output_path}")
        LOGGER.info(f"Target : {target_path}")

        dotenv_env = {}
        if args.variables:
            variables_path = Path(args.variables)
            LOGGER.info(f"Variables : {variables_path}")
            with variables_path.open() as f:
                dotenv_env = dict(line.strip().split("=", 1) for line in f if line.strip() and not line.startswith("#") and "=" in line)

        db = None
        if DB_PATH.is_dir():
            if DB_PATH.as_posix() not in sys_path:
                sys_path.append(DB_PATH.as_posix())

            from Database import Database  # type: ignore

            db = Database(LOGGER, sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None)))

        if args.variables:
            # Check existences and permissions
            LOGGER.info("Checking arguments ...")
            files = [settings_path, variables_path]
            paths_rx = [core_path, plugins_path, pro_plugins_path, templates_path]
            paths_rwx = [output_path]
            for file in files:
                if not file.is_file():
                    LOGGER.error(f"Missing file : {file}")
                    sys_exit(1)
                elif not access(file, R_OK):
                    LOGGER.error(f"Can't read file : {file}")
                    sys_exit(1)
            for path in paths_rx + paths_rwx:
                if not path.is_dir():
                    LOGGER.error(f"Missing directory : {path}")
                    sys_exit(1)
                elif not access(path, R_OK | X_OK):
                    LOGGER.error(f"Missing RX rights on directory : {path}")
                    sys_exit(1)
            for path in paths_rwx:
                if not access(path, W_OK):
                    LOGGER.error(f"Missing W rights on directory : {path}")
                    sys_exit(1)

            # Compute the config
            LOGGER.info("Computing config ...")
            config: Dict[str, Any] = Configurator(
                settings_path.as_posix(),
                core_path.as_posix(),
                plugins_path.as_posix(),
                pro_plugins_path.as_posix(),
                variables_path.as_posix(),
                LOGGER,
            ).get_config(db)
            full_config = config.copy()
            default_config = config.copy()
        else:
            config: Dict[str, Any] = db.get_non_default_settings() | {"DATABASE_URI": db.database_uri}
            full_config = db.get_config(methods=True) | {"DATABASE_URI": {"default": "sqlite:////var/lib/bunkerweb/db.sqlite3", "value": db.database_uri}}
            default_config = {setting: data["default"] for setting, data in full_config.items()}
            full_config = {setting: data["value"] for setting, data in full_config.items()}

        # Remove old files
        LOGGER.info("Removing old files ...")
        files = glob(join(args.output, "*"))
        for file in files:
            file = Path(file)
            if file.is_symlink() or file.is_file():
                file.unlink()
            elif file.is_dir():
                rmtree(file.as_posix(), ignore_errors=True)

        # Render the templates
        LOGGER.info("Rendering templates ...")
        templator = Templator(
            templates_path.as_posix(),
            core_path.as_posix(),
            plugins_path.as_posix(),
            pro_plugins_path.as_posix(),
            output_path.as_posix(),
            target_path.as_posix(),
            config,
            default_config,
            full_config,
        )
        templator.render()
    except SystemExit as e:
        raise e
    except:
        LOGGER.error(f"Exception while executing generator : {format_exc()}")
        sys_exit(1)

    # We're done
    LOGGER.info("Generator successfully executed !")
