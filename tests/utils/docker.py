from functools import cache
from logging import Logger
from os import getenv
from typing import List, Literal, Optional, Tuple

from docker import DockerClient
from docker.models.containers import Container

CONTAINER_TYPES = {
    "bunkerweb": {"label": "bunkerweb.INSTANCE"},
    "controller": {"label": "bunkerweb.type=autoconf"},
    "scheduler": {"label": "bunkerweb.type=scheduler"},
    "database": {"name": "bw-db"},
    # 1.7 moved the database clients (sqlite3, mariadb, psql) to the API image, so
    # queries run there rather than in the scheduler.
    "api": {"name": "bw-api"},
}

AIO_LOG_TAGS = {
    # NGINX and ModSecurity files are streamed separately, but belong to the
    # bunkerweb log stream exposed by a dedicated container.
    "bunkerweb": ("[BUNKERWEB]", "[NGINX.ACCESS]", "[NGINX.ERROR]", "[MODSEC]"),
    "controller": ("[AUTOCONF]",),
    "scheduler": ("[SCHEDULER]",),
    "api": ("[API]",),
}
AIO_RECOGNIZED_LOG_TAGS = {tag for tags in AIO_LOG_TAGS.values() for tag in tags} | {
    "[WORKER]",
    "[UI]",
    "[REDIS]",
    "[CROWDSEC]",
    "[LOGSTREAM]",
    "[LOGROTATE]",
}


@cache
def get_docker_client() -> DockerClient:
    return DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))


@cache
def get_container(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database", "api"]) -> Container:
    docker_client = get_docker_client()

    filters = CONTAINER_TYPES.get(_type)
    if not filters:
        raise ValueError(f"Invalid container type: {_type}")

    containers = docker_client.containers.list(filters=filters) or (
        docker_client.containers.list(filters={"label": "bunkerweb.type=all-in-one"}) if _type != "database" else []
    )

    if not containers:
        logger.error(f"No {_type.title()} container found")
        exit(1)

    return containers[0]


def get_logs(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database", "api"], since: Optional[float]) -> List[str]:
    container = get_container(logger, _type)
    logs = (
        container.logs(
            since=since,
            stdout=True,
            stderr=True,
            timestamps=True,
        )
        .decode("utf-8")
        .strip()
        .split("\n")
    )

    if (container.labels or {}).get("bunkerweb.type") == "all-in-one" and (tags := AIO_LOG_TAGS.get(_type)):
        return [line for line in logs if (tag := line.partition(" ")[2].partition(" ")[0]) not in AIO_RECOGNIZED_LOG_TAGS or tag in tags]

    return logs


def run_command(logger: Logger, _type: Literal["bunkerweb", "controller", "scheduler", "database", "api"], command: List[str]) -> Tuple[int, str]:
    exit_code, output = get_container(logger, _type).exec_run(
        command,
        stdout=True,
        stderr=True,
    )
    return exit_code, output.decode("utf-8").strip()
