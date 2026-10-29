"""Fixtures shared by the autoconf controller tests.

No Docker, Kubernetes or Swarm API is reached: the controllers are built on a fake database and fake
client objects, and the tests feed them resources (labels, Ingress, Gateway API objects, Services,
ConfigMaps) and assert what they produce. AUTOCONF_SRC points the suite at another copy of
src/autoconf (a mutated one, to watch a test fail).
"""

import logging
import os
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
for _rel in (os.getenv("AUTOCONF_SRC", "src/autoconf"), "src/common/db", "src/common/utils", "src/common/api"):
    _path = _rel if _rel.startswith("/") else str(ROOT / _rel)
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _install_docker_stub():
    """The unit venv does not ship docker-py: stand in with the few names the controllers import."""
    docker_mod = ModuleType("docker")
    models = ModuleType("docker.models")
    containers = ModuleType("docker.models.containers")
    services = ModuleType("docker.models.services")
    errors = ModuleType("docker.errors")

    class DockerException(Exception):
        pass

    class DockerClient:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs

    docker_mod.DockerClient = DockerClient
    containers.Container = type("Container", (), {})
    services.Service = type("Service", (), {})
    errors.DockerException = DockerException
    docker_mod.models, docker_mod.errors = models, errors
    models.containers, models.services = containers, services
    sys.modules.update(
        {
            "docker": docker_mod,
            "docker.models": models,
            "docker.models.containers": containers,
            "docker.models.services": services,
            "docker.errors": errors,
        }
    )


try:
    import docker  # noqa: F401
except ImportError:
    _install_docker_stub()

import Config as config_module  # noqa: E402
import controllers.KubernetesController as kc_module  # noqa: E402
from kubernetes.client import Configuration  # noqa: E402
from _autoconf_helpers import LogCapture, reset_logs  # noqa: E402

# Settings the fake database accepts; the multiple ones also accept a numeric suffix.
VALID_SETTINGS = {
    "SERVER_NAME",
    "USE_REVERSE_PROXY",
    "REVERSE_PROXY_HOST",
    "REVERSE_PROXY_URL",
    "USE_GRPC",
    "GRPC_HOST",
    "GRPC_URL",
    "SERVER_TYPE",
    "USE_CUSTOM_SSL",
    "LISTEN_STREAM_PORT",
    "USE_TCP",
    "USE_UDP",
    "USE_ANTIBOT",
    "LIMIT_REQ_RATE",
    "SECURITY_MODE",
    "AUTO_LETS_ENCRYPT",
    "REVERSE_PROXY_CUSTOM_HOST",
}
MULTIPLE_SETTINGS = {"REVERSE_PROXY_HOST": "reverse-proxy", "REVERSE_PROXY_URL": "reverse-proxy", "GRPC_HOST": "grpc", "GRPC_URL": "grpc"}


class FakeDB:
    """Just the Database surface the controllers use, with scriptable answers."""

    def __init__(self, *_args, **_kwargs):
        self.metadata = {"is_initialized": True}
        self.plugins = [{"id": "general", "settings": {name: {"id": name} for name in VALID_SETTINGS}}]
        self.services = []
        self.db_instances = []
        self.set_metadata_result = ""
        self.readonly = False
        self.database_uri = ""
        self.set_metadata_calls = []
        self.saved_configs = []
        self.saved_custom_configs = []
        self.saved_instances = []
        self.checked = []
        self.save_kwargs = []
        self.write_error = None
        self.retries = []
        self.retry_outcomes = []
        self.database_uri_readonly = ""

    def test_write(self):
        if self.write_error:
            raise self.write_error
        return None

    def retry_connection(self, *args, **kwargs):
        self.retries.append(kwargs)
        outcome = self.retry_outcomes.pop(0) if self.retry_outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome

    def update_instances(self, instances, *_args, **_kwargs):
        self.saved_instances.append(instances)
        return ""

    def save_config(self, config, *_args, **kwargs):
        self.saved_configs.append(config)
        self.save_kwargs.append(kwargs)
        return set()

    def save_custom_configs(self, configs, *_args, **_kwargs):
        self.saved_custom_configs.append(configs)
        return ""

    def checked_changes(self, changes, **_kwargs):
        self.checked.append(changes)
        return ""

    def get_metadata(self):
        return self.metadata

    def get_plugins(self):
        return self.plugins

    def get_services(self):
        return self.services

    def get_instances(self, autoconf=False):
        return self.db_instances

    def set_metadata(self, data):
        self.set_metadata_calls.append(data)
        return self.set_metadata_result

    def is_valid_setting(self, setting, value=None, multisite=False, extra_services=None, **_kwargs):
        name = setting
        for host in extra_services or []:
            if name.startswith(f"{host}_"):
                name = name.removeprefix(f"{host}_")
                break
        match = re.fullmatch(r"(.+)_(\d+)", name)
        if name in VALID_SETTINGS or (match and match.group(1) in MULTIPLE_SETTINGS):
            return True, ""
        return False, f"setting {setting} not found"


@pytest.fixture(autouse=True)
def _restore_loggers():
    """Clear controller log records between tests."""
    yield
    reset_logs()


@pytest.fixture
def fake_db(monkeypatch):
    """Every Config() built while this fixture is active gets the same FakeDB."""
    db = FakeDB()
    monkeypatch.setattr(config_module, "Database", lambda *_a, **_k: db)
    return db


@pytest.fixture
def clean_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("KUBERNETES_", "DOCKER_", "SWARM_", "AUTOCONF_", "BUNKERWEB_", "USE_KUBERNETES")) or name == "NAMESPACES":
            monkeypatch.delenv(name)
    return monkeypatch


@pytest.fixture
def k8s_env(clean_env, fake_db):
    """A KubernetesController can be built: in-cluster config loading is a no-op and the shared Configuration is restored."""
    clean_env.setattr(Configuration, "_default", None)
    clean_env.setattr(kc_module.config, "load_incluster_config", lambda: Configuration.set_default(Configuration()))
    return clean_env


@pytest.fixture
def api_exception():
    from kubernetes.client.exceptions import ApiException

    def build(status, reason=""):
        return ApiException(status=status, reason=reason)

    return build


def fake_corev1():
    return MagicMock(name="corev1")


@pytest.fixture
def gateway_build(k8s_env, monkeypatch):
    """GatewayController factory over FakeCustomObjects: build(table, **env); the controller keeps the fake as `.api`."""
    import controllers.GatewayController as gateway_module
    from gateway_fakes import FakeCustomObjects, crds

    holder = SimpleNamespace(api=None)
    monkeypatch.setattr(gateway_module.client, "CustomObjectsApi", lambda api_client=None: holder.api)
    named = logging.getLogger("KUBERNETES-CONTROLLER")
    captures = []
    used = set()

    def make(table=None, **env):
        for name in used:
            k8s_env.delenv(name, raising=False)
        used.clear()
        used.update(env)
        for name in env:
            k8s_env.setenv(name, env[name])
        holder.api = FakeCustomObjects(table if table is not None else crds())
        init_log = LogCapture()
        named.addHandler(init_log)
        captures.append(init_log)
        ctrl = gateway_module.GatewayController()
        ctrl._corev1 = MagicMock(name="corev1")
        ctrl.api = holder.api
        ctrl.init_log = init_log
        return ctrl

    yield make
    for capture in captures:
        named.removeHandler(capture)
