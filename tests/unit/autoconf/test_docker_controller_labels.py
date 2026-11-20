"""DockerController: what the container labels turn into, and which containers are in scope at all."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log

import controllers.DockerController as module
from controllers.DockerController import DockerController
from docker.errors import DockerException


class Stop(BaseException):
    """Ends the endless event loops: raised out of a patched sleep()."""


def container(name, labels, status="running", health="unknown", env=None, cid=None):
    attrs = {"Config": {"Env": env}} if env is not None else {}
    return SimpleNamespace(id=cid or f"id-{name}", name=name, labels=labels, status=status, health=health, attrs=attrs)


CLIENT = {}


@pytest.fixture
def docker_env(clean_env, fake_db):
    clean_env.setenv("AUTOCONF_SETTINGS_RECHECK_INTERVAL", "0")
    clean_env.setattr(module, "DockerClient", lambda base_url=None: CLIENT["client"])
    return clean_env


def build(by_label):
    """A controller whose client lists `by_label[label_filter]`."""
    client = CLIENT["client"] = MagicMock(name="docker-client")
    client.containers.list.side_effect = lambda filters=None: list(by_label.get((filters or {}).get("label"), []))
    ctrl = DockerController("unix:///fake.sock")
    ctrl.client = client
    return ctrl


def test_service_labels_lose_the_prefix_and_foreign_labels_are_dropped(docker_env):
    web = container("web", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.USE_ANTIBOT": "captcha", "com.docker.compose.project": "x"})
    ctrl = build({"bunkerweb.SERVER_NAME": [web]})

    assert ctrl.get_services() == [{"SERVER_NAME": "app.example.com", "USE_ANTIBOT": "captcha"}]


def test_namespace_scope_ignores_containers_of_other_namespaces(docker_env):
    """QAR Q8: a container outside NAMESPACES is neither served nor given configs."""
    docker_env.setenv("NAMESPACES", "prod staging")
    mine = container("mine", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.NAMESPACE": "prod"})
    other = container("other", {"bunkerweb.SERVER_NAME": "b.example.com", "bunkerweb.NAMESPACE": "dev"})
    unscoped = container("none", {"bunkerweb.SERVER_NAME": "c.example.com"})
    ctrl = build({"bunkerweb.SERVER_NAME": [mine, other, unscoped]})
    log = attach_log(ctrl)

    assert [s["SERVER_NAME"] for s in ctrl.get_services()] == ["a.example.com"]
    assert log.has("does not match any namespace", logging.DEBUG)


def test_without_namespaces_every_container_is_in_scope(docker_env):
    a = container("a", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.NAMESPACE": "x"})
    b = container("b", {"bunkerweb.SERVER_NAME": "b.example.com"})
    ctrl = build({"bunkerweb.SERVER_NAME": [a, b]})

    assert [s["SERVER_NAME"] for s in ctrl.get_services()] == ["a.example.com", "b.example.com"]


@pytest.mark.parametrize("token", ["USE_ANTIBOT", "bunkerweb.USE_ANTIBOT"])
def test_ignored_label_hides_the_container_in_both_spellings(docker_env, token):
    docker_env.setenv("DOCKER_IGNORE_LABELS", token)
    skipped = container("skipped", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.USE_ANTIBOT": "yes"})
    kept = container("kept", {"bunkerweb.SERVER_NAME": "b.example.com"})
    ctrl = build({"bunkerweb.SERVER_NAME": [skipped, kept]})

    assert [s["SERVER_NAME"] for s in ctrl.get_services()] == ["b.example.com"]


def test_ignored_label_is_not_copied_into_a_service(docker_env):
    docker_env.setenv("DOCKER_IGNORE_LABELS", "bunkerweb.USE_ANTIBOT")
    ctrl = build({})
    svc = container("svc", {"bunkerweb.SERVER_NAME": "a.example.com", "bunkerweb.USE_ANTIBOT": "yes"})

    assert ctrl._to_services(svc) == [{"SERVER_NAME": "a.example.com"}]


def test_list_shaped_labels_are_accepted_and_odd_ones_skipped(docker_env):
    listed = container("listed", ["bunkerweb.SERVER_NAME"])
    odd = container("odd", "not-a-mapping")
    ctrl = build({"bunkerweb.SERVER_NAME": [listed, odd]})
    log = attach_log(ctrl)

    assert ctrl._get_controller_services() == [listed]
    assert log.has("Unexpected label format for container id-odd", logging.WARNING)


def test_container_without_a_labels_attribute_is_treated_as_unlabelled(docker_env):
    bare = SimpleNamespace(id="bare", name="bare")
    ctrl = build({"bunkerweb.SERVER_NAME": [bare]})

    assert ctrl._get_controller_services() == [bare]


def test_docker_error_while_listing_is_logged_and_raised(docker_env):
    ctrl = build({})
    ctrl.client.containers.list.side_effect = DockerException("daemon gone")
    log = attach_log(ctrl)

    with pytest.raises(DockerException):
        ctrl.get_services()
    assert log.has("Failed to retrieve containers with label 'bunkerweb.SERVER_NAME': daemon gone", logging.ERROR)


@pytest.mark.parametrize(
    ("status", "health", "expected"),
    [
        ("running", "healthy", True),
        ("running", "unhealthy", False),
        ("running", "starting", False),
        ("running", "unknown", True),
        ("exited", "unknown", False),
        ("exited", "healthy", False),
    ],
)
def test_instance_health_follows_healthcheck_then_run_state(docker_env, status, health, expected):
    ctrl = build({})
    inst = container("bw", {}, status=status, health=health, env=["A=1", "NOEQUALS", "B=x=y"])

    [instance] = ctrl._to_instances(inst)

    assert instance == {"name": "bw", "hostname": "bw", "type": "container", "health": expected, "env": {"A": "1", "B": "x=y"}}


def test_instance_without_config_env_has_empty_env(docker_env):
    ctrl = build({})
    inst = container("bw", {}, env=None)

    assert ctrl._to_instances(inst)[0]["env"] == {}


def test_get_instances_lists_labelled_containers(docker_env):
    bw = container("bw", {"bunkerweb.INSTANCE": "yes"}, health="healthy", env=[])
    ctrl = build({"bunkerweb.INSTANCE": [bw]})

    assert [i["name"] for i in ctrl.get_instances()] == ["bw"]


CONF_LABEL = "bunkerweb.CUSTOM_CONF_SERVER_HTTP_hello"


def test_custom_conf_labels_become_site_configs(docker_env, fake_db):
    web = container(
        "web", {"bunkerweb.SERVER_NAME": "app.example.com", CONF_LABEL: "location /hi { return 200; }", "bunkerweb.CUSTOM_CONF_MODSEC_CRS_rules": "SecRule"}
    )
    ctrl = build({"bunkerweb.SERVER_NAME": [web]})
    ctrl._services = [{"SERVER_NAME": "app.example.com"}]

    configs = ctrl.get_configs()

    assert configs["server-http"] == {"app.example.com/hello": "location /hi { return 200; }"}
    assert configs["modsec-crs"] == {"app.example.com/rules": "SecRule"}
    assert configs["http"] == {}


def test_custom_conf_for_unknown_service_is_dropped(docker_env, fake_db):
    web = container("web", {"bunkerweb.SERVER_NAME": "ghost.example.com", CONF_LABEL: "x"})
    ctrl = build({"bunkerweb.SERVER_NAME": [web]})
    log = attach_log(ctrl)

    assert ctrl.get_configs()["server-http"] == {}
    assert log.has("Ignoring config because ghost.example.com doesn't exist", logging.WARNING)


def test_custom_conf_of_a_service_known_to_the_database_is_kept(docker_env, fake_db):
    fake_db.services = [{"id": "db.example.com"}]
    web = container("web", {"bunkerweb.SERVER_NAME": "db.example.com", CONF_LABEL: "x"})
    ctrl = build({"bunkerweb.SERVER_NAME": [web]})

    assert ctrl.get_configs()["server-http"] == {"db.example.com/hello": "x"}


def test_custom_conf_respects_namespaces_ignored_labels_and_missing_names(docker_env, fake_db):
    docker_env.setenv("NAMESPACES", "prod")
    docker_env.setenv("DOCKER_IGNORE_LABELS", "SKIP")
    ok = container("ok", {"bunkerweb.SERVER_NAME": "ok.example.com", "bunkerweb.NAMESPACE": "prod", CONF_LABEL: "ok"})
    foreign = container("foreign", {"bunkerweb.SERVER_NAME": "ok.example.com", "bunkerweb.NAMESPACE": "dev", CONF_LABEL: "foreign"})
    ignored = container("ignored", {"bunkerweb.SERVER_NAME": "ok.example.com", "bunkerweb.NAMESPACE": "prod", "bunkerweb.SKIP": "1", CONF_LABEL: "ignored"})
    nameless = container("nameless", {"bunkerweb.SERVER_NAME": "", "bunkerweb.NAMESPACE": "prod", CONF_LABEL: "nameless"})
    weird = container("weird", "not-a-mapping")
    listed = container("listed", ["bunkerweb.SERVER_NAME"])
    ctrl = build({"bunkerweb.SERVER_NAME": [ok, foreign, ignored, nameless, weird, listed]})
    ctrl._services = [{"SERVER_NAME": "ok.example.com"}]
    log = attach_log(ctrl)

    assert ctrl.get_configs()["server-http"] == {"ok.example.com/hello": "ok"}
    assert log.has("because of ignored labels", logging.INFO)
    assert log.has("Unexpected label format", logging.WARNING)


# --- event filtering --------------------------------------------------------------------------------


def event(action="start", attributes=None, **extra):
    return {"Action": action, "Actor": {"Attributes": attributes if attributes is not None else {"bunkerweb.INSTANCE": "yes"}}, **extra}


@pytest.fixture
def judge(docker_env):
    def make(**env):
        for name, value in env.items():
            docker_env.setenv(name, value)
        ctrl = build({})
        ctrl._first_start = False
        return ctrl, ctrl._DockerController__process_event

    return make


def test_first_event_is_always_processed(docker_env):
    ctrl = build({})

    assert ctrl._DockerController__process_event({"Action": "exec_start"}) is True


@pytest.mark.parametrize("action", ["start", "die", "health_status: healthy", "destroy", "rename"])
def test_lifecycle_events_of_bunkerweb_containers_are_processed(judge, action):
    _, process = judge()

    assert process(event(action)) is True


@pytest.mark.parametrize("action", ["exec_start: sh", "attach", "top", "unknown_action", ""])
def test_noise_and_unknown_actions_are_dropped(judge, action):
    _, process = judge()

    assert process(event(action)) is False


def test_event_without_bunkerweb_label_or_attributes_is_dropped(judge):
    _, process = judge()

    assert process(event(attributes={"image": "nginx"})) is False
    assert process({"Action": "start", "Actor": {"Attributes": None}}) is False
    assert process({"Action": "start"}) is False


def test_event_of_a_server_name_container_is_processed(judge):
    _, process = judge()

    assert process(event(attributes={"bunkerweb.SERVER_NAME": "a.example.com"})) is True


def test_event_outside_the_namespaces_is_dropped(judge):
    """QAR Q8"""
    ctrl, process = judge(NAMESPACES="prod")
    log = attach_log(ctrl)

    assert process(event(attributes={"bunkerweb.INSTANCE": "yes", "bunkerweb.NAMESPACE": "dev", "name": "web"})) is False
    assert process(event(attributes={"bunkerweb.INSTANCE": "yes", "bunkerweb.NAMESPACE": "prod"})) is True
    assert log.has("Skipping Docker event for web because its namespace", logging.INFO)


def test_event_with_an_ignored_label_is_dropped(judge):
    ctrl, process = judge(DOCKER_IGNORE_LABELS="bunkerweb.INSTANCE")

    assert process(event(attributes={"bunkerweb.INSTANCE": "yes", "container": "c1"})) is False


# --- the event loop ---------------------------------------------------------------------------------


def run_loop(ctrl, monkeypatch, events_batches):
    """Drive process_events: the debounce is skipped, and the loop ends when the batches are used up and the error sleep fires."""
    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(module, "time", lambda: next(clock))

    def stop(_seconds):
        raise Stop

    monkeypatch.setattr(module, "sleep", stop)
    batches = iter(events_batches)

    def events(decode=True, filters=None):
        try:
            return iter(next(batches))
        except StopIteration:
            raise RuntimeError("no more events") from None

    ctrl.client.events.side_effect = events
    with pytest.raises(Stop):
        ctrl.process_events()


def test_a_relevant_event_deploys_the_labelled_service(docker_env, fake_db, monkeypatch):
    bw = container("bw", {"bunkerweb.INSTANCE": "yes"}, health="healthy", env=["API_HTTP_PORT=5000"])
    web = container(
        "web", {"bunkerweb.SERVER_NAME": "app.example.com", "bunkerweb.USE_REVERSE_PROXY": "yes", "bunkerweb.REVERSE_PROXY_HOST": "http://web:8080"}
    )
    ctrl = build({"bunkerweb.INSTANCE": [bw], "bunkerweb.SERVER_NAME": [web]})
    log = attach_log(ctrl)

    run_loop(ctrl, monkeypatch, [[event("start")]])

    assert fake_db.saved_configs == [
        {
            "SERVER_NAME": "app.example.com",
            "MULTISITE": "yes",
            "app.example.com_SERVER_NAME": "app.example.com",
            "app.example.com_USE_REVERSE_PROXY": "yes",
            "app.example.com_REVERSE_PROXY_HOST": "http://web:8080",
        }
    ]
    assert fake_db.saved_instances[0][0]["name"] == "bw"
    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert log.has("Successfully deployed new configuration", logging.INFO)
    assert log.has("Exception while reading Docker event", logging.ERROR)


def test_an_event_that_changes_nothing_is_not_deployed(docker_env, fake_db, monkeypatch):
    bw = container("bw", {"bunkerweb.INSTANCE": "yes"}, health="healthy", env=[])
    web = container("web", {"bunkerweb.SERVER_NAME": "app.example.com"})
    ctrl = build({"bunkerweb.INSTANCE": [bw], "bunkerweb.SERVER_NAME": [web]})

    run_loop(ctrl, monkeypatch, [[event("start"), event("stop")]])

    assert len(fake_db.saved_configs) == 1


def test_irrelevant_events_never_reach_the_database(docker_env, fake_db, monkeypatch):
    ctrl = build({})
    ctrl._first_start = False

    run_loop(ctrl, monkeypatch, [[event("exec_start"), event("start", attributes={"image": "nginx"})]])

    assert fake_db.saved_configs == []
    assert ctrl._first_start is False


def test_failed_apply_is_reported_and_the_loop_continues(docker_env, fake_db, monkeypatch):
    bw = container("bw", {"bunkerweb.INSTANCE": "yes"}, health="healthy", env=[])
    ctrl = build({"bunkerweb.INSTANCE": [bw]})
    fake_db.save_config = lambda *a, **k: "boom"
    log = attach_log(ctrl)

    run_loop(ctrl, monkeypatch, [[event("start")]])

    assert log.has("Error while deploying new configuration", logging.ERROR)
    assert fake_db.set_metadata_calls == []


def test_an_exception_while_applying_is_logged_and_the_lock_is_released(docker_env, fake_db, monkeypatch):
    ctrl = build({})
    ctrl.get_instances = MagicMock(side_effect=ValueError("api down"))
    log = attach_log(ctrl)

    run_loop(ctrl, monkeypatch, [[event("start")]])

    assert log.has("Exception while processing Docker event", logging.ERROR)
    assert ctrl._DockerController__internal_lock.acquire(timeout=0.1)


def test_a_busy_scheduler_delays_the_deploy(docker_env, fake_db, monkeypatch):
    """While the scheduler is applying (metadata flag), the controller waits instead of writing."""
    fake_db.metadata = {"is_initialized": True, "instances_changed": True}
    bw = container("bw", {"bunkerweb.INSTANCE": "yes"}, health="healthy", env=[])
    ctrl = build({"bunkerweb.INSTANCE": [bw]})
    sleeps = []

    def release_after_first_wait(_seconds):
        sleeps.append(_seconds)
        fake_db.metadata = {"is_initialized": True}
        if len(sleeps) > 1:
            raise Stop

    clock = iter(range(0, 10_000, 100))
    monkeypatch.setattr(module, "time", lambda: next(clock))
    monkeypatch.setattr(module, "sleep", release_after_first_wait)
    ctrl.client.events.side_effect = [iter([event("start")]), RuntimeError("end")]

    with pytest.raises(Stop):
        ctrl.process_events()

    assert sleeps[0] == 1
    assert len(fake_db.saved_configs) == 1


def test_apply_config_marks_the_first_apply_until_loaded(docker_env, fake_db):
    ctrl = build({})
    ctrl._instances = [{"name": "bw", "hostname": "bw", "type": "container", "health": True, "env": {}}]
    ctrl._services = [{"SERVER_NAME": "a.example.com"}]
    ctrl._configs = {}

    assert ctrl.apply_config() is True

    assert fake_db.checked[0] == ["instances", "services", "custom_configs", "extra_config", "config"]
