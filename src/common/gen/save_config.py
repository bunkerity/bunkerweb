#!/usr/bin/env python3

from argparse import ArgumentParser
from os import R_OK, X_OK, access, environ, getenv, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile
from urllib.parse import urlsplit
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import get_integration, get_version  # type: ignore
from env_file import parse_env_file  # type: ignore
from logger import getLogger  # type: ignore
from Database import Database  # type: ignore
from Configurator import Configurator
from API import API  # type: ignore

# `\Z`, not `$`: `$` also matches immediately before a trailing newline, so an environment key
# `CUSTOM_CONF_HTTP_x\n` matches here. `.` never matches a newline, so `name` is captured as `x`
# either way -- what `$` buys is that the dirty key matches *at all* and then produces the same
# custom config as the clean one, silently aliasing two environment variables onto one file.
# The twin of this pattern lives in `src/ui/app/routes/utils.py`; the two have already drifted once.
CUSTOM_CONF_RX = re_compile(
    r"^(?P<service>[0-9a-z\.-]*)_?CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(?P<name>.+)\Z"
)
LOGGER = getLogger("GENERATOR.SAVE_CONFIG")


if __name__ == "__main__":
    config_saved = False

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
            dotenv_env = parse_env_file(variables_path)

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
        for k, v in environ.items():
            if CUSTOM_CONF_RX.match(k):
                custom_conf = CUSTOM_CONF_RX.search(k)
                if not custom_conf:
                    continue
                custom_confs.append(
                    {
                        "value": f"# CREATED BY ENV\n{v}",
                        "exploded": (
                            custom_conf.group("service"),
                            custom_conf.group("type"),
                            custom_conf.group("name").replace(".conf", ""),
                        ),
                        "is_draft": False,
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

        # Parse BunkerWeb instances: the flat BUNKERWEB_INSTANCES list (all inherit the global
        # API config) plus grouped per-instance BUNKERWEB_INSTANCE_* settings (numeric suffix,
        # no suffix = group 0) that can override listen_https / ports / server_name / api_token / tls.
        instance_defs = []
        hostnames = set()

        def _register_instance(
            raw_host, *, listen_https=None, port=None, https_port=None, server_name=None, credential=None, tls_mode=None, tls_fingerprint=None
        ):
            eff_listen_https = (settings.get("API_LISTEN_HTTPS", "no") or "no").lower() == "yes" if listen_https is None else listen_https
            eff_port = port or settings.get("API_HTTP_PORT")
            eff_https_port = https_port or settings.get("API_HTTPS_PORT")
            try:
                endpoint = API.build_endpoint(raw_host, port=eff_port, listen_https=eff_listen_https, https_port=eff_https_port)
            except ValueError as e:
                LOGGER.warning(f"Invalid BunkerWeb instance {raw_host}: {e}, skipping it")
                return
            parsed = urlsplit(endpoint)
            hostname = parsed.hostname or "127.0.0.1"
            if hostname in hostnames:
                LOGGER.warning(f"Duplicate BunkerWeb instance hostname {hostname}, skipping it")
                return
            hostnames.add(hostname)
            is_https = parsed.scheme == "https"
            http_port_default = settings.get("API_HTTP_PORT", getenv("API_HTTP_PORT", "5000"))
            https_port_default = settings.get("API_HTTPS_PORT", getenv("API_HTTPS_PORT", "5443"))
            if is_https:
                http_port_val = int(eff_port or http_port_default)
                https_port_val = int(parsed.port or eff_https_port or https_port_default)
            else:
                http_port_val = int(parsed.port or eff_port or http_port_default)
                https_port_val = int(eff_https_port or https_port_default)
            instance_defs.append(
                {
                    "hostname": hostname,
                    "port": http_port_val,
                    "https_port": https_port_val,
                    "listen_https": is_https,
                    "server_name": server_name or settings.get("API_SERVER_NAME", "bwapi"),
                    "credential": credential or None,
                    "tls_mode": (tls_mode or "").strip().lower() or None,
                    "tls_fingerprint": (tls_fingerprint or "").strip() or None,
                }
            )

        # Grouped per-instance declarations first (their richer config wins on hostname dedup).
        _instance_host_rx = re_compile(r"^BUNKERWEB_INSTANCE_HOST(?:_(?P<idx>\d+))?$")
        _group_suffixes = sorted({(m.group("idx") or "0") for key in environ for m in (_instance_host_rx.match(key),) if m}, key=int)
        for _idx in _group_suffixes:
            _suffix = "" if _idx == "0" else f"_{_idx}"
            _raw_host = environ.get(f"BUNKERWEB_INSTANCE_HOST{_suffix}", "").strip()
            if not _raw_host:
                continue
            _listen_https_env = environ.get(f"BUNKERWEB_INSTANCE_LISTEN_HTTPS{_suffix}")
            _register_instance(
                _raw_host,
                listen_https=(_listen_https_env.strip().lower() == "yes") if _listen_https_env is not None else None,
                port=environ.get(f"BUNKERWEB_INSTANCE_PORT{_suffix}"),
                https_port=environ.get(f"BUNKERWEB_INSTANCE_HTTPS_PORT{_suffix}"),
                server_name=environ.get(f"BUNKERWEB_INSTANCE_SERVER_NAME{_suffix}"),
                credential=environ.get(f"BUNKERWEB_INSTANCE_API_TOKEN{_suffix}"),
                tls_mode=environ.get(f"BUNKERWEB_INSTANCE_TLS_MODE{_suffix}"),
                tls_fingerprint=environ.get(f"BUNKERWEB_INSTANCE_TLS_FINGERPRINT{_suffix}"),
            )

        # Flat BUNKERWEB_INSTANCES list (all inherit the global API config).
        for bw_instance in settings.get("BUNKERWEB_INSTANCES", "").split():
            _register_instance(bw_instance)

        changes = []
        changed_plugins = set()
        err = db.save_config(settings, args.method, changed=False, explicit_keys=config.explicit_keys)

        if isinstance(err, str):
            LOGGER.error(f"Couldn't save config to database : {err}, config may not work as expected")
        else:
            config_saved = True
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

        for inst in instance_defs:
            err = db.add_instance(
                inst["hostname"],
                inst["port"],
                inst["server_name"],
                method="manual",
                changed=False,
                listen_https=inst["listen_https"],
                https_port=inst["https_port"],
                credential=inst["credential"],
                tls_mode=inst["tls_mode"],
                tls_fingerprint=inst["tls_fingerprint"],
            )

            if err:
                LOGGER.warning(err)
            else:
                LOGGER.info(f"Instance {inst['hostname']} successfully saved to database")

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

    # A failed save leaves the caller running on defaults for every setting it sent. Exiting 0 here
    # made that indistinguishable from success: the scheduler's returncode check never fired and the
    # log ended on "successfully executed".
    if not config_saved:
        sys_exit(1)

    # We're done
    LOGGER.info("Config saver successfully executed !")
