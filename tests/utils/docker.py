from functools import cache
from logging import Logger
from os import getenv, sep
from pathlib import Path
from re import sub
from typing import List, Literal, Optional, Set, Tuple

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

# Scoping a container lookup to the stack this run brought up.
#
# `bunkerweb.INSTANCE` identifies *a* BunkerWeb instance, not *ours*: any BunkerWeb container
# on the same daemon carries it. Without a scope, a foreign stack (a parallel session running
# another release, say) is a candidate, and `containers[0]` can hand back its logs — the HTTP
# assertions still hit the right instance through the published port, so only the `log:`
# assertions go wrong, silently, in either direction.
#
# The harness never exports COMPOSE_PROJECT_NAME, so `docker compose -f <file>` names each
# project after the directory holding the compose file. Deriving the names from those
# directories keeps this in sync with a rename instead of hardcoding them.
TESTS_DIR = Path(__file__).resolve().parents[1]
HARNESS_COMPOSE_DIRS = (TESTS_DIR / "docker", TESTS_DIR / "misc" / "docker", TESTS_DIR / "linux")
# An example ships its own stack, materialised under /tmp; start.sh reads this marker for the
# compose file path, so its parent directory is that stack's project name.
EXAMPLE_STACK_MARKER = Path(sep, "tmp", "example_stack.txt")
# Swarm deploys with `docker stack deploy <SWARM_STACK>` (tests/scripts/utils.sh), which labels
# tasks with the namespace rather than a compose project.
SWARM_STACK_NAMESPACE = "bw-tests"
COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
SWARM_NAMESPACE_LABEL = "com.docker.stack.namespace"


def normalize_compose_project(name: str) -> str:
    """`docker compose` lowercases the directory name, drops what it cannot use, and trims
    leading separators (compose-go's NormalizeProjectName)."""
    return sub(r"[^a-z0-9_-]", "", name.lower()).lstrip("_-")


def harness_stack_projects() -> Set[str]:
    projects = {normalize_compose_project(directory.name) for directory in HARNESS_COMPOSE_DIRS}
    if EXAMPLE_STACK_MARKER.is_file():
        compose = EXAMPLE_STACK_MARKER.read_text(encoding="utf-8").strip()
        if compose:
            projects.add(normalize_compose_project(Path(compose).parent.name))
    return projects


def is_harness_container(container: Container) -> bool:
    """True when the container belongs to a stack this harness brought up.

    A positive match is required. Every container the harness can select comes from a compose
    stack or from `docker stack deploy`, so "no identifying label" means "not ours" — and the
    All-in-one image is precisely the case that makes the difference: it carries no
    `bunkerweb.INSTANCE`, so the lookup falls through to `bunkerweb.type=all-in-one`, and the
    documented way to deploy it (`docker run --name bunkerweb-aio`, docs/quickstart-guide.md)
    labels it with neither. Accepting the unlabelled would let that foreign container back
    into the candidate list on exactly the arm this scoping exists for.
    """
    labels = container.labels or {}

    project = labels.get(COMPOSE_PROJECT_LABEL)
    if project is not None:
        return project in harness_stack_projects()

    return labels.get(SWARM_NAMESPACE_LABEL) == SWARM_STACK_NAMESPACE


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

    def own(candidates: List[Container]) -> List[Container]:
        return [container for container in candidates if is_harness_container(container)]

    containers = own(docker_client.containers.list(filters=filters)) or (
        own(docker_client.containers.list(filters={"label": "bunkerweb.type=all-in-one"})) if _type != "database" else []
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
