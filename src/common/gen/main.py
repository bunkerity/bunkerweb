#!/usr/bin/env python3

from argparse import ArgumentParser
from glob import glob
from os import R_OK, W_OK, X_OK, access, getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Any, Dict

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import get_integration  # type: ignore
from logger import setup_logger  # type: ignore
from Configurator import Configurator
from Templator import Templator


if __name__ == "__main__":
    logger = setup_logger("Generator", getenv("LOG_LEVEL", "INFO"))
    wait_retry_interval = int(getenv("WAIT_RETRY_INTERVAL", "5"))

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

        logger.info("Generator started ...")
        logger.info(f"Settings : {settings_path}")
        logger.info(f"Templates : {templates_path}")
        logger.info(f"Core : {core_path}")
        logger.info(f"Plugins : {plugins_path}")
        logger.info(f"Pro plugins : {pro_plugins_path}")
        logger.info(f"Output : {output_path}")
        logger.info(f"Target : {target_path}")

        integration = get_integration()

        if args.variables:
            variables_path = Path(args.variables)
            variables_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Variables : {variables_path}")

            # Check existences and permissions
            logger.info("Checking arguments ...")
            files = [settings_path, variables_path]
            paths_rx = [core_path, plugins_path, pro_plugins_path, templates_path]
            paths_rwx = [output_path]
            for file in files:
                if not file.is_file():
                    logger.error(f"Missing file : {file}")
                    sys_exit(1)
                elif not access(file, R_OK):
                    logger.error(f"Can't read file : {file}")
                    sys_exit(1)
            for path in paths_rx + paths_rwx:
                if not path.is_dir():
                    logger.error(f"Missing directory : {path}")
                    sys_exit(1)
                elif not access(path, R_OK | X_OK):
                    logger.error(
                        f"Missing RX rights on directory : {path}",
                    )
                    sys_exit(1)
            for path in paths_rwx:
                if not access(path, W_OK):
                    logger.error(
                        f"Missing W rights on directory : {path}",
                    )
                    sys_exit(1)

            # Compute the config
            logger.info("Computing config ...")
            config: Dict[str, Any] = Configurator(
                str(settings_path), str(core_path), str(plugins_path), str(pro_plugins_path), str(variables_path), logger
            ).get_config()
        else:
            if join(sep, "usr", "share", "bunkerweb", "db") not in sys_path:
                sys_path.append(join(sep, "usr", "share", "bunkerweb", "db"))

            from Database import Database  # type: ignore

            db = Database(
                logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
            )
            config: Dict[str, Any] = db.get_config()

        # Remove old files
        logger.info("Removing old files ...")
        files = glob(join(args.output, "*"))
        for file in files:
            file = Path(file)
            if file.is_symlink() or file.is_file():
                file.unlink()
            elif file.is_dir():
                rmtree(str(file), ignore_errors=True)

        # Render the templates
        logger.info("Rendering templates ...")
        templator = Templator(str(templates_path), str(core_path), str(plugins_path), str(pro_plugins_path), str(output_path), str(target_path), config)
        templator.render()

        if integration not in ("Autoconf", "Swarm", "Kubernetes", "Docker") and not args.no_linux_reload:
            retries = 0
            while not Path(sep, "var", "run", "bunkerweb", "nginx.pid").exists():
                if retries == 5:
                    logger.error(
                        "BunkerWeb's nginx didn't start in time.",
                    )
                    sys_exit(1)

                logger.warning(
                    "Waiting for BunkerWeb's nginx to start, retrying in 5 seconds ...",
                )
                retries += 1
                sleep(5)

            proc = run(
                [join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                stdin=DEVNULL,
                stderr=STDOUT,
            )
            if proc.returncode != 0:
                status = 1
                logger.error("Error while reloading nginx")
            else:
                logger.info("Successfully reloaded nginx")

    except SystemExit as e:
        raise e
    except:
        logger.error(
            f"Exception while executing generator : {format_exc()}",
        )
        sys_exit(1)

    # We're done
    logger.info("Generator successfully executed !")
