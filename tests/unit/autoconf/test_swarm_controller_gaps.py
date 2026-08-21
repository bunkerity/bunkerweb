"""The Swarm controller's gaps against the Docker one, and the loop the two used to duplicate.

Every behaviour here is invisible from the outside when it is wrong, which is why none of it was
caught before: a config leaking across a namespace partition still applies cleanly, a replicated
`bunkerweb.INSTANCE` service registers instances that simply never answer, an `INSTANCE=yes`
setting is only a warning line, `CUSTOM_CONF_*` labels do nothing at all with no diagnostic, and
an unbounded tracking list is a leak nobody reads. Each test below is paired with the mutant it
kills -- see `.cache/results-2026-08-21/swarm-report.md` for the table.

No test here is skipped: nothing in this file needs Docker, a daemon or a Swarm cluster.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def _stub_docker():
    """`.venv-unit` deliberately does not carry autoconf's runtime deps, so `docker` is stubbed.

    Nothing under test dials a daemon: the controller is driven with hand-built service and
    config objects shaped like the ones docker-py returns.
    """
    docker = ModuleType("docker")
    docker.DockerClient = Mock()
    services_mod = ModuleType("docker.models.services")
    services_mod.Service = type("Service", (), {})
    models = ModuleType("docker.models")
    models.services = services_mod
    errors = ModuleType("docker.errors")

    class DockerException(Exception):
        pass

    errors.DockerException = DockerException
    docker.models = models
    docker.errors = errors
    return {
        "docker": docker,
        "docker.models": models,
        "docker.models.services": services_mod,
        "docker.errors": errors,
    }, DockerException


def _load_swarm_controller():
    stubs, DockerException = _stub_docker()
    controllers = ModuleType("controllers")
    controller_mod = ModuleType("controllers.Controller")
    controller_mod.Controller = type("Controller", (), {})
    controllers.Controller = controller_mod
    stubs |= {"controllers": controllers, "controllers.Controller": controller_mod}

    with patch.dict(sys.modules, stubs):
        path = ROOT / "src" / "autoconf" / "controllers" / "SwarmController.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_swarm_controller", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


SWARM = _load_swarm_controller()
SwarmController = SWARM.SwarmController


def _bare_controller(namespaces=None):
    """A controller without __init__ -- __init__ builds a real DockerClient."""
    controller = object.__new__(SwarmController)
    controller._logger = Mock()
    controller._namespaces = namespaces
    controller._supported_config_types = ["server-http", "modsec"]
    controller._services = []
    controller._SwarmController__swarm_instances = []
    controller._SwarmController__swarm_services = []
    controller._SwarmController__swarm_configs = []
    controller._SwarmController__warned_custom_conf_services = set()
    controller._SwarmController__warned_non_global_instances = set()
    controller._SwarmController__ignored_labels_exact = set()
    controller._SwarmController__ignored_label_suffixes = set()
    return controller


def _config_obj(name, labels, data=b"# a config"):
    """A docker-py Config double. `Spec.Data` is base64 on the wire, as the controller expects."""
    from base64 import b64encode

    obj = Mock()
    obj.name = name
    obj.id = f"cfg-{name}"
    obj.attrs = {"Spec": {"Labels": labels, "Data": b64encode(data).decode()}}
    return obj


def _service_obj(name, labels, *, global_mode=True, env=None):
    obj = Mock()
    obj.name = name
    obj.id = f"svc-{name}"
    obj.attrs = {
        "Spec": {
            "Labels": labels,
            "Mode": {"Global": {}} if global_mode else {"Replicated": {"Replicas": 3}},
            "TaskTemplate": {"ContainerSpec": {"Env": env or []}},
        }
    }
    return obj


# --------------------------------------------------------------------------- NAMESPACES on configs


def _controller_with_configs(configs, namespaces):
    controller = _bare_controller(namespaces=namespaces)
    client = Mock()
    client.configs.list.return_value = configs
    controller._SwarmController__client = client
    return controller


def test_a_global_config_labelled_for_another_namespace_is_ignored():
    """The gap: NAMESPACES filtered the event path and service discovery, never this one.

    A *global* custom config (no CONFIG_SITE) labelled for another namespace was collected by
    every autoconf partition on the daemon. Mutant: delete the namespace check in `get_configs`.
    """
    mine = _config_obj("mine.conf", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.NAMESPACE": "mine"})
    theirs = _config_obj("theirs.conf", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.NAMESPACE": "theirs"})
    controller = _controller_with_configs([mine, theirs], namespaces=["mine"])

    configs = controller.get_configs()

    collected = set(configs["server-http"])
    assert "mine.conf" in collected, "the allowed-namespace config must still be collected"
    assert "theirs.conf" not in collected, "a global config from another namespace leaked across the partition"


def test_a_global_config_with_no_namespace_label_is_ignored_when_namespaces_are_set():
    """An unlabelled config is not 'everyone's' -- the Docker controller drops it too."""
    unlabelled = _config_obj("loose.conf", {"bunkerweb.CONFIG_TYPE": "server-http"})
    controller = _controller_with_configs([unlabelled], namespaces=["mine"])

    assert "loose.conf" not in controller.get_configs()["server-http"]


def test_every_config_is_collected_when_no_namespace_is_configured():
    """Floor (RULE 13): without NAMESPACES nothing is filtered, so the tests above cannot pass
    by the controller simply collecting nothing."""
    configs = [
        _config_obj("a.conf", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.NAMESPACE": "mine"}),
        _config_obj("b.conf", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.NAMESPACE": "theirs"}),
        _config_obj("c.conf", {"bunkerweb.CONFIG_TYPE": "server-http"}),
    ]
    controller = _controller_with_configs(configs, namespaces=None)

    collected = controller.get_configs()["server-http"]
    assert len(collected) >= 3, f"expected every config, got {sorted(collected)}"


# ------------------------------------------------------------------------------- R6 mode:global


def test_a_replicated_instance_service_is_refused():
    """R6. `_to_instances` builds the hostname `<service>.<NodeID>.<TaskID>`, which is only the
    task's real name under a *global* service. A replicated one resolves as
    `<service>.<slot>.<TaskID>`, so every instance registered from it is unreachable and the
    stack never converges -- with no error anywhere. Mutant: remove the guard."""
    service = _service_obj("bunkerweb", {"bunkerweb.INSTANCE": "yes"}, global_mode=False)
    service.tasks.return_value = [{"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}}]
    controller = _bare_controller()

    assert controller._to_instances(service) == []
    assert controller._logger.error.called, "refusing the service silently is the defect, not the fix"
    message = controller._logger.error.call_args[0][0]
    assert "global" in message.lower(), f"the operator must be told what to change, got: {message!r}"


def test_the_refusal_is_logged_once_per_service_not_once_per_pass():
    """The guard runs on EVERY reconcile pass, and a burst of Swarm events reconciles often. An
    operator cannot act on this from the log -- the service has to be redeployed -- so repeating it
    every few seconds only buries the other diagnostics. Refusing must stay unconditional; only the
    logging is deduplicated. Mutant: drop the `__warned_non_global_instances` gate (keep the log
    call) and the second-pass assertion goes red while the `== []` assertions stay green."""
    service = _service_obj("bunkerweb", {"bunkerweb.INSTANCE": "yes"}, global_mode=False)
    service.tasks.return_value = [{"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}}]
    controller = _bare_controller()

    for _ in range(5):
        assert controller._to_instances(service) == [], "the refusal itself must NOT be deduplicated"
    assert controller._logger.error.call_count == 1, f"expected one error for five passes over the same service, got {controller._logger.error.call_count}"

    # A DIFFERENT broken service still gets its own error: the dedup is per service id, not global.
    other = _service_obj("bunkerweb-2", {"bunkerweb.INSTANCE": "yes"}, global_mode=False)
    other.id = "svc-other"
    other.tasks.return_value = []
    assert controller._to_instances(other) == []
    assert controller._logger.error.call_count == 2, "a second broken service must not be silenced by the first"


def test_a_global_instance_service_is_accepted_and_keeps_task_identity():
    """RULE 19: the guard must reject the broken shape, not everything. R6 also settled that task
    identity (`service.NodeID.TaskID`) is KEPT -- no model change -- so assert the hostname shape."""
    service = _service_obj("bunkerweb", {"bunkerweb.INSTANCE": "yes"}, global_mode=True, env=["API_TOKEN=x"])
    service.tasks.return_value = [{"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}}]
    controller = _bare_controller()

    instances = controller._to_instances(service)

    assert len(instances) == 1
    assert instances[0]["hostname"] == "bunkerweb.n1.t1"
    assert instances[0]["health"] is True
    assert instances[0]["env"] == {"API_TOKEN": "x"}


# ------------------------------------------------------------------- metadata labels in _to_services


def test_metadata_labels_are_not_emitted_as_settings():
    """The BunkerWeb image bakes `bunkerweb.INSTANCE`, so a service carrying both SERVER_NAME and
    INSTANCE emitted `INSTANCE=yes` as a setting -- a validation warning every single cycle.
    Mutant: drop the __METADATA_LABELS check."""
    service = _service_obj(
        "app",
        {"bunkerweb.SERVER_NAME": "www.example.com", "bunkerweb.INSTANCE": "yes", "bunkerweb.type": "all", "bunkerweb.USE_ANTIBOT": "captcha"},
    )
    controller = _bare_controller()

    settings = controller._to_services(service)[0]

    assert "INSTANCE" not in settings
    assert "type" not in settings
    assert settings["SERVER_NAME"] == "www.example.com"
    assert settings["USE_ANTIBOT"] == "captcha", "stripping metadata must not strip real settings"


# ----------------------------------------------------------------------------- CUSTOM_CONF_* labels


def test_custom_conf_labels_are_reported_rather_than_silently_ignored():
    """`Config.py` ignores the CUSTOM_CONF_ prefix for every controller and only DockerController
    reads it back off the container, so under Swarm these labels did nothing AND said nothing.
    Mutant: remove the warning (keep the `continue`) -- the label is still dropped, so only the
    diagnostic distinguishes fix from defect."""
    service = _service_obj(
        "app",
        {"bunkerweb.SERVER_NAME": "www.example.com", "bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello": "return 200;"},
    )
    controller = _bare_controller()

    settings = controller._to_services(service)[0]

    assert not any(key.startswith("CUSTOM_CONF_") for key in settings), "the label is not a setting"
    assert controller._logger.warning.called, "an inert label must be reported, not swallowed"
    message = controller._logger.warning.call_args[0][0]
    assert "CUSTOM_CONF" in message and "config" in message.lower(), f"the warning must name the label and the way out, got: {message!r}"


def test_the_custom_conf_warning_is_not_repeated_for_the_same_service():
    """The reconcile runs on every event; a per-pass warning would bury the controller log."""
    service = _service_obj("app", {"bunkerweb.SERVER_NAME": "www.example.com", "bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello": "return 200;"})
    controller = _bare_controller()

    for _ in range(5):
        controller._to_services(service)

    assert controller._logger.warning.call_count == 1, f"warned {controller._logger.warning.call_count} times for one service"


def test_a_service_without_custom_conf_labels_is_not_warned_about():
    """RULE 19 floor: the warning must fire on the broken shape only."""
    service = _service_obj("app", {"bunkerweb.SERVER_NAME": "www.example.com"})
    controller = _bare_controller()

    controller._to_services(service)

    assert not controller._logger.warning.called


# --------------------------------------------------------------------------- tracking-list growth


def _controller_listing(services, namespaces=None):
    controller = _bare_controller(namespaces=namespaces)
    client = Mock()
    client.services.list.return_value = services
    controller._SwarmController__client = client
    return controller


def test_the_instance_tracking_list_does_not_grow_across_passes():
    """`_to_instances` appends one id per service per pass and only `__swarm_configs` was ever
    reset. Mutant: remove the reset in `_get_controller_instances`."""
    service = _service_obj("bunkerweb", {"bunkerweb.INSTANCE": "yes"})
    service.tasks.return_value = [{"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}}]
    controller = _controller_listing([service])

    for _ in range(4):
        for found in controller._get_controller_instances():
            controller._to_instances(found)

    tracked = controller._SwarmController__swarm_instances
    assert tracked == ["svc-bunkerweb"], f"one service tracked four times: {tracked}"


def test_a_deleted_service_stops_matching_the_event_filter():
    """RULE 14a -- the operator-visible consequence of the leak above, tested directly.

    `__process_event` short-circuits to True when the actor id is in the tracking list. With the
    list never reset, a service that has since been *deleted* kept forcing a reconcile on every
    unrelated event bearing its id.
    """
    service = _service_obj("app", {"bunkerweb.SERVER_NAME": "www.example.com"})
    controller = _controller_listing([service])
    controller._first_start = False

    for found in controller._get_controller_services():
        controller._to_services(found)
    assert controller._SwarmController__swarm_services == ["svc-app"]

    # the service is deleted: the next pass lists nothing, and the daemon no longer knows the id
    controller._SwarmController__client.services.list.return_value = []
    controller._SwarmController__client.services.get.side_effect = KeyError("no such service")
    controller._get_controller_services()

    event = {"Type": "service", "Action": "remove", "Actor": {"ID": "svc-app"}}
    assert controller._SwarmController__process_event(event) is False, "a deleted service still forced a reconcile"
