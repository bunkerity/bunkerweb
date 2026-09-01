"""`get_container`'s cache must not keep serving a handle after `restart_stack()` recreates it.

`tests/scripts/utils.sh:restart_stack` runs `docker compose down` then brings the stack back up
(or, for an example stack, the same down/up pair) between actions -- the new container gets the
same name but a different id. The `@cache`d `get_container` (wave-10 L1, `get_container` scoped to
its own compose project) would then hand back the pre-restart `Container` object.

This was latent, not live, in every run to date: `tests/scripts/run.sh` invokes a fresh
`python3 tests/<type>.py` per action (`:186-241`), so the process-lifetime cache never survives
past the restart that would have staled it -- wave-10 L1's own report noted it did not bite in
any run. It is still a real hazard for the next process shape that keeps `get_container` alive
across a `restart_stack()` call, which is exactly what this residual note asked this lane to close.

`get_container` now verifies a cache hit with `container.reload()` (a single by-id inspect, not a
`containers.list()` scan) before returning it, and re-resolves on `docker.errors.NotFound` instead
of handing back a dead handle -- see `tests/utils/docker.py`.
"""

from importlib.util import module_from_spec, spec_from_file_location
from logging import getLogger
from pathlib import Path
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
docker_errors = ModuleType("docker.errors")


class NotFound(Exception):
    pass


docker_errors.NotFound = NotFound
with patch.dict(
    modules,
    {"docker": docker, "docker.models": docker_models, "docker.models.containers": docker_containers, "docker.errors": docker_errors},
):
    spec = spec_from_file_location("test_container_cache_staleness_docker_utils", ROOT / "tests" / "utils" / "docker.py")
    docker_utils = module_from_spec(spec)
    spec.loader.exec_module(docker_utils)

LOGGER = getLogger(__name__)


class FakeContainer:
    def __init__(self, name: str, labels: dict, removed: bool = False):
        self.name = name
        self.labels = labels
        self.removed = removed
        self.reload_calls = 0

    def reload(self):
        self.reload_calls += 1
        if self.removed:
            raise NotFound(f"container {self.name} is gone")


class FakeContainers:
    def __init__(self, containers):
        self._containers = containers
        self.list_calls = 0

    def list(self, filters=None):
        self.list_calls += 1
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


def own_instance(removed=False):
    return FakeContainer(
        "bunkerweb",
        {"bunkerweb.INSTANCE": "bunkerweb", "bunkerweb.type": "bunkerweb", "com.docker.compose.project": "docker"},
        removed=removed,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    docker_utils._CONTAINER_CACHE.clear()
    yield
    docker_utils._CONTAINER_CACHE.clear()


def test_a_healthy_cache_hit_is_reused_without_relisting(monkeypatch):
    first = own_instance()
    fake_containers = FakeContainers([first])
    client = type("FakeClient", (), {"containers": fake_containers})()
    monkeypatch.setattr(docker_utils, "get_docker_client", lambda: client)

    selected_1 = docker_utils.get_container(LOGGER, "bunkerweb")
    selected_2 = docker_utils.get_container(LOGGER, "bunkerweb")

    assert selected_1 is first
    assert selected_2 is first
    assert fake_containers.list_calls == 1, "a second call must not re-scan the daemon on a live cache hit"
    assert first.reload_calls == 1, "only the second call verifies liveness; the first call has nothing cached yet"


def test_a_recreated_container_is_re_resolved_instead_of_returning_the_removed_handle(monkeypatch):
    pre_restart = own_instance()
    fake_containers = FakeContainers([pre_restart])
    client = type("FakeClient", (), {"containers": fake_containers})()
    monkeypatch.setattr(docker_utils, "get_docker_client", lambda: client)

    selected_1 = docker_utils.get_container(LOGGER, "bunkerweb")
    assert selected_1 is pre_restart

    # restart_stack(): down removes the old container, up creates a new one under the same name.
    pre_restart.removed = True
    post_restart = own_instance()
    fake_containers._containers = [post_restart]

    selected_2 = docker_utils.get_container(LOGGER, "bunkerweb")

    assert selected_2 is post_restart
    assert selected_2 is not pre_restart
    assert fake_containers.list_calls == 2, "a stale hit must trigger exactly one re-resolve, not a silent failure"


def test_a_container_that_never_comes_back_still_exits(monkeypatch):
    pre_restart = own_instance()
    fake_containers = FakeContainers([pre_restart])
    client = type("FakeClient", (), {"containers": fake_containers})()
    monkeypatch.setattr(docker_utils, "get_docker_client", lambda: client)

    docker_utils.get_container(LOGGER, "bunkerweb")

    pre_restart.removed = True
    fake_containers._containers = []

    with pytest.raises(SystemExit):
        docker_utils.get_container(LOGGER, "bunkerweb")
