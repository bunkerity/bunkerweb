"""Instance discovery changes only publish when configuration push targets change."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from test_docker_controller_labels import container
from test_kubernetes_controller_core import K8s, pod
from test_swarm_controller_labels import service

import controllers.DockerController as docker_module
import controllers.SwarmController as swarm_module


@pytest.fixture(params=["docker", "swarm", "kubernetes"])
def discovery(request, k8s_env, monkeypatch):
    if request.param == "docker":
        monkeypatch.setattr(docker_module, "DockerClient", lambda **_kwargs: MagicMock())
        ctrl = docker_module.DockerController("unix:///fake.sock")

        def snapshot(healthy):
            return ctrl._to_instances(container("bw", {}, health="healthy" if healthy else "unhealthy", env=["API_HTTP_PORT=5000"]))

    elif request.param == "swarm":
        monkeypatch.setattr(swarm_module, "DockerClient", lambda **_kwargs: MagicMock())
        ctrl = swarm_module.SwarmController("unix:///fake.sock")

        def snapshot(healthy):
            tasks = [{"ID": "task", "NodeID": "node", "DesiredState": "running", "Status": {"State": "running" if healthy else "starting"}}]
            return ctrl._to_instances(service("bw", {}, env=["API_HTTP_PORT=5000"], tasks=tasks))

    else:
        ctrl = K8s()

        def snapshot(healthy):
            return ctrl._to_instances(pod(running=healthy))

    return ctrl, snapshot


def baseline(discovery, fake_db, healthy=True):
    ctrl, snapshot = discovery
    instances = snapshot(healthy)
    services = [{"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "captcha"}]
    assert ctrl.apply(instances, services, first=True)
    assert fake_db.saved_instances == [instances]
    fake_db.checked.clear()
    fake_db.saved_instances.clear()
    fake_db.saved_configs.clear()
    return ctrl, instances, services


@pytest.mark.parametrize("healthy", [False, True], ids=["recovering", "unhealthy"])
def test_health_only_changes_do_not_signal_the_scheduler(discovery, fake_db, healthy):
    ctrl, instances, services = baseline(discovery, fake_db, healthy=healthy)
    changed = discovery[1](not healthy)
    assert instances[0]["health"] is healthy
    assert changed[0]["health"] is not healthy

    assert ctrl.update_needed(changed, services) is False
    assert ctrl.apply(changed, services)
    assert fake_db.checked == []
    assert fake_db.saved_instances == []
    assert fake_db.saved_configs == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "renamed"),
        ("type", "static"),
        ("method", "manual"),
        ("status", "down"),
        ("creation_date", "later"),
        ("last_seen", "later"),
        ("port", 9000),
        ("listen_https", True),
        ("https_port", 9443),
        ("server_name", "unused.example"),
        ("env", {"API_HTTP_PORT": "5000", "SECURITY_MODE": "detect"}),
    ],
)
def test_fields_not_used_for_push_targets_do_not_publish(discovery, fake_db, field, value):
    ctrl, instances, services = baseline(discovery, fake_db)
    changed = [dict(instances[0], **{field: value})]

    assert ctrl.update_needed(changed, services) is False
    assert ctrl.apply(changed, services)
    assert fake_db.checked == []
    assert fake_db.saved_instances == []


@pytest.mark.parametrize("change", ["add", "remove", "hostname", "API_HTTP_PORT", "API_LISTEN_HTTPS", "API_HTTPS_PORT", "API_SERVER_NAME"])
def test_real_target_changes_publish_and_converge(discovery, fake_db, change):
    ctrl, instances, services = baseline(discovery, fake_db)
    changed = deepcopy(instances)
    if change == "add":
        changed.append(dict(instances[0], hostname="other"))
    elif change == "remove":
        changed = []
    elif change == "hostname":
        changed[0]["hostname"] = "other"
    else:
        changed[0]["env"][change] = {
            "API_HTTP_PORT": "5001",
            "API_LISTEN_HTTPS": "yes",
            "API_HTTPS_PORT": "5444",
            "API_SERVER_NAME": "other.example",
        }[change]

    assert ctrl.update_needed(changed, services) is True
    assert ctrl.apply(changed, services)
    assert fake_db.checked == [["instances"]]
    assert fake_db.saved_instances == [changed]
    assert ctrl.update_needed(changed, services) is False
    assert ctrl.apply(changed, services)
    assert fake_db.checked == [["instances"]]


def test_discovery_order_does_not_change_targets(discovery, fake_db):
    ctrl, instances, services = baseline(discovery, fake_db)
    instances = instances + [dict(instances[0], hostname="other")]
    assert ctrl.apply(instances, services)
    fake_db.checked.clear()
    fake_db.saved_instances.clear()

    assert ctrl.update_needed(instances[::-1], services) is False
    assert ctrl.apply(instances[::-1], services)
    assert fake_db.checked == []
    assert fake_db.saved_instances == []


def test_default_api_settings_do_not_change_targets(discovery, fake_db):
    ctrl, instances, services = baseline(discovery, fake_db)
    changed = [dict(instances[0], env={"API_HTTP_PORT": "5000", "API_LISTEN_HTTPS": "no", "API_HTTPS_PORT": "5443", "API_SERVER_NAME": "bwapi"})]

    assert ctrl.update_needed(changed, services) is False
    assert ctrl.apply(changed, services)
    assert fake_db.checked == []


def test_service_change_with_health_change_only_signals_service_configuration(discovery, fake_db):
    ctrl, _instances, services = baseline(discovery, fake_db)
    changed = discovery[1](False)
    services = [dict(services[0], USE_ANTIBOT="no")]

    assert ctrl.update_needed(changed, services) is True
    assert ctrl.apply(changed, services)
    assert fake_db.checked == [["services", "config"]]
    assert fake_db.saved_instances == []
    assert fake_db.saved_configs[0]["app.example.com_USE_ANTIBOT"] == "no"
    assert ctrl.update_needed(changed, services) is False


def test_forced_revalidation_with_health_change_preserves_service_validation(discovery, fake_db):
    ctrl, _instances, services = baseline(discovery, fake_db)
    fake_db.is_valid_setting = lambda *_args, **_kwargs: (False, "setting no longer supported")

    assert ctrl.apply(discovery[1](False), services, force=True)
    assert fake_db.checked == [["config"]]
    assert fake_db.saved_instances == []
    assert fake_db.saved_configs == [{"SERVER_NAME": "app.example.com", "MULTISITE": "yes"}]
