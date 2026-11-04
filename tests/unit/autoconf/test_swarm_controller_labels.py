"""SwarmController: what Swarm service labels and Swarm configs turn into, and which of them are in scope."""

import logging
from base64 import b64encode
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import LogCapture, attach_log

import controllers.SwarmController as module
from controllers.SwarmController import SwarmController
from docker.errors import DockerException


class Stop(BaseException):
    """Ends the endless event loop: raised out of a patched sleep()."""


CLIENT = {}


def service(name, labels, env=None, tasks=None, sid=None):
    spec = {"Labels": labels, "TaskTemplate": {"ContainerSpec": {"Env": env}}}
    return SimpleNamespace(id=sid or f"id-{name}", name=name, attrs={"Spec": spec}, tasks=lambda: tasks or [])


def swarm_config(name, labels, data=b"conf", cid=None):
    attrs = {"Spec": {"Labels": labels, "Data": b64encode(data).decode()}}
    return SimpleNamespace(id=cid or f"id-{name}", name=name, attrs=attrs)


@pytest.fixture
def swarm_env(clean_env, fake_db):
    clean_env.setenv("AUTOCONF_SETTINGS_RECHECK_INTERVAL", "0")
    clean_env.setattr(module, "DockerClient", lambda base_url=None: CLIENT["client"])
    return clean_env


def build(services=None, configs=None):
    """services: {label filter: [service]}; configs: [swarm config]."""
    client = CLIENT["client"] = MagicMock(name="swarm-client")
    client.services.list.side_effect = lambda filters=None: list((services or {}).get((filters or {}).get("label"), []))
    client.configs.list.side_effect = lambda filters=None: list(configs or [])
    ctrl = SwarmController("unix:///fake.sock")
    ctrl.client = client
    return ctrl


def test_deprecation_is_announced(swarm_env):
    capture = LogCapture()
    logger = logging.getLogger("SWARM-CONTROLLER")
    logger.addHandler(capture)
    try:
        build()
    finally:
        logger.removeHandler(capture)

    assert capture.has("Swarm integration is deprecated", logging.WARNING)


def test_service_labels_lose_the_prefix_and_foreign_labels_are_dropped(swarm_env):
    web = service("web", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.USE_ANTIBOT": "captcha", "com.docker.stack.namespace": "x"})
    ctrl = build({"bunkerweb.SERVER_NAME": [web]})

    assert ctrl.get_services() == [{"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "captcha"}]


def test_namespace_scope_ignores_services_of_other_namespaces(swarm_env):
    """QAR Q8"""
    swarm_env.setenv("NAMESPACES", "prod")
    mine = service("mine", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.NAMESPACE": "prod"})
    other = service("other", {"bunkerweb.SERVER_NAME": "b.example.com", "bunkerweb.NAMESPACE": "dev"})
    ctrl = build({"bunkerweb.SERVER_NAME": [mine, other]})

    assert [s["SERVER_NAME"] for s in ctrl.get_services()] == ["a.example.com"]


@pytest.mark.parametrize("token", ["USE_ANTIBOT", "bunkerweb.USE_ANTIBOT"])
def test_ignored_label_hides_the_service(swarm_env, token):
    swarm_env.setenv("SWARM_IGNORE_LABELS", token)
    skipped = service("skipped", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.USE_ANTIBOT": "yes"})
    kept = service("kept", {"bunkerweb.SERVER_NAME": "b.example.com"})
    ctrl = build({"bunkerweb.SERVER_NAME": [skipped, kept]})

    assert [s["SERVER_NAME"] for s in ctrl.get_services()] == ["b.example.com"]


def test_ignored_label_is_not_copied_into_a_service(swarm_env):
    swarm_env.setenv("SWARM_IGNORE_LABELS", "bunkerweb.USE_ANTIBOT")
    ctrl = build()
    svc = service("svc", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.USE_ANTIBOT": "yes"})

    assert ctrl._to_services(svc) == [{"SERVER_NAME": "a.example.com"}]


def test_service_with_non_mapping_labels_is_skipped_with_a_warning(swarm_env):
    odd = service("odd", "not-a-mapping")
    ctrl = build({"bunkerweb.SERVER_NAME": [odd]})
    log = attach_log(ctrl)

    assert ctrl.get_services() == []
    assert log.has("Unexpected label format for service id-odd", logging.WARNING)


def test_service_without_attrs_is_reported_not_fatal(swarm_env):
    broken = SimpleNamespace(id="broken", name="broken")
    ctrl = build({"bunkerweb.SERVER_NAME": [broken]})
    log = attach_log(ctrl)

    assert ctrl._get_controller_services() == []
    assert log.has("Service broken missing expected attributes", logging.WARNING)


def test_docker_error_while_listing_is_logged_and_raised(swarm_env):
    ctrl = build()
    ctrl.client.services.list.side_effect = DockerException("no manager")
    log = attach_log(ctrl)

    with pytest.raises(DockerException):
        ctrl.get_instances()
    assert log.has("Failed to retrieve services with label 'bunkerweb.INSTANCE': no manager", logging.ERROR)


def test_only_running_tasks_become_instances(swarm_env):
    tasks = [
        {"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}},
        {"ID": "t2", "NodeID": "n2", "DesiredState": "running", "Status": {"State": "starting"}},
        {"ID": "t3", "NodeID": "n3", "DesiredState": "shutdown", "Status": {"State": "running"}},
    ]
    bw = service("bw", {"bunkerweb.INSTANCE": "yes"}, env=["API_HTTP_PORT=5000", "BROKEN", "X=a=b"], tasks=tasks)
    ctrl = build({"bunkerweb.INSTANCE": [bw]})

    instances = ctrl.get_instances()

    env = {"API_HTTP_PORT": "5000", "X": "a=b"}
    assert instances == [
        {"name": "t1", "hostname": "bw.n1.t1", "type": "container", "health": True, "env": env},
        {"name": "t2", "hostname": "bw.n2.t2", "type": "container", "health": False, "env": env},
    ]


def test_instance_without_env_has_an_empty_env(swarm_env):
    bw = service("bw", {}, env=None, tasks=[{"ID": "t", "NodeID": "n", "DesiredState": "running", "Status": {"State": "running"}}])
    ctrl = build()

    assert ctrl._to_instances(bw)[0]["env"] == {}


def test_configs_are_decoded_and_filed_by_type_and_site(swarm_env, fake_db):
    fake_db.services = [{"id": "app.example.com"}]
    cfgs = [
        swarm_config("hello", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.CONFIG_SITE": "app.example.com"}, b"location / {}"),
        swarm_config("global", {"bunkerweb.CONFIG_TYPE": "http"}, b"map $a $b {}"),
    ]
    ctrl = build(configs=cfgs)

    configs = ctrl.get_configs()

    assert configs["server-http"] == {"app.example.com/hello": b"location / {}"}
    assert configs["http"] == {"global": b"map $a $b {}"}
    assert set(configs) == set(ctrl._supported_config_types)


def test_config_edge_cases_are_skipped_with_the_right_warning(swarm_env, fake_db):
    swarm_env.setenv("SWARM_IGNORE_LABELS", "SKIP")
    cfgs = [
        SimpleNamespace(id="empty", name="", attrs={}),
        SimpleNamespace(id="nolabels", name="nolabels", attrs={"Spec": {"Labels": {}, "Data": "eA=="}}),
        SimpleNamespace(id="nodata", name="nodata", attrs={"Spec": {"Labels": {"bunkerweb.CONFIG_TYPE": "http"}, "Data": {}}}),
        swarm_config("ignored", {"bunkerweb.CONFIG_TYPE": "http", "bunkerweb.SKIP": "1"}),
        swarm_config("badtype", {"bunkerweb.CONFIG_TYPE": "nonsense"}),
        swarm_config("ghost", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.CONFIG_SITE": "ghost.example.com"}),
    ]
    ctrl = build(configs=cfgs)
    log = attach_log(ctrl)

    configs = ctrl.get_configs()

    assert all(not files for files in configs.values())
    assert log.has("Skipping Swarm config ignored because of ignored labels", logging.INFO)
    assert log.has("Ignoring unsupported CONFIG_TYPE nonsense for Config badtype", logging.WARNING)
    assert log.has("Ignoring config ghost because ghost.example.com doesn't exist", logging.WARNING)


# --- event filtering --------------------------------------------------------------------------------


def swarm_event(kind="service", actor="svc1"):
    return {"Type": kind, "Actor": {"ID": actor}}


@pytest.fixture
def judge(swarm_env):
    def make(services=None, configs=None, **env):
        for name, value in env.items():
            swarm_env.setenv(name, value)
        ctrl = build()
        ctrl._first_start = False
        ctrl.client.services.get.side_effect = lambda sid: (services or {})[sid]
        ctrl.client.configs.get.side_effect = lambda cid: (configs or {})[cid]
        return ctrl, ctrl._SwarmController__process_event

    return make


def test_first_event_is_always_processed(swarm_env):
    ctrl = build()

    assert ctrl._SwarmController__process_event({}) is True


@pytest.mark.parametrize("bad", [{}, {"Type": "service"}, {"Type": "service", "Actor": {}}, {"Type": "node", "Actor": {"ID": "x"}}])
def test_malformed_or_unrelated_events_are_dropped(judge, bad):
    _, process = judge()

    assert process(bad) is False


def test_event_of_a_known_service_is_processed_without_a_lookup(judge):
    ctrl, process = judge()
    ctrl._to_services(service("web", {"bunkerweb.SERVER_NAME": "a.example.com"}, sid="known"))

    assert process(swarm_event(actor="known")) is True
    ctrl.client.services.get.assert_not_called()


def test_event_of_an_unknown_service_is_looked_up_by_label(judge):
    services = {
        "inst": service("i", {"bunkerweb.INSTANCE": "yes"}),
        "site": service("s", {"bunkerweb.SERVER_NAME": "a.example.com"}),
        "plain": service("p", {"app": "x"}),
    }
    _, process = judge(services=services)

    assert process(swarm_event(actor="inst")) is True
    assert process(swarm_event(actor="site")) is True
    assert process(swarm_event(actor="plain")) is False
    assert process(swarm_event(actor="gone")) is False


def test_service_event_outside_the_namespaces_is_dropped(judge):
    """QAR Q8"""
    services = {
        "in": service("i", {"bunkerweb.INSTANCE": "yes", "bunkerweb.NAMESPACE": "prod"}),
        "out": service("o", {"bunkerweb.INSTANCE": "yes", "bunkerweb.NAMESPACE": "dev"}),
    }
    _, process = judge(services=services, NAMESPACES="prod")

    assert process(swarm_event(actor="in")) is True
    assert process(swarm_event(actor="out")) is False


def test_service_event_with_an_ignored_label_is_dropped(judge):
    services = {"s": service("s", {"bunkerweb.INSTANCE": "yes", "bunkerweb.SKIP": "1"})}
    _, process = judge(services=services, SWARM_IGNORE_LABELS="SKIP")

    assert process(swarm_event(actor="s")) is False


def test_config_events(judge):
    configs = {
        "cfg": swarm_config("a", {"bunkerweb.CONFIG_TYPE": "http"}),
        "other": swarm_config("b", {"app": "x"}),
        "scoped": swarm_config("c", {"bunkerweb.CONFIG_TYPE": "http", "bunkerweb.NAMESPACE": "dev"}),
        "ign": swarm_config("d", {"bunkerweb.CONFIG_TYPE": "http", "bunkerweb.SKIP": "1"}),
    }
    ctrl, process = judge(configs=configs, NAMESPACES="prod", SWARM_IGNORE_LABELS="SKIP")

    assert process(swarm_event("config", "cfg")) is False  # no NAMESPACE label under NAMESPACES=prod
    assert process(swarm_event("config", "other")) is False
    assert process(swarm_event("config", "scoped")) is False
    assert process(swarm_event("config", "ign")) is False
    assert process(swarm_event("config", "missing")) is False
    ctrl._SwarmController__swarm_configs.append("cfg")
    assert process(swarm_event("config", "cfg")) is True


def test_unscoped_config_event_is_processed(judge):
    configs = {"cfg": swarm_config("a", {"bunkerweb.CONFIG_TYPE": "http"})}
    _, process = judge(configs=configs)

    assert process(swarm_event("config", "cfg")) is True


# --- the event loop ---------------------------------------------------------------------------------


def run_event(ctrl, monkeypatch, batches):
    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(module, "time", lambda: next(clock))

    def stop(_seconds):
        raise Stop

    monkeypatch.setattr(module, "sleep", stop)
    pending = iter(batches)

    def events(decode=True, filters=None):
        try:
            return iter(next(pending))
        except StopIteration:
            raise RuntimeError("no more events") from None

    ctrl.client.events.side_effect = events
    with pytest.raises(Stop):
        ctrl._SwarmController__event("service")


def test_a_service_event_deploys_instances_services_and_configs(swarm_env, fake_db, monkeypatch):
    tasks = [{"ID": "t1", "NodeID": "n1", "DesiredState": "running", "Status": {"State": "running"}}]
    bw = service("bw", {"bunkerweb.INSTANCE": "yes"}, env=[], tasks=tasks, sid="bw1")
    web = service("web", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.USE_ANTIBOT": "captcha"}, sid="web1")
    cfg = swarm_config("hello", {"bunkerweb.CONFIG_TYPE": "server-http", "bunkerweb.CONFIG_SITE": "app.example.com"}, b"location / {}")
    ctrl = build({"bunkerweb.INSTANCE": [bw], "bunkerweb.SERVER_NAME": [web]}, [cfg])
    log = attach_log(ctrl)

    run_event(ctrl, monkeypatch, [[swarm_event(actor="web1")]])

    assert fake_db.saved_configs[0]["app.example.com_USE_ANTIBOT"] == "captcha"
    assert fake_db.saved_instances[0][0]["hostname"] == "bw.n1.t1"
    assert fake_db.saved_custom_configs[0] == [{"value": b"location / {}", "exploded": ["app.example.com", "server-http", "hello"]}]
    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert log.has("Successfully deployed new configuration", logging.INFO)


def test_an_exception_while_applying_is_logged(swarm_env, fake_db, monkeypatch):
    ctrl = build()
    ctrl.get_instances = MagicMock(side_effect=ValueError("api down"))
    log = attach_log(ctrl)

    run_event(ctrl, monkeypatch, [[swarm_event()]])

    assert log.has("Exception while processing Swarm event (service)", logging.ERROR)
    assert ctrl._SwarmController__internal_lock.acquire(timeout=0.1)


def test_failed_apply_is_reported_without_marking_loaded(swarm_env, fake_db, monkeypatch):
    bw = service("bw", {"bunkerweb.INSTANCE": "yes"}, env=[], tasks=[{"ID": "t", "NodeID": "n", "DesiredState": "running", "Status": {"State": "running"}}])
    ctrl = build({"bunkerweb.INSTANCE": [bw]})
    fake_db.save_config = lambda *a, **k: "boom"
    log = attach_log(ctrl)

    run_event(ctrl, monkeypatch, [[swarm_event()]])

    assert log.has("Error while deploying new configuration", logging.ERROR)
    assert fake_db.set_metadata_calls == []


def test_unrelated_event_does_not_touch_the_database(swarm_env, fake_db, monkeypatch):
    ctrl = build()
    ctrl._first_start = False

    run_event(ctrl, monkeypatch, [[{"Type": "node", "Actor": {"ID": "n"}}]])

    assert fake_db.saved_configs == []


def test_process_events_runs_one_loop_per_event_type(swarm_env, monkeypatch):
    ctrl = build()
    seen = []
    monkeypatch.setattr(ctrl, "_SwarmController__event", lambda event_type: seen.append(event_type), raising=False)
    started = []
    monkeypatch.setattr(ctrl, "_start_settings_recheck_worker", lambda: started.append(True))

    ctrl.process_events()

    assert sorted(seen) == ["config", "service"]
    assert started == [True]
