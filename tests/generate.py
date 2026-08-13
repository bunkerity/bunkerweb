#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from base64 import b64encode
from logging import getLogger
from os import getenv, sep
from os.path import join
from pathlib import Path

from redis import Redis
from tzlocal import get_localzone
from yaml import safe_dump, safe_load

from utils import resolve_env_placeholders
import utils.logger  # noqa: F401
from utils.action import parse_action
from utils.example import clear as example_clear, materialise as example_materialise

LOGGER = getLogger("GENERATE")

# Admin bearer token shared by the stack's scheduler, worker and API. Test-only: the
# API accepts it as an admin override (src/api/app/auth/guard.py), which keeps the
# stack from needing a Biscuit exchange before the first job can be dispatched.
API_TEST_TOKEN = "tests-secret-token"  # noqa: S105

# Root the generated env files live under. Overridable so a local run writes to a
# scratch directory instead of the host's real /etc/bunkerweb — the compose fragments
# read the same variable (${BW_TESTS_ETC:-/etc/bunkerweb}).
BW_ETC = Path(getenv("BW_TESTS_ETC", join(sep, "etc", "bunkerweb")))

parser = ArgumentParser(prog="Tests generator", description="Generate all the files needed to run a test.")
integration_action = parser.add_argument(
    "integration", type=str, help="Integration to test", choices=["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"]
)
parser.add_argument("type", type=str, help="Type of test to parse", choices=["core", "ui", "api"])
parser.add_argument("test", type=str, help="Test to generate the files for")
parser.add_argument("--dev", action="store_true", help="Run in development mode")
ARGS = parser.parse_args()

integrations = safe_load(Path("tests", "utils", "integrations.yml").read_text())["dev" if ARGS.dev else "staging"]

test_split = ARGS.test.split(";")
filename = test_split[0]
action_str = test_split[1]

LOGGER.info(f"🛠 Running {filename} / {action_str} generation for integration {ARGS.integration}")

if ARGS.integration.replace("-", "_") not in integrations:
    LOGGER.error(f"Integration {ARGS.integration} not found in integrations.yml")
    exit(1)

redis_client = Redis(host="localhost", port=6379, db=0)

resp = redis_client.ping()
if not resp:
    LOGGER.error("Redis server is not running")
    exit(1)

file_path = join("tests", ARGS.type, f"{filename}.yml")

LOGGER.info(f"📖 Reading {file_path}")

LOGGER.debug(f"Trying to open {file_path}")

content = Path(file_path).read_text()

# Replace ${VAR} patterns with the corresponding environment variable
content = resolve_env_placeholders(content)

data = safe_load(content)

LOGGER.info("📖 Parsing test file")
LOGGER.debug(f"Data: {data}")

action_data = data.get("actions", {}).get(action_str, {})

LOGGER.debug(f"Action data: {action_data}")

if not action_data:
    LOGGER.error(f"Action {action_str} not found in {filename}.yml")
    exit(1)

action_type = action_data.get("type", "Type not found")
action_models = [model.stem for model in Path("tests", "models").glob("*.py")] + ["ui"]

if action_type not in action_models:
    LOGGER.error(f'Action {action_str} has an invalid type "{action_type}"')
    exit(1)
elif ARGS.type == "ui" and action_type != "ui":
    LOGGER.error(f"Action {action_str} is not a UI action")
    exit(1)

action = parse_action(
    LOGGER,
    integration_action.choices,
    ARGS.integration,
    action_str,
    action_data,
    ARGS.type,
)

if ARGS.integration not in action.integrations:
    LOGGER.error(f"Action {action_str} is not compatible with integration {ARGS.integration}")
    exit(1)

test_config = data.get("config", {}) | data.get(ARGS.integration, {}).get("config", {})

content = Path("tests", "utils", "config.yml").read_text()

# Replace ${VAR} patterns with the corresponding environment variable
content = resolve_env_placeholders(content)

config = safe_load(content)

test_crowdsec_config = config.get("crowdsec_config", {}) | config.get(ARGS.integration, {}).get("crowdsec_config", {})
crowdsec_config = test_crowdsec_config | data.get("crowdsec_config", {}) | data.get(ARGS.integration, {}).get("crowdsec_config", {})

LOGGER.debug(f"Test config: {test_config}")
LOGGER.debug(f"Default config: {config}")
LOGGER.debug(f"Action config: {action.config}")

SERVICES_PATH = Path("tests", "misc", "docker", "services.yml")
services = safe_load(SERVICES_PATH.read_text())

if action.services:
    services["services"] = services.get("services", {}) | action.services
    redis_client.set("restart_stack", 1)
    redis_client.set("restart_services", 1)

database = action.database
log_from = action.log_from
need_socket = False
ingress = {}

try:
    config["variables"]["TZ"] = get_localzone().key
except BaseException as e:
    LOGGER.warning(f"Couldn't fetch local timezone: {e}, falling back to UTC")
    config["variables"]["TZ"] = "UTC"

if ARGS.integration == "All-in-one":
    config["variables"]["DNS_RESOLVERS"] = "10.20.30.20 127.0.0.11"
    config["variables"]["SERVICE_UI"] = "yes" if ARGS.type == "ui" else "no"
    config["variables"]["SERVICE_API"] = "yes" if ARGS.type == "api" else "no"
elif ARGS.integration != "Linux":
    config["variables"]["BUNKERWEB_INSTANCES"] = "bunkerweb"
    config["variables"]["DNS_RESOLVERS"] = "10.20.30.20 127.0.0.11"
    config["variables"]["API_LISTEN_IP"] = "0.0.0.0"
    config["variables"]["API_WHITELIST_IP"] = "127.0.0.0/8 10.20.30.0/24"
    # Since 1.7 the scheduler only dispatches: it reaches the API, which queues the
    # job on the broker for a Celery worker. Without these three the stack boots and
    # runs zero jobs.
    config["variables"]["API_URL"] = "http://svc-bunkerweb-api.bunkerweb.svc.cluster.local:8888" if ARGS.integration == "Kubernetes" else "http://bw-api:8888"
    config["variables"]["API_TOKEN"] = API_TEST_TOKEN

if ARGS.type == "ui" and action.annotations.get("bunkerweb.io/SERVER_NAME") == "www.example.com":
    del action.annotations["bunkerweb.io/SERVER_NAME"]

if ARGS.type == "ui" and action.labels.get("bunkerweb.SERVER_NAME") == "www.example.com":
    del action.labels["bunkerweb.SERVER_NAME"]

if ARGS.integration in ("Autoconf", "Kubernetes"):
    config["variables"]["BUNKERWEB_INSTANCES"] = ""
    config["variables"]["SERVER_NAME"] = ""
    config["variables"]["MULTISITE"] = "yes"
    config["variables"][f"{ARGS.integration.upper()}_MODE"] = "yes"

    if database == "sqlite":
        LOGGER.warning("🚨 SQLite is only supported in Linux, Docker and All-in-one integrations, defaulting to MariaDB")
        database = "mariadb"

    if ARGS.integration == "Kubernetes":
        test_annotations = data.get("annotations", {})

        LOGGER.debug(f"Test annotations: {test_annotations}")
        LOGGER.debug(f"Default annotations: {services}")
        LOGGER.debug(f"Action annotations: {action.annotations}")

        all_annotations = test_annotations | action.annotations

        ingress = safe_load(Path("tests", "misc", "k8s", "services.ingress.yml").read_text())

        config["variables"].pop("HTTP_PORT", None)
        config["variables"].pop("HTTPS_PORT", None)

        config["variables"]["DNS_RESOLVERS"] = "kube-dns.kube-system.svc.cluster.local"
        config["variables"]["API_WHITELIST_IP"] = "127.0.0.0/8 10.0.0.0/8"
        config["variables"]["USE_REDIS"] = "yes"
        config["variables"]["REDIS_HOST"] = "svc-bunkerweb-redis.bunkerweb.svc.cluster.local"
        config["variables"]["DATABASE_RETRY_TIMEOUT"] = "120"

        if all_annotations.get("bunkerweb.io/REVERSE_PROXY_URL", all_annotations.get("REVERSE_PROXY_URL", "/")):
            for key, value in all_annotations.copy().items():
                if value is None:
                    continue

                key = key.replace("bunkerweb.io/", "", 1)

                if key in ("REVERSE_PROXY_URL", "SERVER_NAME"):
                    if "spec" in ingress:
                        continue

                    ingress["spec"] = {
                        "rules": [
                            {
                                "host": all_annotations.pop("bunkerweb.io/SERVER_NAME", all_annotations.pop("SERVER_NAME", "www.example.com")),
                                "http": {
                                    "paths": [
                                        {
                                            "path": all_annotations.pop("bunkerweb.io/REVERSE_PROXY_URL", all_annotations.pop("REVERSE_PROXY_URL", "/")),
                                            "pathType": "Prefix",
                                            "backend": {
                                                "service": {
                                                    "name": "svc-app1",
                                                    "port": {
                                                        "number": 80,
                                                    },
                                                },
                                            },
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                    continue

                if "annotations" not in ingress["metadata"]:
                    ingress["metadata"]["annotations"] = {}

                ingress["metadata"]["annotations"][f"bunkerweb.io/{key}"] = value

            namespace = safe_load(Path("tests", "misc", "k8s", "services.namespace.yml").read_text())
            deployment = safe_load(Path("tests", "misc", "k8s", "services.deployment.yml").read_text())
            svc = safe_load(Path("tests", "misc", "k8s", "services.svc.yml").read_text())

            services = (
                safe_dump(namespace, indent=2)
                + "\n---\n"
                + safe_dump(ingress, indent=2)
                + "\n---\n"
                + safe_dump(deployment, indent=2)
                + "\n---\n"
                + safe_dump(svc, indent=2)
            )

            LOGGER.debug(f"Final ingress: {services}")
        else:
            all_annotations.pop("bunkerweb.io/REVERSE_PROXY_URL", all_annotations.pop("REVERSE_PROXY_URL", "/"))
            for key, value in all_annotations.copy().items():
                if value is None:
                    continue
                config["variables"][key.replace("bunkerweb.io/", "", 1)] = value

        LOGGER.debug(f"Final annotations: {services}")
    else:
        need_socket = True
        test_labels = data.get("labels", {}) | data.get(ARGS.integration, {}).get("labels", {})

        LOGGER.debug(f"Test labels: {test_labels}")
        LOGGER.debug(f"Default labels: {services}")
        LOGGER.debug(f"Action labels: {action.labels}")

        all_labels = test_labels | action.labels

        for key, value in all_labels.items():
            if value is None:
                continue
            if "labels" not in services["services"]["app1"]:
                services["services"]["app1"]["labels"] = {}
            services["services"]["app1"]["labels"][f"bunkerweb.{key.replace('bunkerweb.', '', 1)}"] = value

        LOGGER.debug(f"Final labels: {services}")
elif log_from == "controller":
    LOGGER.warning("🚨 The 'controller' log from is only compatible with Autoconf and Kubernetes integrations, defaulting to scheduler")
    log_from = "scheduler"


DATABASE_SPECS = {
    "mariadb": {
        "extension": "pymysql",
        "port": 3306,
    },
    "mysql": {
        "extension": "pymysql",
        "port": 3306,
    },
    "postgresql": {
        "extension": "psycopg",
        "port": 5432,
    },
    "oracle": {
        "extension": "oracledb",
        "port": 1521,
    },
}
DATABASE_HOST = "bw-db" if ARGS.integration != "Kubernetes" else "svc-bunkerweb-db.bunkerweb-db.svc.cluster.local"

if database != "sqlite":
    config["variables"]["DATABASE_URI"] = (
        f"{database}+{DATABASE_SPECS[database]['extension']}://bunkerweb:secret@{DATABASE_HOST}:{DATABASE_SPECS[database]['port']}"
        + ("/db" if database != "oracle" else "?service_name=FREEPDB1")
    )

version_file_path = Path(sep, "tmp", "bw_version.txt")
version = data.get("bw_version", "tests")
integration_version = data.get(ARGS.integration, {}).get("bw_version", "tests")
if integration_version != "tests":
    version = integration_version
if action.bw_version != "tests":
    version = action.bw_version
# Ensure bw_version can be provided via environment variables as ${VAR}
version = resolve_env_placeholders(version)
LOGGER.info(f"📝 Writing {version_file_path} with version {version!r}")
version_file_path.write_text(version)

services_path = Path(sep, "tmp", "services.yml")
services_path.unlink(missing_ok=True)

# An example-backed spec brings its own stack: the whole thing (BunkerWeb, scheduler,
# API, worker, broker and the application) comes from examples/<name>, so the framework
# deploys that instead of composing one from services.yml.
example_name = data.get("example") or data.get(ARGS.integration, {}).get("example")
example_clear()
if example_name:
    example_materialise(LOGGER, example_name, ARGS.integration, version)
elif ARGS.integration != "Kubernetes":
    LOGGER.info("📝 Writing /tmp/services.yml")
    services_path.write_text(safe_dump(services, indent=2))
elif "spec" in ingress:
    LOGGER.info("📝 Writing /tmp/services.yml")
    services_path.write_text(services)

if ARGS.type == "ui":
    config["variables"].update({"SERVER_NAME": "", "SESSIONS_CHECK_IP": "no"})

    base_ui_config = {"UI_HOST": "http://bw-ui:7000", "MULTISITE": "yes"}
    if ARGS.integration == "Linux":
        base_ui_config["UI_HOST"] = "http://127.0.0.1:7000"
    elif ARGS.integration == "Kubernetes":
        base_ui_config["UI_HOST"] = "http://svc-bunkerweb-ui.bunkerweb.svc.cluster.local:7000"

    config["variables"] = base_ui_config | config["variables"]

for key, value in (test_config | action.config).items():
    if value is None:
        config["variables"].pop(key, None)
        continue
    config["variables"][key] = value

for key, value in action.crowdsec_config.items():
    if value is None:
        crowdsec_config.pop(key, None)
        continue
    crowdsec_config[key] = value

if ARGS.type == "ui":
    ui_config = data.get("ui", {}) | data.get(ARGS.integration, {}).get("ui", {})

    if database != "sqlite":
        config["ui"][
            "DATABASE_URI"
        ] = f"{database}+{DATABASE_SPECS[database]['extension']}://bunkerweb:secret@{DATABASE_HOST}:{DATABASE_SPECS[database]['port']}/db"

    for key, value in (ui_config | action.ui).items():
        if value is None:
            config["ui"].pop(key.upper(), None)
            continue
        config["ui"][key.upper()] = value

    if config["labels"].get("bunkerweb.SERVER_NAME") == "www.example.com":
        del config["labels"]["bunkerweb.SERVER_NAME"]

    if config["annotations"].get("bunkerweb.io/SERVER_NAME") == "www.example.com":
        del config["annotations"]["bunkerweb.io/SERVER_NAME"]

# The API is part of every 1.7 stack, not just `type: api` runs: the scheduler
# dispatches jobs through it and the UI has no database access of its own. Its env is
# therefore built for every type.
api_config = data.get("api", {}) | data.get(ARGS.integration, {}).get("api", {})

if database != "sqlite":
    config["api"][
        "DATABASE_URI"
    ] = f"{database}+{DATABASE_SPECS[database]['extension']}://bunkerweb:secret@{DATABASE_HOST}:{DATABASE_SPECS[database]['port']}/db"

for key, value in (api_config | action.api).items():
    if value is None:
        config["api"].pop(key.upper(), None)
        continue
    config["api"][key.upper()] = value

if ARGS.integration not in ("Linux", "All-in-one"):
    # Job broker only — deliberately not the WAF datastore Redis, which 1.7 split off.
    jobs_broker_url = (
        "redis://svc-bunkerweb-jobs-broker.bunkerweb.svc.cluster.local:6379/0" if ARGS.integration == "Kubernetes" else "redis://bw-jobs-broker:6379/0"
    )
    config["api"]["API_TOKEN"] = API_TEST_TOKEN
    config["api"]["CELERY_BROKER_URL"] = jobs_broker_url
    # Pin the database explicitly rather than letting the images fall back to their own
    # default: on SQLite a mismatch here means the API and the worker quietly read a
    # different file than the scheduler wrote.
    config["api"].setdefault("DATABASE_URI", config["variables"]["DATABASE_URI"])

    if ARGS.integration == "Kubernetes":
        # The worker deployment reads bw-secret (built from `variables`), so the broker
        # URL has to travel there too. BunkerWeb itself ignores the extra key.
        config["variables"]["CELERY_BROKER_URL"] = jobs_broker_url
    # The worker runs the jobs the API queues: it needs the same database and the
    # same broker, nothing else.
    config["worker"] = {
        "CELERY_BROKER_URL": jobs_broker_url,
        "CUSTOM_LOG_LEVEL": config["api"].get("CUSTOM_LOG_LEVEL", "debug"),
        "DATABASE_URI": config["api"]["DATABASE_URI"],
    }

crowdsec_config_path = Path(sep, "tmp", "crowdsec.env")
crowdsec_config_path.unlink(missing_ok=True)

LOGGER.debug(f"Final config: {config}")
if ARGS.integration != "Kubernetes":
    if ARGS.integration == "All-in-one" and config["variables"].get("AUTOCONF_MODE", "no") == "yes":
        need_socket = True
        config["variables"]["DOCKER_HOST"] = "tcp://bw-docker:2375"

    BW_ETC.mkdir(parents=True, exist_ok=True)

    def write_env(name: str, values: dict) -> None:
        path = BW_ETC.joinpath(name)
        LOGGER.info(f"📝 Writing {path}")
        path.write_text("\n".join([f"{key}={value}" for key, value in values.items()]))

    write_env("variables.env", config["variables"])

    if ARGS.type == "ui":
        write_env("ui.env", config["ui"])

    if ARGS.integration not in ("Linux", "All-in-one"):
        write_env("api.env", config["api"])
        write_env("worker.env", config["worker"])

    if test_crowdsec_config != crowdsec_config:
        LOGGER.debug(f"Final CrowdSec config: {crowdsec_config}")
        # Check if config file exists and content has changed
        current_content = ""
        if crowdsec_config_path.exists():
            current_content = crowdsec_config_path.read_text()

        new_content = "\n".join([f"{key}={value}" for key, value in crowdsec_config.items()])

        if new_content != current_content:
            LOGGER.info(f"📝 Writing {crowdsec_config_path}")
            crowdsec_config_path.write_text(new_content)
            redis_client.set("restart_crowdsec", 1)
else:
    secrets = safe_load(Path("tests", "misc", "k8s", "secrets.yml").read_text())
    secrets["data"] = {key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in config["variables"].items()}

    LOGGER.info("📝 Writing /tmp/secrets.yml")
    Path(sep, "tmp", "secrets.yml").write_text(safe_dump(secrets, indent=2))

    if ARGS.type == "ui":
        ui_secrets = safe_load(Path("tests", "misc", "k8s", "secrets-ui.yml").read_text())
        ui_secrets["data"] = {key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in config["ui"].items()}

        LOGGER.info("📝 Writing /tmp/secrets-ui.yml")
        Path(sep, "tmp", "secrets-ui.yml").write_text(safe_dump(ui_secrets, indent=2))

    # Written for every type: the API deployment is part of every 1.7 cluster.
    api_secrets = safe_load(Path("tests", "misc", "k8s", "secrets-api.yml").read_text())
    api_secrets["data"] = {key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in config["api"].items()}

    LOGGER.info("📝 Writing /tmp/secrets-api.yml")
    Path(sep, "tmp", "secrets-api.yml").write_text(safe_dump(api_secrets, indent=2))

timeout = action.timeout
if ARGS.integration == "Kubernetes" and action.timeout < 420:
    LOGGER.warning("🔍 We need at least a 7 minutes timeout for Kubernetes tests")
    timeout = 420

redis_acl_path = Path(sep, "tmp", "redis-acl")
redis_acl_path.mkdir(parents=True, exist_ok=True)
for file in redis_acl_path.glob("*"):
    file.unlink(missing_ok=True)

valkey_acl_path = Path(sep, "tmp", "valkey-acl")
valkey_acl_path.mkdir(parents=True, exist_ok=True)
for file in valkey_acl_path.glob("*"):
    file.unlink(missing_ok=True)

redis_client.delete("redis_type")

if action.type == "redis" and (
    any(
        (
            action.port != 6379,
            action.password,
            action.tls,
            action.tls_port != 6379,
            action.user,
            action.sentinel,
            action.sentinel_port != 26379,
            action.sentinel_master != "bw-master",
            # action.sentinel_tls, # TODO: uncomment when we have the sentinel tls
            # action.sentinel_tls_port,
            action.sentinel_user,
        )
        or action.valkey
    )
):
    # Configuration for Redis vs Valkey - centralized for easier maintenance
    REDIS_CONFIG = {
        "redis": {
            "port": "6379",
            "tls_port": "6379",
            "sentinel_port": "26379",
            "type": "master",
            "acl_file": redis_acl_path.joinpath("redis.acl"),
            "env_file": Path(sep, "tmp", "redis-master.env"),
            "secrets_template": Path("tests", "misc", "k8s", "redis-master-secrets.yml"),
            "secrets_file": Path(sep, "tmp", "redis-master-secrets.yml"),
            "slave_env_file": Path(sep, "tmp", "redis-slave.env"),
            "slave_secrets_template": Path("tests", "misc", "k8s", "redis-slave-secrets.yml"),
            "slave_secrets_file": Path(sep, "tmp", "redis-slave-secrets.yml"),
            "sentinel_secrets_template": Path("tests", "misc", "k8s", "redis-sentinel-secrets.yml"),
            "sentinel_secrets_file": Path(sep, "tmp", "redis-sentinel-secrets.yml"),
        },
        "valkey": {
            "port": "6379",
            "tls_port": "6380",
            "sentinel_port": "26379",
            "type": "valkey",
            "acl_file": valkey_acl_path.joinpath("valkey.acl"),
            "env_file": Path(sep, "tmp", "valkey.env"),
            "secrets_template": Path("tests", "misc", "k8s", "valkey-secrets.yml"),
            "secrets_file": Path(sep, "tmp", "valkey-secrets.yml"),
            "slave_env_file": Path(sep, "tmp", "valkey-slave.env"),
            "slave_secrets_template": Path("tests", "misc", "k8s", "valkey-slave-secrets.yml"),
            "slave_secrets_file": Path(sep, "tmp", "valkey-slave-secrets.yml"),
            "sentinel_secrets_template": Path("tests", "misc", "k8s", "valkey-sentinel-secrets.yml"),
            "sentinel_secrets_file": Path(sep, "tmp", "valkey-sentinel-secrets.yml"),
        },
    }

    db_type = "valkey" if action.valkey else "redis"
    redis_config = REDIS_CONFIG[db_type]

    LOGGER.info(f"🧰 Using {db_type.capitalize()}")

    redis_type = redis_config["type"]
    redis_env = {
        "ALLOW_EMPTY_PASSWORD": "yes",
        "REDIS_PORT_NUMBER": redis_config["port"],
        "REDIS_TLS_AUTH_CLIENTS": "no",
    }

    valkey_env = {}
    valkey_slave_env = {}

    if action.user:
        LOGGER.info(f"📝 Writing {redis_config['acl_file']}")
        redis_config["acl_file"].write_text(f"user {action.user[0]} on >{action.user[1]} +@all ~*")
        redis_config["acl_file"].chmod(0o777)
        redis_env["REDIS_ACLFILE"] = f"/acl/{redis_config['acl_file'].name}"
    elif action.password:
        redis_env["REDIS_PASSWORD"] = action.password

    if action.tls:
        redis_env.update(
            {
                "REDIS_TLS_ENABLED": "yes",
                "REDIS_PORT_NUMBER": "36380" if db_type == "redis" else "36479",
                "REDIS_TLS_PORT_NUMBER": redis_config["tls_port"],
                "REDIS_TLS_CERT_FILE": "/tls/redis.pem",
                "REDIS_TLS_KEY_FILE": "/tls/redis.key",
                "REDIS_TLS_CA_FILE": "/tls/ca.crt",
            }
        )

    if db_type == "valkey":
        tls_enabled = "yes" if action.tls else "no"
        valkey_env = {
            "VALKEY_PORT_NUMBER": redis_config["port"],
            "VALKEY_TLS_ENABLED": tls_enabled,
            "VALKEY_DATA_DIR": "/data",
            "VALKEY_ACL_FILE": f"/acl/{redis_config['acl_file'].name}",
            "VALKEY_TLS_CERT_FILE": "/tls/valkey.crt",
            "VALKEY_TLS_KEY_FILE": "/tls/valkey.key",
            "VALKEY_TLS_CA_FILE": "/tls/ca.crt",
            "VALKEY_TLS_AUTH_CLIENTS": "optional",
        }
        if action.tls:
            valkey_env["VALKEY_TLS_PORT_NUMBER"] = redis_config["tls_port"]
        if action.password and not action.user:
            valkey_env["VALKEY_PASSWORD"] = action.password

        LOGGER.debug(f"Valkey env: {valkey_env}")

    if action.sentinel:
        if db_type == "valkey":
            redis_type = "valkey-sentinel"
        else:
            redis_type = "sentinel"

        redis_env.update(
            {
                "REDIS_REPLICATION_MODE": "master",
                "REDIS_MASTER_SET": action.sentinel_master,
            }
        )
        if db_type == "valkey":
            tls_enabled = "yes" if action.tls else "no"
            valkey_slave_env = {
                "VALKEY_PORT_NUMBER": redis_config["port"],
                "VALKEY_TLS_ENABLED": tls_enabled,
                "VALKEY_DATA_DIR": "/data",
                "VALKEY_ACL_FILE": f"/acl/{redis_config['acl_file'].name}",
                "VALKEY_TLS_CERT_FILE": "/tls/valkey.crt",
                "VALKEY_TLS_KEY_FILE": "/tls/valkey.key",
                "VALKEY_TLS_CA_FILE": "/tls/ca.crt",
                "VALKEY_TLS_AUTH_CLIENTS": "optional",
                "VALKEY_REPLICAOF_HOST": "valkey" if "REDIS_HOST" not in config else config["REDIS_HOST"],
                "VALKEY_REPLICAOF_PORT": redis_env["REDIS_PORT_NUMBER"] if not action.tls else redis_config["tls_port"],
            }
            if action.tls:
                valkey_slave_env["VALKEY_TLS_PORT_NUMBER"] = redis_config["tls_port"]
            if action.password and not action.user:
                valkey_slave_env["VALKEY_MASTER_PASSWORD"] = action.password
            if action.user:
                valkey_slave_env["VALKEY_MASTER_USERNAME"] = action.user[0]
                valkey_slave_env["VALKEY_MASTER_PASSWORD"] = action.user[1]
            LOGGER.debug(f"Valkey slave env: {valkey_slave_env}")

    LOGGER.debug(f"{db_type.capitalize()} master env: {redis_env}")

    if ARGS.integration != "Kubernetes":
        LOGGER.info(f"📝 Writing {redis_config['env_file']}")
        redis_config["env_file"].write_text("\n".join([f"{key}={value}" for key, value in (valkey_env if db_type == "valkey" else redis_env).items()]))
        redis_config["env_file"].chmod(0o777)
    else:
        secrets = safe_load(redis_config["secrets_template"].read_text())
        secrets["data"] = {key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in (valkey_env if db_type == "valkey" else redis_env).items()}

        LOGGER.info(f"📝 Writing {redis_config['secrets_file']}")
        redis_config["secrets_file"].write_text(safe_dump(secrets, indent=2))
    if action.sentinel:
        LOGGER.info(f"🧰 Using {db_type.capitalize()} Sentinel")
        redis_env.update(
            {
                "REDIS_REPLICATION_MODE": "slave",
                "REDIS_MASTER_HOST": "redis-master" if "REDIS_HOST" not in config["variables"] else config["variables"]["REDIS_HOST"],
                "REDIS_MASTER_PORT_NUMBER": redis_env["REDIS_PORT_NUMBER"] if not action.tls else redis_env["REDIS_TLS_PORT_NUMBER"],
            }
        )
        if db_type == "valkey":
            valkey_slave_env["VALKEY_REPLICAOF_HOST"] = redis_env["REDIS_MASTER_HOST"]
            valkey_slave_env["VALKEY_REPLICAOF_PORT"] = redis_env["REDIS_MASTER_PORT_NUMBER"]

        if action.password:
            redis_env["REDIS_MASTER_PASSWORD"] = action.password

        LOGGER.debug(f"{db_type.capitalize()} slave env: {redis_env}")

        if ARGS.integration != "Kubernetes":
            LOGGER.info(f"📝 Writing {redis_config['slave_env_file']}")
            redis_config["slave_env_file"].write_text(
                "\n".join(f"{key}={value}" for key, value in (valkey_slave_env if db_type == "valkey" else redis_env).items())
            )
            redis_config["slave_env_file"].chmod(0o777)
        else:
            secrets = safe_load(redis_config["slave_secrets_template"].read_text())
            secrets["data"] = {
                key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in (valkey_slave_env if db_type == "valkey" else redis_env).items()
            }

            LOGGER.info(f"📝 Writing {redis_config['slave_secrets_file']}")
            redis_config["slave_secrets_file"].write_text(safe_dump(secrets, indent=2))

        sentinel_env = {
            "ALLOW_EMPTY_PASSWORD": "yes",
            "REDIS_SENTINEL_PORT_NUMBER": redis_config["sentinel_port"],
            "REDIS_SENTINEL_TLS_AUTH_CLIENTS": "no",
            "REDIS_MASTER_SET": redis_env["REDIS_MASTER_SET"],
            "REDIS_MASTER_HOST": redis_env["REDIS_MASTER_HOST"],
            "REDIS_MASTER_PORT_NUMBER": redis_env["REDIS_MASTER_PORT_NUMBER"],
        }

        if action.password:
            sentinel_env["REDIS_MASTER_PASSWORD"] = redis_env["REDIS_MASTER_PASSWORD"]

        content = ""
        if action.sentinel_user:
            LOGGER.info(f"📝 Writing /tmp/{db_type}-acl/sentinel.acl")
            content = f"user {action.sentinel_user[0]} on >{action.sentinel_user[1]} +@all ~* +sentinel"

        if db_type == "valkey":
            valkey_acl_path.joinpath("sentinel.acl").write_text(content)
            valkey_acl_path.joinpath("sentinel.acl").chmod(0o777)
        else:
            redis_acl_path.joinpath("sentinel.acl").write_text(content)
            redis_acl_path.joinpath("sentinel.acl").chmod(0o777)

        # if action.sentinel_tls: # TODO: uncomment when we have the sentinel tls
        #     sentinel_env.update(
        #         {
        #             "REDIS_REDIS_SENTINEL_TLS_ENABLED": "yes",
        #             "REDIS_SENTINEL_PORT_NUMBER": "26380",
        #             "REDIS_SENTINEL_TLS_PORT_NUMBER": "26379",
        #             "REDIS_SENTINEL_TLS_CERT_FILE": "/tls/sentinel.pem",
        #             "REDIS_SENTINEL_TLS_KEY_FILE": "/tls/sentinel.key",
        #             "REDIS_SENTINEL_TLS_CA_FILE": "/tls/sentinel_ca.crt",
        #         }
        #     )

        LOGGER.debug(f"{db_type.capitalize()} sentinel env: {sentinel_env}")

        if ARGS.integration != "Kubernetes":
            LOGGER.info(f"📝 Writing /tmp/{db_type}-sentinel.env")
            sentinel_file = Path(sep, "tmp", f"{db_type}-sentinel.env")
            sentinel_file.write_text("\n".join([f"{key}={value}" for key, value in sentinel_env.items()]))
            sentinel_file.chmod(0o777)
        else:
            secrets = safe_load(redis_config["sentinel_secrets_template"].read_text())
            secrets["data"] = {key: b64encode(value.encode("utf-8")).decode("utf-8") for key, value in sentinel_env.items()}

            LOGGER.info(f"📝 Writing {redis_config['sentinel_secrets_file']}")
            redis_config["sentinel_secrets_file"].write_text(safe_dump(secrets, indent=2))
    redis_client.set("redis_type", redis_type)

# Check if BunkerWeb version has changed from the previous action
previous_bw_version = redis_client.get("previous_bw_version")
if previous_bw_version:
    previous_bw_version = previous_bw_version.decode() if isinstance(previous_bw_version, bytes) else previous_bw_version
if previous_bw_version and previous_bw_version != action.bw_version:
    LOGGER.info(f"🔄 BunkerWeb version changed from {previous_bw_version} to {action.bw_version}, whole stack will be restarted")
    redis_client.set("restart_stack", 1)
    redis_client.set("restart_whole_stack", 1)
    # Don't set full_clean to True, we want to restart without clearing volumes
else:
    LOGGER.debug(f"🔍 BunkerWeb version unchanged: {action.bw_version}")

# Store the current version for the next action
redis_client.set("previous_bw_version", action.bw_version)

redis_client.set("database", database)
redis_client.set("log_from", log_from)
redis_client.set("timeout", timeout)
redis_client.set("retries", action.retries)
redis_client.set("need_socket", 1 if need_socket else 0)
