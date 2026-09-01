"""`get_container` must only ever return a container from the stack this run brought up.

`bunkerweb.INSTANCE` marks *a* BunkerWeb instance, not *ours*. On a shared daemon a foreign
stack carries it too, and `containers[0]` then hands back the wrong container: the HTTP
assertions still reach the right instance through the published port, so only the `log:`
assertions break — and they break in both directions. A real occurrence, 2026-09-01:

    harness would read: name=bwverifrc1-bw-1 image=['bunkerity/bunkerweb:1.6.15-rc1']
                        labels={'bunkerweb.INSTANCE': 'bunkerweb', 'bunkerweb.type': 'bunkerweb'}
    foreign rc1 container CRS-banner lines: 64

which turned an All-in-one `general;block` run green off another release's logs.
"""

from importlib.util import module_from_spec, spec_from_file_location
from logging import getLogger
from pathlib import Path
from re import MULTILINE, findall
from sys import modules
from types import ModuleType
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]

docker = ModuleType("docker")
docker.DockerClient = type("DockerClient", (), {})
docker_models = ModuleType("docker.models")
docker_containers = ModuleType("docker.models.containers")
docker_containers.Container = type("Container", (), {})
with patch.dict(modules, {"docker": docker, "docker.models": docker_models, "docker.models.containers": docker_containers}):
    spec = spec_from_file_location("test_harness_docker_scoping", ROOT / "tests" / "utils" / "docker.py")
    docker_utils = module_from_spec(spec)
    spec.loader.exec_module(docker_utils)

LOGGER = getLogger(__name__)

# The projects `docker compose -f tests/<dir>/…yml` produces, i.e. the harness's own stacks.
HARNESS_PROJECT = "docker"
FOREIGN_PROJECT = "bwverifrc1"


class FakeContainer:
    def __init__(self, name: str, labels: dict):
        self.name = name
        self.labels = labels


class FakeContainers:
    """Matches docker-py's label/name filtering closely enough for the lookup under test."""

    def __init__(self, containers):
        self._containers = containers

    def list(self, filters=None):
        filters = filters or {}
        matched = []
        for container in self._containers:
            if "label" in filters:
                key, _, value = filters["label"].partition("=")
                if key not in container.labels or (value and container.labels[key] != value):
                    continue
            if "name" in filters and filters["name"] not in container.name:
                continue
            matched.append(container)
        return matched


def lookup(monkeypatch, containers, _type="bunkerweb"):
    client = type("FakeClient", (), {"containers": FakeContainers(containers)})()
    monkeypatch.setattr(docker_utils, "get_docker_client", lambda: client)
    docker_utils.get_container.cache_clear()
    return docker_utils.get_container(LOGGER, _type)


def aio(project=HARNESS_PROJECT):
    return FakeContainer("bunkerweb-all-in-one", {"bunkerweb.type": "all-in-one", "com.docker.compose.project": project})


def foreign_instance(project=FOREIGN_PROJECT):
    return FakeContainer(
        f"{project}-bw-1",
        {"bunkerweb.INSTANCE": "bunkerweb", "bunkerweb.type": "bunkerweb", "com.docker.compose.project": project},
    )


def own_instance():
    return FakeContainer(
        "bunkerweb",
        {"bunkerweb.INSTANCE": "bunkerweb", "bunkerweb.type": "bunkerweb", "com.docker.compose.project": HARNESS_PROJECT},
    )


def test_foreign_instance_never_shadows_the_all_in_one_container(monkeypatch):
    # The exact 2026-09-01 situation: a foreign release is up, the All-in-one stack is ours.
    selected = lookup(monkeypatch, [foreign_instance(), aio()])
    assert selected.name == "bunkerweb-all-in-one"


def test_foreign_instance_is_not_selected_even_when_it_is_the_only_candidate(monkeypatch):
    # Better to fail loudly than to assert against another stack's logs.
    with pytest.raises(SystemExit):
        lookup(monkeypatch, [foreign_instance()])


def test_our_own_instance_is_still_selected(monkeypatch):
    selected = lookup(monkeypatch, [foreign_instance(), own_instance()])
    assert selected.name == "bunkerweb"


def test_example_stack_project_is_accepted(monkeypatch, tmp_path):
    # An example ships its own stack under /tmp; start.sh finds it through this marker.
    compose = tmp_path / "wordpress" / "docker-compose.yml"
    compose.parent.mkdir(parents=True)
    marker = tmp_path / "example_stack.txt"
    marker.write_text(str(compose), encoding="utf-8")
    monkeypatch.setattr(docker_utils, "EXAMPLE_STACK_MARKER", marker)

    example = FakeContainer("wordpress-bw-1", {"bunkerweb.INSTANCE": "bunkerweb", "com.docker.compose.project": "wordpress"})
    assert lookup(monkeypatch, [foreign_instance(), example]).name == "wordpress-bw-1"


def test_swarm_tasks_are_scoped_by_their_stack_namespace(monkeypatch):
    ours = FakeContainer("bw-tests_bunkerweb.1.abc", {"bunkerweb.INSTANCE": "bunkerweb", "com.docker.stack.namespace": "bw-tests"})
    theirs = FakeContainer("other_bunkerweb.1.def", {"bunkerweb.INSTANCE": "bunkerweb", "com.docker.stack.namespace": "other"})
    assert lookup(monkeypatch, [theirs, ours]).name == "bw-tests_bunkerweb.1.abc"


def test_a_foreign_docker_run_all_in_one_is_not_selected(monkeypatch):
    # The All-in-one image carries no `bunkerweb.INSTANCE`, so this lookup always falls
    # through to the `bunkerweb.type=all-in-one` list -- and the documented way to deploy it
    # (`docker run --name bunkerweb-aio`, docs/quickstart-guide.md) labels it with neither a
    # compose project nor a Swarm namespace. Accepting the unlabelled would put that foreign
    # container straight back into the candidate list, on the very arm this scoping is for.
    foreign_aio = FakeContainer("bunkerweb-aio", {"bunkerweb.type": "all-in-one"})
    assert lookup(monkeypatch, [foreign_aio, aio()]).name == "bunkerweb-all-in-one"

    with pytest.raises(SystemExit):
        lookup(monkeypatch, [foreign_aio])


def test_swarm_namespace_matches_the_one_the_harness_deploys(monkeypatch):
    # `SWARM_STACK_NAMESPACE` is a second copy of `SWARM_STACK` in tests/scripts/utils.sh;
    # a rename there would silently strand the whole Swarm arm.
    utils = (ROOT / "tests" / "scripts" / "utils.sh").read_text(encoding="utf-8")
    declared = findall(r'^SWARM_STACK="([^"]+)"', utils, flags=MULTILINE)
    assert declared == [docker_utils.SWARM_STACK_NAMESPACE], f"utils.sh declares {declared}"


def test_project_names_are_normalised_the_way_compose_normalises_them():
    # compose-go's NormalizeProjectName: lowercase, drop unusable characters, trim leading
    # separators.
    assert docker_utils.normalize_compose_project("Example-Stack") == "example-stack"
    assert docker_utils.normalize_compose_project("_leading") == "leading"
    assert docker_utils.normalize_compose_project("My Stack!") == "mystack"


def test_harness_projects_track_the_shipped_compose_directories():
    # If tests/docker or tests/linux is renamed, the derivation must follow it.
    for directory in docker_utils.HARNESS_COMPOSE_DIRS:
        assert directory.is_dir(), f"{directory} is gone — the derived project name is now wrong"
    assert {"docker", "linux"} <= docker_utils.harness_stack_projects()
