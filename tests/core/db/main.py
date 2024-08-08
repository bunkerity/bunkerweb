from contextlib import contextmanager
from glob import iglob
from hashlib import sha256
from json import dumps, load
from os import environ, getenv
from os.path import dirname, join
from pathlib import Path
from re import compile as re_compile
from sqlalchemy import create_engine, text
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
from traceback import format_exc
from time import sleep

from bunkerweb.db.model import (
    Custom_configs,
    Global_values,
    Jobs,
    Jobs_runs,
    Metadata,
    Plugins,
    Plugin_pages,
    Services,
    Services_settings,
    Settings,
)

try:
    database_uri = getenv("DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3")

    if getenv("TEST_TYPE", "docker") == "docker" and database_uri == "sqlite:////var/lib/bunkerweb/db.sqlite3":
        database_uri = "sqlite:////data/lib/db.sqlite3"

    error = False

    print(f"ℹ️ Connecting to database: {database_uri}", flush=True)

    try:
        sql_engine = create_engine(database_uri, future=True)
    except ArgumentError:
        print(f"❌ Invalid database URI: {database_uri}", flush=True)
        error = True
    except SQLAlchemyError:
        print(f"❌ Error when trying to create the engine: {format_exc()}", flush=True)
        error = True
    finally:
        if error:
            exit(1)

    try:
        assert sql_engine is not None
    except AssertionError:
        print("❌ The database engine is not initialized", flush=True)
        exit(1)

    not_connected = True
    retries = 15

    while not_connected:
        try:
            with sql_engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS test (id INT)"))
                conn.execute(text("DROP TABLE test"))
            not_connected = False
        except (OperationalError, DatabaseError) as e:
            if retries <= 0:
                print(f"❌ Can't connect to database : {format_exc()}", flush=True)
                exit(1)

            if "attempt to write a readonly database" in str(e):
                print(
                    "⚠️ The database is read-only, waiting for it to become writable. Retrying in 5 seconds ...",
                    flush=True,
                )
                sql_engine.dispose(close=True)
                sql_engine = create_engine(
                    database_uri,
                    future=True,
                )
            if "Unknown table" in str(e):
                not_connected = False
                continue
            else:
                print(
                    "⚠️ Can't connect to database, retrying in 5 seconds ...",
                    flush=True,
                )
            retries -= 1
            sleep(5)
        except BaseException:
            print(
                f"❌ Error when trying to connect to the database: {format_exc()}",
                flush=True,
            )
            exit(1)

    print("ℹ️ Database connection established, launching tests ...", flush=True)

    session = sessionmaker()
    sql_session = scoped_session(session)
    sql_session.remove()
    sql_session.configure(bind=sql_engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def db_session():
        try:
            assert sql_session is not None
        except AssertionError:
            print("❌ The database session is not initialized", flush=True)
            exit(1)

        session = sql_session()
        session.expire_on_commit = False

        try:
            yield session
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    print("ℹ️ Checking if database is initialized ...", flush=True)

    with db_session() as session:
        metadata = session.query(Metadata).with_entities(Metadata.is_initialized).filter_by(id=1).first()

        if metadata is None or not metadata.is_initialized:
            print(
                "❌ The database is not initialized, it should be, exiting ...",
                flush=True,
            )
            exit(1)

    print("✅ Database is initialized", flush=True)
    print("   ", flush=True)
    print("ℹ️ Checking if service bwadm.example.com is in the database ...", flush=True)

    with db_session() as session:
        services = session.query(Services).all()

        if not services:
            print(
                "❌ The bw_services database table is empty, it shouldn't be, exiting ...",
                flush=True,
            )
            exit(1)

        if services[0].id != "bwadm.example.com":
            print(
                "❌ The service bwadm.example.com is not in the database, it should be, exiting ...",
                flush=True,
            )
            exit(1)

    print("✅ Service bwadm.example.com is in the database", flush=True)
    print("   ", flush=True)
    print(
        "ℹ️ Checking if global values are in the database and are correct ...",
        flush=True,
    )

    global_settings = {}
    service_settings = {}
    multisite = getenv("GLOBAL_MULTISITE", "no") == "yes"
    for env in environ:
        if env.startswith("GLOBAL_"):
            if env == "GLOBAL_MULTISITE" and environ[env] == "no":
                continue
            global_settings[env[7:]] = {"value": environ[env], "checked": False}
        elif env.startswith("SERVICE_"):
            service_settings[env[8:]] = {"value": environ[env], "checked": False}

    with db_session() as session:
        global_values = session.query(Global_values).all()

        for global_value in global_values:
            if global_value.setting_id == "API_LISTEN_IP":
                continue
            if global_value.setting_id in global_settings:
                if global_value.value != global_settings[global_value.setting_id]["value"]:
                    print(
                        f"❌ The global value {global_value.setting_id} is in the database but is not correct, exiting ...\n{global_value.value} (database) != {global_settings[global_value.setting_id]['value']} (env)",
                        flush=True,
                    )
                    exit(1)
                elif global_value.suffix != 0:
                    print(
                        f"❌ The global value {global_value.setting_id} is in the database but has the wrong suffix, exiting ...\n{global_value.suffix} (database) != 0 (env)",
                        flush=True,
                    )
                    exit(1)
                elif global_value.method != "scheduler":
                    print(
                        f"❌ The global value {global_value.setting_id} is in the database but has the wrong method, exiting ...\n{global_value.method} (database) != scheduler (env)",
                        flush=True,
                    )
                    exit(1)

                global_settings[global_value.setting_id]["checked"] = True
            else:
                print(
                    f"❌ The global value {global_value.setting_id} is in the database but should not be, exiting ...",
                    flush=True,
                )
                exit(1)

    if not all([global_settings[global_value]["checked"] for global_value in global_settings]):
        print(
            f"❌ Not all global values are in the database, exiting ...\nmissing values: {', '.join([global_value for global_value in global_settings if not global_settings[global_value]['checked']])}",
            flush=True,
        )
        exit(1)

    print("✅ Global values are in the database and are correct", flush=True)
    print("   ", flush=True)
    print(
        "ℹ️ Checking if service values are in the database and are correct ...",
        flush=True,
    )

    with db_session() as session:
        services_settings = session.query(Services_settings).all()

        if not multisite and service_settings:
            print(
                '❌ The bw_services_settings database table is not empty, it should be when multisite is set to "no", exiting ...',
                flush=True,
            )
            exit(1)
        else:
            for service_setting in services_settings:
                if service_setting.setting_id in service_settings:
                    if service_setting.value != service_settings[service_setting.setting_id]["value"]:
                        print(
                            f"❌ The service value {service_setting.setting_id} is in the database but is not correct, exiting ...\n{service_setting.value} (database) != {service_settings[service_setting.setting_id]['value']} (env)",
                            flush=True,
                        )
                        exit(1)
                    elif service_setting.suffix != 0:
                        print(
                            f"❌ The service value {service_setting.setting_id} is in the database but has the wrong suffix, exiting ...\n{service_setting.suffix} (database) != 0 (env)",
                            flush=True,
                        )
                        exit(1)
                    elif service_setting.method != "scheduler":
                        print(
                            f"❌ The service value {service_setting.setting_id} is in the database but has the wrong method, exiting ...\n{service_setting.method} (database) != scheduler (env)",
                            flush=True,
                        )
                        exit(1)

                    service_settings[service_setting.setting_id]["checked"] = True
                else:
                    print(
                        f"❌ The service value {service_setting.setting_id} is in the database but should not be, exiting ...",
                        flush=True,
                    )
                    exit(1)

    if not all([service_settings[service_setting]["checked"] for service_setting in service_settings]):
        print(
            f"❌ Not all service values are in the database, exiting ...\nmissing values: {', '.join([service_setting for service_setting in service_settings if not service_settings[service_setting]['checked']])}",
            flush=True,
        )
        exit(1)

    print("✅ Service values are correct", flush=True)
    print("   ", flush=True)
    print("ℹ️ Checking if the plugins are correct ...", flush=True)

    with open(join("bunkerweb", "settings.json"), "r") as f:
        global_settings = load(f)

    core_plugins = {
        "general": {
            "name": "General",
            "description": "The general settings for the server",
            "version": "0.1",
            "stream": "partial",
            "type": "core",
            "checked": False,
            "page_checked": True,
            "settings": global_settings,
        },
    }
    for filename in iglob(join("bunkerweb", "core", "*", "plugin.json")):
        with open(filename, "r") as f:
            data = load(f)
            data["checked"] = False
            for x, job in enumerate(data.get("jobs", [])):
                data["jobs"][x]["checked"] = False
            data["page_checked"] = not Path(f"{dirname(filename)}/ui").exists() or False
            core_plugins[data.pop("id")] = data

    external_plugins = {}
    for filename in iglob(join("external", "*", "plugin.json")):
        with open(filename, "r") as f:
            data = load(f)
            data["checked"] = False
            for x, job in enumerate(data.get("jobs", [])):
                data["jobs"][x]["checked"] = False
            data["page_checked"] = not Path(f"{dirname(filename)}/ui").exists() or False
            external_plugins[data.pop("id")] = data

    with db_session() as session:
        plugins = (
            session.query(Plugins)
            .with_entities(
                Plugins.id,
                Plugins.name,
                Plugins.description,
                Plugins.version,
                Plugins.stream,
                Plugins.type,
                Plugins.method,
            )
            .all()
        )

        for plugin in plugins:
            if plugin.type == "pro":  # ? We do not test the pro plugins in here
                continue

            if plugin.type == "core" and plugin.id in core_plugins:
                current_plugin = core_plugins
            elif plugin.type == "external" and plugin.id in external_plugins:
                current_plugin = external_plugins
            else:
                print(
                    f"❌ The {'external' if plugin.type == 'external' else 'core'} plugin {plugin.name} (id: {plugin.id}) is in the database but should not be, exiting ...: {plugin}",
                    flush=True,
                )
                exit(1)

            if (
                plugin.name != current_plugin[plugin.id]["name"]
                or plugin.description != current_plugin[plugin.id]["description"]
                or plugin.version != current_plugin[plugin.id]["version"]
                or plugin.stream != current_plugin[plugin.id]["stream"]
            ):
                print(
                    f"❌ The {'external' if plugin.type == 'external' else 'core'} plugin {plugin.name} (id: {plugin.id}) is in the database but is not correct, exiting ...\n"
                    + f"{dumps({'name': plugin.name, 'description': plugin.description, 'version': plugin.version, 'stream': plugin.stream})}"
                    + f" (database) != {dumps({'name': current_plugin[plugin.id]['name'], 'description': current_plugin[plugin.id]['description'], 'version': current_plugin[plugin.id]['version'], 'stream': current_plugin[plugin.id]['stream']})} (file)",  # noqa: E501
                    flush=True,
                )
                exit(1)
            else:
                settings = session.query(Settings).filter_by(plugin_id=plugin.id).all()

                for setting in settings:
                    if (
                        setting.name != current_plugin[plugin.id]["settings"][setting.id]["id"]
                        or setting.context != current_plugin[plugin.id]["settings"][setting.id]["context"]
                        or setting.default != current_plugin[plugin.id]["settings"][setting.id]["default"]
                        or setting.help != current_plugin[plugin.id]["settings"][setting.id]["help"]
                        or setting.label != current_plugin[plugin.id]["settings"][setting.id]["label"]
                        or setting.regex != current_plugin[plugin.id]["settings"][setting.id]["regex"]
                        or setting.type != current_plugin[plugin.id]["settings"][setting.id]["type"]
                        or setting.multiple != current_plugin[plugin.id]["settings"][setting.id].get("multiple", None)
                    ):
                        print(
                            f"❌ The {'external' if plugin.type == 'external' else 'core'} plugin {plugin.name} (id: {plugin.id}) is in the database but is not correct, exiting ...\n"
                            + f"{dumps({'default': setting.default, 'help': setting.help, 'label': setting.label, 'regex': setting.regex, 'type': setting.type})}"
                            + f" (database) != {dumps({'default': current_plugin[plugin.id]['settings'][setting.id]['default'], 'help': current_plugin[plugin.id]['settings'][setting.id]['help'], 'label': current_plugin[plugin.id]['settings'][setting.id]['label'], 'regex': current_plugin[plugin.id]['settings'][setting.id]['regex'], 'type': current_plugin[plugin.id]['settings'][setting.id]['type']})} (file)",  # noqa: E501
                            flush=True,
                        )
                        exit(1)

                current_plugin[plugin.id]["checked"] = True

    if not all([core_plugins[plugin]["checked"] for plugin in core_plugins]):
        print(
            f"❌ Not all core plugins are in the database, exiting ...\nmissing plugins: {', '.join([plugin for plugin in core_plugins if not core_plugins[plugin]['checked']])}",
            flush=True,
        )
        exit(1)
    elif not all([external_plugins[plugin]["checked"] for plugin in external_plugins]):
        print(
            f"❌ Not all external plugins are in the database, exiting ...\nmissing plugins: {', '.join([plugin for plugin in external_plugins if not external_plugins[plugin]['checked']])}",
            flush=True,
        )
        exit(1)

    print("✅ The ClamAV plugin and all core plugins are in the database", flush=True)
    print("   ", flush=True)
    print("ℹ️ Checking if the jobs are in the database ...", flush=True)

    with db_session() as session:
        jobs = session.query(Jobs).all()
        pro_plugin_ids = [plugin.id for plugin in session.query(Plugins).with_entities(Plugins.id).filter_by(type="pro").all()]

        for job in jobs:
            if job.plugin_id in pro_plugin_ids:
                continue

            if job.name != "download-pro-plugins" and not all(job_run.success for job_run in session.query(Jobs_runs).filter_by(job_name=job.name)):
                print(
                    f"❌ The job {job.name} (plugin_id: {job.plugin_id}) is in the database but failed, exiting ...",
                    flush=True,
                )
                exit(1)

            if job.plugin_id in core_plugins:
                current_plugin = core_plugins
            elif job.plugin_id in external_plugins:
                current_plugin = external_plugins
            else:
                print(
                    f"❌ The job {job.name} (plugin_id: {job.plugin_id}) is in the database but should not be, exiting ...",
                    flush=True,
                )
                exit(1)

            index = next(index for (index, d) in enumerate(current_plugin[job.plugin_id].get("jobs", [])) if d["name"] == job.name)
            core_job = current_plugin[job.plugin_id]["jobs"][index]

            if job.name != core_job["name"] or job.file_name != core_job["file"] or job.every != core_job["every"] or job.reload != core_job["reload"]:
                print(
                    f"❌ The job {job.name} (plugin_id: {job.plugin_id}) is in the database but is not correct, exiting ...\n"
                    + f"{dumps({'name': job.name, 'file': job.file_name, 'every': job.every, 'reload': job.reload})} (database) != {dumps({'name': core_job['name'], 'file': core_job['file'], 'every': core_job['every'], 'reload': core_job['reload']})} (file)",  # noqa: E501
                    flush=True,
                )
                exit(1)

            current_plugin[job.plugin_id]["jobs"][index]["checked"] = True

    if not all([all([job["checked"] for job in core_plugins[plugin].get("jobs", [])]) for plugin in core_plugins]):
        print(
            f"❌ Not all jobs from core plugins are in the database, exiting ...\nmissing jobs: {dumps({plugin: [job['name'] for job in core_plugins[plugin]['jobs'] if not job['checked']] for plugin in core_plugins})}",
            flush=True,
        )
        exit(1)
    elif not all([all([job["checked"] for job in external_plugins[plugin].get("jobs", [])]) for plugin in external_plugins]):
        print(
            f"❌ Not all jobs from external plugins are in the database, exiting ...\nmissing jobs: {dumps({plugin: [job['name'] for job in external_plugins[plugin]['jobs'] if not job['checked']] for plugin in external_plugins})}",
            flush=True,
        )
        exit(1)

    print("✅ All jobs are in the database and have successfully ran", flush=True)
    print(" ", flush=True)
    print("ℹ️ Checking if all plugin pages are in the database ...", flush=True)

    def file_hash(file: str) -> str:
        _sha256 = sha256()
        with open(file, "rb") as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                _sha256.update(data)
        return _sha256.hexdigest()

    with db_session() as session:
        plugin_pages = (
            session.query(Plugin_pages)
            .with_entities(
                Plugin_pages.id,
                Plugin_pages.plugin_id,
                Plugin_pages.checksum,
            )
            .all()
        )

        for plugin_page in plugin_pages:
            if plugin_page.plugin_id in core_plugins:
                current_plugin = core_plugins
            elif plugin_page.plugin_id in external_plugins:
                current_plugin = external_plugins
            else:
                print(
                    f"❌ The plugin page from {plugin_page.plugin_id} is in the database but should not be, exiting ...",
                    flush=True,
                )
                exit(1)

            path_ui = (
                Path(join("bunkerweb", "core", plugin_page.plugin_id, "ui"))
                if Path(join("bunkerweb", "core", plugin_page.plugin_id, "ui")).exists()
                else Path(join("external", plugin_page.plugin_id, "ui"))
            )

            if not path_ui.exists():
                print(
                    f'❌ The plugin page from {plugin_page.plugin_id} is in the database but should not be because the "ui" folder is missing from the plugin, exiting ...',
                    flush=True,
                )
                exit(1)

            current_plugin[plugin_page.plugin_id]["page_checked"] = True

    if not all([core_plugins[plugin]["page_checked"] for plugin in core_plugins]):
        print(
            f"❌ Not all core plugins pages are in the database, exiting ...\nmissing plugins pages: {', '.join([plugin for plugin in core_plugins if not core_plugins[plugin]['page_checked']])}",
            flush=True,
        )
        exit(1)
    elif not all([external_plugins[plugin]["page_checked"] for plugin in external_plugins]):
        print(
            f"❌ Not all external plugins pages are in the database, exiting ...\nmissing plugins pages: {', '.join([plugin for plugin in external_plugins if not external_plugins[plugin]['page_checked']])}",
            flush=True,
        )
        exit(1)

    print("✅ All plugin pages are in the database and have the right value", flush=True)
    print(" ", flush=True)
    print("ℹ️ Checking if all custom configs are in the database ...", flush=True)

    custom_confs_rx = re_compile(r"^([0-9a-z\.-]*)_?CUSTOM_CONF_(SERVICE_)?(HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$")

    global_custom_configs = {}
    service_custom_configs = {}
    for env in environ:
        if not custom_confs_rx.match(env):
            continue

        custom_conf = custom_confs_rx.search(env).groups()
        if custom_conf[1]:
            service_custom_configs[custom_conf[3]] = {
                "value": environ[env].encode(),
                "type": custom_conf[2].lower(),
                "method": "manual" if getenv("TEST_TYPE", "docker") == "linux" else "scheduler",
                "checked": False,
            }
            continue

        global_custom_configs[custom_conf[3]] = {
            "value": environ[env].encode(),
            "type": custom_conf[2].lower(),
            "method": "manual" if getenv("TEST_TYPE", "docker") == "linux" else "scheduler",
            "checked": False,
        }

    with db_session() as session:
        custom_configs = (
            session.query(Custom_configs)
            .with_entities(
                Custom_configs.service_id,
                Custom_configs.type,
                Custom_configs.name,
                Custom_configs.data,
                Custom_configs.method,
            )
            .all()
        )

        for custom_config in custom_configs:
            if custom_config.name == "ready":
                continue
            if not multisite and custom_config.name in global_custom_configs and custom_config.service_id:
                print(
                    f"❌ The custom config {custom_config.name} is in the database but should not be owned by the service {custom_config.service_id} because multisite is not enabled, exiting ...",
                    flush=True,
                )
                exit(1)
            elif multisite and custom_config.name in service_custom_configs and not custom_config.service_id:
                print(
                    f"❌ The custom config {custom_config.name} is in the database but should be owned by the service bwadm.example.com because it's a service config, exiting ...",
                    flush=True,
                )
                exit(1)

            if custom_config.name in global_custom_configs:
                current_custom_configs = global_custom_configs
            elif custom_config.name in service_custom_configs:
                current_custom_configs = service_custom_configs
            else:
                print(
                    f"❌ The custom config {custom_config.name} is in the database but should not be, exiting ...",
                    flush=True,
                )
                exit(1)

            if custom_config.type != current_custom_configs[custom_config.name]["type"]:
                print(
                    f"❌ The custom config {custom_config.name} is in the database but the type differ, exiting ...\n{custom_config.type} (database) != {current_custom_configs[custom_config.name]['type']} (env)",
                    flush=True,
                )
                exit(1)
            elif (
                custom_config.data.replace(b"# CREATED BY ENV\n", b"") != current_custom_configs[custom_config.name]["value"]
                and custom_config.data.replace(b"# CREATED BY ENV\n", b"") != current_custom_configs[custom_config.name]["value"] + b"\n"
            ):
                print(
                    f"❌ The custom config {custom_config.name} is in the database but the value differ, exiting ...\n{custom_config.data} (database) != {current_custom_configs[custom_config.name]['value']} (env)",
                    flush=True,
                )
                exit(1)
            elif custom_config.method != current_custom_configs[custom_config.name]["method"]:
                print(
                    f"❌ The custom config {custom_config.name} is in the database but the method differ, exiting ...\n{custom_config.method} (database) != {current_custom_configs[custom_config.name]['method']} (env)",
                    flush=True,
                )
                exit(1)

            current_custom_configs[custom_config.name]["checked"] = True

    if not all([global_custom_configs[custom_config]["checked"] for custom_config in global_custom_configs]):
        print(
            f"❌ Not all global custom configs are in the database, exiting ...\nmissing custom configs: {', '.join([custom_config for custom_config in global_custom_configs if not global_custom_configs[custom_config]['checked']])}",
            flush=True,
        )
        exit(1)
    elif not all([service_custom_configs[custom_config]["checked"] for custom_config in service_custom_configs]):
        print(
            f"❌ Not all service custom configs are in the database, exiting ...\nmissing custom configs: {', '.join([custom_config for custom_config in service_custom_configs if not service_custom_configs[custom_config]['checked']])}",
            flush=True,
        )
        exit(1)

    print("✅ All custom configs are in the database and have the right value", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
