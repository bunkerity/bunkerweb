#!/usr/bin/env python3

from argparse import ArgumentParser
from os import R_OK, X_OK, access, environ, getenv, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import get_integration, get_version  # type: ignore
from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from Configurator import Configurator
from API import API  # type: ignore

CUSTOM_CONF_RX = re_compile(
    r"^(?P<service>[0-9a-z\.-]*)_?CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(?P<name>.+)$"
)
BUNKERWEB_STATIC_INSTANCES_RX = re_compile(r"(http://)?(?P<hostname>(?<![:])\b[^:\s]+\b)(:(?P<port>\d+))?")

LOGGER = setup_logger("Generator.save_config", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))


if __name__ == "__main__":
    try:
        # Parse arguments
        parser = ArgumentParser(description="BunkerWeb config saver")
        parser.add_argument("--settings", default=join(sep, "usr", "share", "bunkerweb", "settings.json"), type=str, help="file containing the main settings")
        parser.add_argument("--core", default=join(sep, "usr", "share", "bunkerweb", "core"), type=str, help="directory containing the core plugins")
        parser.add_argument("--plugins", default=join(sep, "etc", "bunkerweb", "plugins"), type=str, help="directory containing the external plugins")
        parser.add_argument("--pro-plugins", default=join(sep, "etc", "bunkerweb", "pro", "plugins"), type=str, help="directory containing the pro plugins")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        parser.add_argument("--init", action="store_true", help="Only initialize the database")
        parser.add_argument("--method", default="scheduler", type=str, help="The method that is used to save the config")
        parser.add_argument("--no-check-changes", action="store_true", help="Set the changes to checked in the database")
        parser.add_argument("--first-run", action="store_true", help="Set the first run flag")
        args = parser.parse_args()

        settings_path = Path(args.settings)
        core_path = Path(args.core)
        plugins_path = Path(args.plugins)
        pro_plugins_path = Path(args.pro_plugins)

        LOGGER.info("Save config started ...")
        LOGGER.info(f"Settings : {settings_path}")
        LOGGER.info(f"Core : {core_path}")
        LOGGER.info(f"Plugins : {plugins_path}")
        LOGGER.info(f"Pro plugins : {pro_plugins_path}")
        LOGGER.info(f"Init : {args.init}")

        integration = get_integration()

        if args.init:
            LOGGER.info(f"Detected {integration} integration")

        external_plugins = args.plugins
        pro_plugins = args.pro_plugins

        dotenv_env = {}
        if args.variables:
            variables_path = Path(args.variables)
            LOGGER.info(f"Variables : {variables_path}")
            with variables_path.open() as f:
                dotenv_env = dict(line.strip().split("=", 1) for line in f if line.strip() and not line.startswith("#") and "=" in line)

        # Check existences and permissions
        LOGGER.info("Checking arguments ...")
        files = [settings_path] + ([variables_path] if args.variables else [])
        paths_rx = [core_path, plugins_path, pro_plugins_path]
        for file in files:
            if not file.is_file():
                LOGGER.error(f"Missing file : {file}")
                sys_exit(1)
            if not access(file, R_OK):
                LOGGER.error(f"Can't read file : {file}")
                sys_exit(1)
        for path in paths_rx:
            if not path.is_dir():
                LOGGER.error(f"Missing directory : {path}")
                sys_exit(1)
            if not access(path, R_OK | X_OK):
                LOGGER.error(f"Missing RX rights on directory : {path}")
                sys_exit(1)

        # Compute the config
        LOGGER.info("Computing config ...")
        config = Configurator(
            settings_path.as_posix(),
            core_path.as_posix(),
            external_plugins,
            pro_plugins,
            variables_path.as_posix() if args.variables else environ.copy(),
            LOGGER,
        )

        custom_confs = []
        for k, v in (environ | dotenv_env).items():
            if CUSTOM_CONF_RX.match(k):
                custom_conf = CUSTOM_CONF_RX.search(k)
                custom_confs.append(
                    {
                        "value": f"# CREATED BY ENV\n{v}",
                        "exploded": (
                            custom_conf.group("service"),
                            custom_conf.group("type"),
                            custom_conf.group("name").replace(".conf", ""),
                        ),
                    }
                )
                LOGGER.info(
                    f"Found custom conf env var {'for service ' + custom_conf.group('service') if custom_conf.group('service') else 'without service'} with type {custom_conf.group('type')} and name {custom_conf.group('name')}"
                )
                continue

        db = Database(LOGGER, sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None)))

        db_metadata = db.get_metadata()
        db_initialized = not isinstance(db_metadata, str) and db_metadata["is_initialized"]

        if not db_initialized:
            LOGGER.info("Database not initialized, initializing ...")
            ret, err = db.init_tables([config.get_settings(), config.get_plugins("core"), config.get_plugins("external"), config.get_plugins("pro")])

            # Initialize database tables
            if err:
                LOGGER.error(f"Exception while initializing database : {err}")
                sys_exit(1)
            elif not ret:
                LOGGER.info("Database tables are already initialized, skipping creation ...")
            else:
                LOGGER.info("Database tables initialized")
        else:
            LOGGER.info("Database is already initialized, checking for changes ...")

            ret, err = db.init_tables([config.get_settings(), config.get_plugins("core"), config.get_plugins("external"), config.get_plugins("pro")])

            if not ret and err:
                LOGGER.error(f"Exception while checking database tables : {err}")
                sys_exit(1)
            elif not ret:
                LOGGER.info("Database tables didn't change, skipping update ...")
            else:
                LOGGER.info("Database tables successfully updated")

        err = db.initialize_db(version=get_version(), integration=integration)

        if err:
            LOGGER.error(f"Can't {'initialize' if not db_initialized else 'update'} database metadata : {err}")
            sys_exit(1)
        else:
            LOGGER.info("Database metadata successfully " + ("initialized" if not db_initialized else "updated"))

        if args.init:
            sys_exit(0)

        settings = config.get_config(db, first_run=args.first_run)

        # Parse BunkerWeb instances from environment
        apis = []
        hostnames = set()
        for bw_instance in settings.get("BUNKERWEB_INSTANCES", "").split(" "):
            if not bw_instance:
                continue

            match = BUNKERWEB_STATIC_INSTANCES_RX.search(bw_instance)
            if match:
                if match.group("hostname") in hostnames:
                    LOGGER.warning(f"Duplicate BunkerWeb instance hostname {match.group('hostname')}, skipping it")

                hostnames.add(match.group("hostname"))
                apis.append(
                    API(
                        f"http://{match.group('hostname')}:{match.group('port') or settings.get('API_HTTP_PORT', '5000')}",
                        host=settings.get("API_SERVER_NAME", "bwapi"),
                    )
                )
            else:
                LOGGER.warning(
                    f"Invalid BunkerWeb instance {bw_instance}, it should match the following regex: (http://)<hostname>(:<port>) ({BUNKERWEB_STATIC_INSTANCES_RX.pattern}), skipping it"
                )

        changes = []
        changed_plugins = set()
        err = db.save_config(settings, args.method, changed=False)

        if isinstance(err, str):
            LOGGER.warning(f"Couldn't save config to database : {err}, config may not work as expected")
        else:
            changed_plugins = err
            changes.append("config")
            LOGGER.info("Config successfully saved to database")

        err1 = db.save_custom_configs(custom_confs, args.method, changed=False)

        if err1:
            LOGGER.warning(f"Couldn't save custom configs to database : {err1}, custom configs may not work as expected")
        else:
            changes.append("custom_configs")
            LOGGER.info("Custom configs successfully saved to database")

        err = db.update_instances([], method="manual", changed=False)
        if err:
            LOGGER.warning(f"Couldn't clear manual instances from database : {err}, instances may be incorrect")

        changes.append("instances")

        for api in apis:
            endpoint_data = api.endpoint.replace("http://", "").split(":")
            err = db.add_instance(endpoint_data[0], endpoint_data[1].replace("/", ""), api.host, method="manual", changed=False)

            if err:
                LOGGER.warning(err)
            else:
                LOGGER.info(f"Instance {endpoint_data[0]} successfully saved to database")

        if not args.no_check_changes:
            # update changes in db
            ret = db.checked_changes(changes, plugins_changes=changed_plugins, value=True)
            if ret:
                LOGGER.error(f"An error occurred when setting the changes to checked in the database : {ret}")
    except SystemExit as e:
        sys_exit(e.code)
    except:
        LOGGER.error(f"Exception while executing config saver : {format_exc()}")
        sys_exit(1)

    # We're done
    LOGGER.info("Config saver successfully executed !")
