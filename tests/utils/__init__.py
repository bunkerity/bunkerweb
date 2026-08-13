from base64 import b64decode
from datetime import datetime
from logging import Logger
from os import getenv
from os.path import sep
from pathlib import Path
from re import MULTILINE, compile as re_compile
from typing import List, Literal, Optional, Tuple, Union
import platform
import subprocess

from dotenv import dotenv_values
from yaml import safe_load

from .docker import get_logs as get_docker_logs, run_command as run_docker_command
from .k8s import get_logs as get_k8s_logs, run_command as run_k8s_command

ERROR_LOG_FILE = Path(sep, "var", "log", "bunkerweb", "error.log")

# Same override generate.py honours, so a local run reads back the env files it wrote
BW_TESTS_ETC = Path(getenv("BW_TESTS_ETC", Path(sep, "etc", "bunkerweb").as_posix()))

# Regular expression to find ${VAR} patterns
ENV_VAR_PATTERN = re_compile(r"\$\{([^}^{]+)\}", MULTILINE)
IS_FREEBSD = platform.system() == "FreeBSD"


# Resolve ${VAR} placeholders in a string using environment variables
# Returns the input unchanged if it is not a string
# Example: "release-${BW_CHANNEL}" -> "release-stable" if BW_CHANNEL=stable
def resolve_env_placeholders(value: str):
    if not isinstance(value, str):
        return value
    for match in ENV_VAR_PATTERN.finditer(value):
        placeholder = match.group(0)
        key = match.group(1)

        # Try OS env first
        resolved = getenv(key)

        # Fallback to Redis-stored values if not in OS env
        if resolved is None:
            try:
                from redis import Redis  # Lazy import to avoid heavy deps at module import time

                r = Redis(host="localhost", port=6379, db=0, decode_responses=True)
                if r.ping():
                    resolved = r.get(key)
            except Exception:
                resolved = None

        value = value.replace(placeholder, resolved if resolved is not None else placeholder)
    return value


def get_logs(
    logger: Logger,  # noqa: F811
    integration: Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"],
    since: Optional[Union[datetime, str]] = None,
    *,
    log_from: Literal["bunkerweb", "controller", "scheduler", "database"] = "bunkerweb",
) -> List[str]:
    if integration != "Linux":
        if isinstance(since, str):
            since = datetime.fromisoformat(since)

        logger.debug(f"Getting logs from {log_from}" + (f" since {since}" if since else ""))

        if integration == "Kubernetes":
            return get_k8s_logs(logger, log_from, since)
        return get_docker_logs(logger, "bunkerweb" if integration == "Linux" else log_from, since)

    with ERROR_LOG_FILE.open("r", encoding="utf-8") as file:
        return file.readlines()


def run_command(logger: Logger, integration: Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"], command: str) -> Tuple[int, str]:  # noqa: F811
    command = command.split(" ")
    if command[0] != "bwcli":
        command.insert(0, "bwcli")
    if "--debug" not in command:
        command.append("--debug")

    if integration == "Kubernetes":
        return 0, run_k8s_command(logger, "scheduler", command)
    if integration == "Linux" and IS_FREEBSD:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, (result.stdout + result.stderr).strip()
    return run_docker_command(logger, "bunkerweb" if integration == "Linux" else "scheduler", command)


def execute_query(
    logger: Logger,  # noqa: F811
    integration: Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"],
    database: Literal["sqlite", "mariadb", "mysql", "postgresql", "oracle"],
    query: str,
) -> Tuple[int, str]:  # Returning exit_code, output
    if database == "sqlite":
        if integration in ("Autoconf", "Kubernetes"):
            raise NotImplementedError("SQLite is not supported in Autoconf and Kubernetes")
        if integration == "Linux" and IS_FREEBSD:
            result = subprocess.run(
                ["sqlite3", "/var/lib/bunkerweb/db.sqlite3", query],
                capture_output=True,
                text=True,
            )
            return result.returncode, (result.stdout + result.stderr).strip()
        return run_docker_command(logger, "bunkerweb" if integration == "Linux" else "scheduler", f"sqlite3 /var/lib/bunkerweb/db.sqlite3 {query!r}")

    # Handle database URI depending on the integration
    if integration == "Kubernetes":
        database_uri = b64decode(safe_load(Path(sep, "tmp", "secrets.yml").read_text())["data"]["DATABASE_URI"].encode("utf-8")).decode("utf-8")
    else:
        database_uri = dotenv_values(BW_TESTS_ETC.joinpath("variables.env").as_posix())["DATABASE_URI"]

    db_host = database_uri.rsplit("@", 1)[1].split("/")[0].split(":")
    db_port = None
    if len(db_host) == 1:
        db_host = db_host[0]
    else:
        db_host, db_port = db_host

    db_user = database_uri.split("://")[1].split(":")[0]
    db_password = database_uri.split("://")[1].split(":")[1].rsplit("@", 1)[0]
    db_database_name = database_uri.split("/")[-1].split("?")[0]

    # Construct the command for MySQL/MariaDB or PostgreSQL
    command = []
    if database in ("mariadb", "mysql"):
        command = ["env", f"MYSQL_PWD={db_password}", database, "-h", db_host, "-u", db_user, db_database_name]
        if db_port:
            command.extend(["-P", db_port])
        command.extend(["-e", query])
    elif database == "postgresql":
        command = ["env", f"PGPASSWORD={db_password}", "psql", "-h", db_host, "-U", db_user, "-w"]
        if db_port:
            command.extend(["-p", db_port])
        command.extend([db_database_name, "-c", query])
    elif database == "oracle":
        command = ["sqlplus", "-S", f"{db_user}/{db_password}@{db_host}" + (f":{db_port}" if db_port else "") + f"/{db_database_name}", "-c", query]

    logger.debug(f"Executing query: {command}")

    # Run the command in either Kubernetes or Docker
    if integration == "Kubernetes":
        return 0, run_k8s_command(logger, "database", command)
    if integration == "Linux" and IS_FREEBSD:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, (result.stdout + result.stderr).strip()
    return run_docker_command(logger, "bunkerweb" if integration == "Linux" else "database", command)


if __name__ == "__main__":
    from argparse import ArgumentParser
    from logging import getLogger
    import logger  # noqa: F811, F401

    LOGGER = getLogger("UTILS")

    parser = ArgumentParser(prog="Runner utils", description="Utils for the test runner (will show logs of the Integration)")
    parser.add_argument("integration", type=str, help="Integration to test", choices=["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"])
    ARGS = parser.parse_args()

    LOGGER.info(get_logs(LOGGER, ARGS.integration))
