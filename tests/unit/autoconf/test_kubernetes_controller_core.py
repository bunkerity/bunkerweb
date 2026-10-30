"""KubernetesController: pods, ConfigMaps, scope filtering, Ingress merging and the watch event plumbing."""

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log, ns
from kubernetes import client as k
from kubernetes.client.exceptions import ApiException

import controllers.KubernetesController as module
from controllers.KubernetesController import KubernetesController


class Stop(BaseException):
    """Ends an endless loop: raised out of a patched sleep()."""


class K8s(KubernetesController):
    """The base controller with the abstract hooks stubbed out."""

    watchers = {}
    custom_event = False

    def _get_controller_services(self):
        return []

    def _get_watchers(self):
        return self.watchers

    def _is_custom_event(self, kind, obj, annotations, namespace, name):
        return self.custom_event


@pytest.fixture
def ctrl(k8s_env):
    c = K8s()
    c._corev1 = MagicMock(name="corev1")
    return c


def meta(name="x", namespace="prod", annotations=None, **kw):
    return k.V1ObjectMeta(name=name, namespace=namespace, annotations=annotations, **kw)


# --- configuration from the environment ---------------------------------------------------------------


def test_defaults(ctrl):
    assert ctrl._domain_name == "cluster.local"
    assert ctrl._service_protocol == "http"
    assert ctrl._use_fqdn is True
    assert ctrl._reverse_proxy_suffix_start == 1
    assert ctrl._service_name == "bunkerweb" and ctrl._namespace == "bunkerweb"


def test_environment_overrides(k8s_env):
    k8s_env.setenv("KUBERNETES_DOMAIN_NAME", "corp.local")
    k8s_env.setenv("KUBERNETES_SERVICE_PROTOCOL", "HTTPS")
    k8s_env.setenv("USE_KUBERNETES_FQDN", "no")
    k8s_env.setenv("BUNKERWEB_SERVICE_NAME", "bw-svc")
    k8s_env.setenv("BUNKERWEB_NAMESPACE", "edge")
    k8s_env.setenv("KUBERNETES_REVERSE_PROXY_SUFFIX_START", "0")

    c = K8s()

    assert (c._domain_name, c._service_protocol, c._use_fqdn) == ("corp.local", "https", False)
    assert (c._service_name, c._namespace, c._reverse_proxy_suffix_start) == ("bw-svc", "edge", 0)


def test_unsupported_protocol_and_bad_suffix_fall_back(k8s_env):
    k8s_env.setenv("KUBERNETES_SERVICE_PROTOCOL", "ftp")
    k8s_env.setenv("KUBERNETES_REVERSE_PROXY_SUFFIX_START", "-3")

    c = K8s()

    assert c._service_protocol == "http"
    assert c._reverse_proxy_suffix_start == 1


def test_ssl_settings_reach_the_shared_client_configuration(k8s_env):
    k8s_env.setenv("KUBERNETES_VERIFY_SSL", "no")
    k8s_env.setenv("KUBERNETES_SSL_CA_CERT", "/ca.pem")

    K8s()

    cfg = module.Configuration._default
    assert cfg.verify_ssl is False
    assert cfg.ssl_ca_cert == "/ca.pem"
    assert (module.IPPROTO_TCP, module.TCP_NODELAY, 1) in cfg.socket_options


@pytest.mark.parametrize(
    ("token", "annotation", "ignored"),
    [
        ("skip-me", "bunkerweb.io/skip-me", True),
        ("skip-me", "other.io/skip-me", False),
        ("bunkerweb.io/skip-me", "bunkerweb.io/skip-me", True),
        ("example.com/thing", "example.com/thing", True),
        ("example.com/thing", "thing", False),
    ],
)
def test_ignored_annotations(k8s_env, token, annotation, ignored):
    k8s_env.setenv("KUBERNETES_IGNORE_ANNOTATIONS", token)

    assert K8s()._should_ignore_annotation(annotation) is ignored


def test_nothing_is_ignored_by_default(ctrl):
    assert ctrl._should_ignore_annotation("bunkerweb.io/anything") is False


# --- pods -----------------------------------------------------------------------------------------------


def pod(name="bw-0", namespace="prod", annotations=None, ip="10.0.0.5", phase="Running", running=True, containers=None, conditions=None, deleting=False):
    if containers is None:
        containers = [k.V1Container(name="bunkerweb", env=[k.V1EnvVar(name="API_HTTP_PORT", value="5000"), k.V1EnvVar(name="EMPTY")])]
    statuses = [
        k.V1ContainerStatus(
            name="bunkerweb",
            image="i",
            image_id="i",
            ready=False,
            restart_count=0,
            state=k.V1ContainerState(running=k.V1ContainerStateRunning() if running else None),
        )
    ]
    return k.V1Pod(
        metadata=meta(name, namespace, annotations, deletion_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) if deleting else None),
        spec=k.V1PodSpec(containers=containers),
        status=k.V1PodStatus(phase=phase, pod_ip=ip, container_statuses=statuses, conditions=conditions),
    )


def test_pods_are_selected_by_annotation(ctrl):
    ctrl._corev1.list_pod_for_all_namespaces.return_value = SimpleNamespace(
        items=[pod("a", annotations={"bunkerweb.io/INSTANCE": "yes"}), pod("b", annotations={"x": "y"}), pod("c"), SimpleNamespace(metadata=None)]
    )

    assert [p.metadata.name for p in ctrl._get_controller_instances()] == ["a"]


def test_pods_outside_the_namespaces_or_with_ignored_annotations_are_dropped(k8s_env):
    """QAR Q8"""
    k8s_env.setenv("NAMESPACES", "prod")
    k8s_env.setenv("KUBERNETES_IGNORE_ANNOTATIONS", "skip")
    c = K8s()
    c._corev1 = MagicMock()
    inst = {"bunkerweb.io/INSTANCE": "yes"}
    c._corev1.list_pod_for_all_namespaces.return_value = SimpleNamespace(
        items=[pod("in", "prod", inst), pod("out", "dev", inst), pod("skipped", "prod", {**inst, "bunkerweb.io/skip": "1"})]
    )

    assert [p.metadata.name for p in c._get_controller_instances()] == ["in"]


def test_running_pod_becomes_a_healthy_instance_with_its_env(ctrl):
    [instance] = ctrl._to_instances(pod())

    assert instance == {
        "name": "bw-0",
        "hostname": "10-0-0-5.prod.pod.cluster.local",
        "health": True,
        "type": "pod",
        "env": {"API_HTTP_PORT": "5000", "EMPTY": ""},
    }


def test_pod_hostname_uses_the_ip_without_fqdn(k8s_env):
    k8s_env.setenv("USE_KUBERNETES_FQDN", "no")
    c = K8s()

    assert c._to_instances(pod())[0]["hostname"] == "10.0.0.5"
    assert c._to_instances(pod(ip=None))[0]["hostname"] == "bw-0"


@pytest.mark.parametrize(
    "kwargs",
    [{"phase": "Pending"}, {"ip": None}, {"deleting": True}, {"running": False}],
    ids=["pending", "no-ip", "terminating", "container-not-running"],
)
def test_pod_that_cannot_serve_yet_is_unhealthy(ctrl, kwargs):
    assert ctrl._to_instances(pod(**kwargs))[0]["health"] is False


def test_pod_without_a_bunkerweb_container_uses_the_ready_condition(ctrl):
    ready = [k.V1PodCondition(type="Ready", status="True")]
    log = attach_log(ctrl)

    other = pod(containers=[k.V1Container(name="sidecar")], conditions=ready)

    assert ctrl._to_instances(other)[0]["health"] is True
    assert ctrl._to_instances(pod(containers=[k.V1Container(name="sidecar")]))[0]["health"] is False
    assert log.has("Missing container bunkerweb in pod bw-0", logging.WARNING)


def test_pod_without_status_is_unhealthy(ctrl):
    p = pod()
    p.status = None

    assert ctrl._to_instances(p)[0]["health"] is False


def test_service_annotations_become_instance_env(ctrl):
    ctrl._get_controller_services = lambda: [ns(metadata=meta(annotations={"bunkerweb.io/USE_ANTIBOT": "captcha", "other.io/x": "y"})), ns(metadata=None)]

    assert ctrl._to_instances(pod())[0]["env"]["USE_ANTIBOT"] == "captcha"
    assert "x" not in ctrl._to_instances(pod())[0]["env"]


# --- ConfigMaps -----------------------------------------------------------------------------------------


def cm(name, data, annotations, namespace="prod"):
    return k.V1ConfigMap(metadata=meta(name, namespace, annotations), data=data)


def configmaps(ctrl, *maps):
    ctrl._corev1.list_config_map_for_all_namespaces.return_value = SimpleNamespace(items=list(maps))


def test_configmaps_become_custom_configs_by_type(ctrl):
    configmaps(ctrl, cm("hello", {"hello.conf": "location / {}"}, {"bunkerweb.io/CONFIG_TYPE": "http"}), cm("plain", {"a": "b"}, None))

    extra, configs = ctrl.get_configs()

    assert configs["http"] == {"hello.conf": "location / {}"}
    assert extra == {}
    assert ctrl._managed_configmaps == {"prod/hello"}


def test_site_configmap_is_prefixed_with_its_service(ctrl):
    ctrl._services = [{"SERVER_NAME": "app.example.com www.example.com"}, {"SERVER_NAME": ""}]
    configmaps(ctrl, cm("s", {"x.conf": "c"}, {"bunkerweb.io/CONFIG_TYPE": "server-http", "bunkerweb.io/CONFIG_SITE": "app.example.com"}))

    _, configs = ctrl.get_configs()

    assert configs["server-http"] == {"app.example.com/x.conf": "c"}


def test_site_configmap_of_an_unknown_service_is_dropped(ctrl):
    configmaps(ctrl, cm("s", {"x": "c"}, {"bunkerweb.io/CONFIG_TYPE": "server-http", "bunkerweb.io/CONFIG_SITE": "ghost.example.com"}))
    log = attach_log(ctrl)

    _, configs = ctrl.get_configs()

    assert configs["server-http"] == {}
    assert log.has("Ignoring config s because ghost.example.com doesn't exist", logging.WARNING)


def test_settings_configmap_keeps_only_valid_settings(ctrl):
    configmaps(ctrl, cm("s", {"USE_ANTIBOT": "captcha", "NOT_A_SETTING": "x"}, {"bunkerweb.io/CONFIG_TYPE": "settings"}))
    log = attach_log(ctrl)

    extra, _ = ctrl.get_configs()

    assert extra == {"USE_ANTIBOT": "captcha"}
    assert log.has("Ignoring invalid setting NOT_A_SETTING for ConfigMap s", logging.WARNING)


def test_site_settings_configmap_prefixes_the_service_once(ctrl):
    ctrl._services = [{"SERVER_NAME": "app.example.com"}]
    configmaps(
        ctrl,
        cm(
            "s",
            {"USE_ANTIBOT": "captcha", "app.example.com_LIMIT_REQ_RATE": "2r/s"},
            {"bunkerweb.io/CONFIG_TYPE": "settings", "bunkerweb.io/CONFIG_SITE": "app.example.com"},
        ),
    )

    extra, _ = ctrl.get_configs()

    assert extra == {"app.example.com_USE_ANTIBOT": "captcha", "app.example.com_LIMIT_REQ_RATE": "2r/s"}


def test_configmaps_outside_scope_are_ignored(k8s_env):
    """QAR Q8: namespace, ignored annotation, unsupported type and blank data."""
    k8s_env.setenv("NAMESPACES", "prod")
    k8s_env.setenv("KUBERNETES_IGNORE_ANNOTATIONS", "skip")
    c = K8s()
    c._corev1 = MagicMock()
    t = {"bunkerweb.io/CONFIG_TYPE": "http"}
    configmaps(
        c,
        cm("ok", {"ok": "1"}, t),
        cm("foreign", {"foreign": "1"}, t, namespace="dev"),
        cm("skipped", {"skipped": "1"}, {**t, "bunkerweb.io/skip": "1"}),
        cm("badtype", {"x": "1"}, {"bunkerweb.io/CONFIG_TYPE": "nonsense"}),
        cm("blank", None, t),
    )
    log = attach_log(c)

    _, configs = c.get_configs()

    assert configs["http"] == {"ok": "1"}
    assert c._managed_configmaps == {"prod/ok"}
    assert log.has("Ignoring unsupported CONFIG_TYPE nonsense", logging.WARNING)
    assert log.has("Ignoring blank ConfigMap blank", logging.WARNING)


# --- events ---------------------------------------------------------------------------------------------


def secret(data, name="tls", namespace="prod"):
    return k.V1Secret(metadata=meta(name, namespace), data=data, kind="Secret")


def evt(obj, typ="MODIFIED"):
    return {"type": typ, "object": obj}


@pytest.fixture
def running(ctrl):
    ctrl._first_start = False
    return ctrl


def with_kind(obj, kind):
    obj.kind = kind
    return obj


def test_first_event_is_always_processed(ctrl):
    assert ctrl._process_event({"type": "ADDED"}) is True


def test_event_without_an_object_is_dropped(running):
    assert running._process_event({"type": "ADDED", "object": None}) is False


def test_pod_event_needs_the_instance_annotation(running):
    assert running._process_event(evt(with_kind(pod(annotations={"bunkerweb.io/INSTANCE": "yes"}), "Pod"))) is True
    assert not running._process_event(evt(with_kind(pod(annotations={"x": "y"}), "Pod")))
    assert not running._process_event(evt(with_kind(pod(), "Pod")))


def test_configmap_event_rules(running):
    managed = with_kind(cm("m", {"a": "b"}, None), "ConfigMap")
    labelled = with_kind(cm("l", {"a": "b"}, {"bunkerweb.io/CONFIG_TYPE": "http"}), "ConfigMap")
    plain = with_kind(cm("p", {"a": "b"}, None), "ConfigMap")
    running._managed_configmaps = {"prod/m"}

    assert running._process_event(evt(labelled)) is True
    assert running._process_event(evt(managed)) is True
    assert running._process_event(evt(plain)) is False
    assert running._process_event(evt(managed, "DELETED")) is True
    assert running._process_event(evt(labelled, "DELETED")) is False


def test_service_event_is_always_relevant(running):
    assert running._process_event(evt(with_kind(k.V1Service(metadata=meta("s")), "Service"))) is True


def test_secret_event_needs_a_tls_pair(running):
    assert running._process_event(evt(secret({"tls.crt": "c", "tls.key": "k"}))) is True
    assert not running._process_event(evt(secret({"tls.crt": "c"})))
    assert not running._process_event(evt(secret(None)))


def test_unknown_kinds_are_left_to_the_subclass(running):
    other = with_kind(k.V1Service(metadata=meta("s")), "Gateway")

    assert running._process_event(evt(other)) is False
    running.custom_event = True
    assert running._process_event(evt(other)) is True


def test_events_outside_the_namespaces_are_dropped(k8s_env):
    """QAR Q8"""
    k8s_env.setenv("NAMESPACES", "prod")
    c = K8s()
    c._first_start = False

    assert c._process_event(evt(with_kind(k.V1Service(metadata=meta("s", "dev")), "Service"))) is False
    assert c._process_event(evt(with_kind(k.V1Service(metadata=meta("s", "prod")), "Service"))) is True


def test_events_with_ignored_annotations_are_dropped(k8s_env):
    k8s_env.setenv("KUBERNETES_IGNORE_ANNOTATIONS", "skip")
    c = K8s()
    c._first_start = False

    skipped = with_kind(k.V1Service(metadata=meta("s", annotations={"bunkerweb.io/skip": "1"})), "Service")

    assert c._process_event(evt(skipped)) is False


def test_dict_objects_are_understood(running):
    obj = {"kind": "Secret", "metadata": {"namespace": "prod", "name": "tls", "annotations": None}, "data": {"tls.crt": "c", "tls.key": "k"}}

    assert running._get_event_fields(obj) == ("Secret", {}, "prod", "tls", {"tls.crt": "c", "tls.key": "k"})
    assert running._process_event(evt(obj)) is True


def test_object_without_metadata_has_no_fields(running):
    assert running._get_event_fields(SimpleNamespace(metadata=None, kind="Pod")) == ("Pod", None, None, None, None)


def test_status_only_events_are_dropped_before_anything_else(ctrl):
    ctrl._is_status_only_event = lambda event: True

    assert ctrl._process_event({"type": "MODIFIED", "object": object()}) is False


# --- event summary --------------------------------------------------------------------------------------


def test_event_summary_collapses_repeats_and_prefers_deletion(ctrl):
    ctrl._record_event("Ingress", "prod", "web", "ADDED")
    ctrl._record_event("Ingress", "prod", "web", "MODIFIED")
    ctrl._record_event("Secret", "prod", "tls", "ADDED")
    ctrl._record_event("Secret", "prod", "tls", "DELETED")
    ctrl._record_event("Pod", "prod", "bw", "ADDED")
    ctrl._record_event(None, "prod", "x", "ADDED")
    ctrl._record_event("Gateway", None, None, None)

    assert ctrl._format_event_summary() == "Ingress prod/web (ADDED), Secret prod/tls (DELETED), Gateway unknown (UPDATED)"


def test_event_summary_is_capped(ctrl):
    ctrl._event_summary_max = 2
    for index in range(5):
        ctrl._record_event("Ingress", "prod", f"i{index}", "ADDED")

    assert ctrl._format_event_summary() == "Ingress prod/i0 (ADDED), Ingress prod/i1 (ADDED), and 3 more"


def test_logging_the_summary_empties_it(ctrl):
    log = attach_log(ctrl)
    ctrl._log_event_summary()
    ctrl._record_event("Ingress", "prod", "web", "ADDED")
    ctrl._log_event_summary()

    assert log.messages(logging.INFO)[-1] == "Detected Kubernetes changes: Ingress prod/web (ADDED)"
    assert ctrl._event_summary == {}
    assert ctrl._format_event_summary() == ""


# --- health markers -------------------------------------------------------------------------------------


@pytest.fixture
def healthy_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "HEALTHY_PATH", tmp_path / "state" / "autoconf.healthy")
    return tmp_path / "state"


def test_expected_watches_are_published_and_seeded_healthy(ctrl, healthy_dir):
    ctrl._write_expected_watch_types(["pod", "ingress", "gateway class!"])

    assert (healthy_dir / "autoconf.healthy.expected").read_text() == "gateway_class_\ningress\npod\n"
    for name in ("pod", "ingress", "gateway_class_"):
        assert (healthy_dir / f"autoconf.healthy.{name}").read_text() == "ok"


def test_unhealthy_then_healthy_again(ctrl, healthy_dir):
    ctrl._write_expected_watch_types(["pod"])
    log = attach_log(ctrl)

    ctrl._mark_unhealthy("pod", "failed 5 times")
    assert not (healthy_dir / "autoconf.healthy.pod").exists()
    ctrl._mark_healthy("pod")
    assert (healthy_dir / "autoconf.healthy.pod").read_text() == "ok"

    assert log.has("Marking autoconf unhealthy for watch pod: failed 5 times", logging.ERROR)
    assert log.has("Kubernetes watch pod is streaming again", logging.INFO)


def test_marking_healthy_twice_is_silent(ctrl, healthy_dir):
    ctrl._write_expected_watch_types(["pod"])
    log = attach_log(ctrl)

    ctrl._mark_healthy("pod")

    assert not log.has("streaming again")


def test_marking_unhealthy_a_watch_that_never_started_is_harmless(ctrl, healthy_dir):
    ctrl._mark_unhealthy("never", "x")


# --- watch streams --------------------------------------------------------------------------------------


class FakeWatch:
    """watch.Watch stand-in: each stream() call plays the next scripted outcome (events, or an exception to raise)."""

    script = []
    calls = []

    def __init__(self):
        self.resource_version = None

    def stream(self, what, **kwargs):
        FakeWatch.calls.append((what, kwargs, self.resource_version))
        outcome = FakeWatch.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        yield from outcome


@pytest.fixture
def fake_watch(monkeypatch):
    FakeWatch.script, FakeWatch.calls = [], []
    monkeypatch.setattr(module.watch, "Watch", FakeWatch)
    sleeps = []
    monkeypatch.setattr(module, "sleep", lambda seconds: sleeps.append(seconds))
    return SimpleNamespace(script=FakeWatch.script, calls=FakeWatch.calls, sleeps=sleeps)


def test_stream_tracks_the_resource_version_and_restarts_after_a_long_clean_close(ctrl, fake_watch, healthy_dir, monkeypatch):
    clock = iter([0, 100, 100, 200, 200, 300, 300])
    monkeypatch.setattr(module, "time", lambda: next(clock))
    fake_watch.script += [[{"raw_object": {"metadata": {"resourceVersion": "7"}}, "id": 1}, {"raw_object": None, "id": 2}], Stop()]

    gen = ctrl._get_stream_with_retries("pod", "lister")
    got = [next(gen), next(gen)]
    with pytest.raises(Stop):
        next(gen)

    assert [e["id"] for e in got] == [1, 2]
    assert fake_watch.calls[1][2] == "7"
    assert fake_watch.calls[0][1]["timeout_seconds"] == module.WATCH_TIMEOUT_SECONDS


def test_expired_resource_version_resets_the_stream_without_sleeping(ctrl, fake_watch):
    fake_watch.script += [ApiException(status=410, reason="Expired: too old resource version: 5 (9)"), []]
    log = attach_log(ctrl)

    gen = ctrl._get_stream_with_retries("pod", "lister", retries=2)
    with pytest.raises(RuntimeError):
        next(gen)

    assert fake_watch.sleeps == [5]
    assert log.has("resetting watch stream", logging.DEBUG)
    assert fake_watch.calls[1][2] is None


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (ApiException(status=403, reason="Forbidden"), "rejected our credentials while watching pod (403 Forbidden)"),
        (ApiException(status=401, reason="Unauthorized"), "rejected our credentials while watching pod (401 Unauthorized)"),
        (ApiException(status=500, reason="Oops"), "Unexpected ApiException while watching pod"),
        (ValueError("socket closed"), "Unexpected error while watching pod:\nsocket closed"),
    ],
)
def test_a_watch_that_keeps_failing_gives_up_and_marks_itself_unhealthy(ctrl, fake_watch, healthy_dir, error, fragment):
    ctrl._write_expected_watch_types(["pod"])
    fake_watch.script += [error, error]
    log = attach_log(ctrl)

    with pytest.raises(RuntimeError, match="Failed to watch pod after 2 retries"):
        next(ctrl._get_stream_with_retries("pod", "lister", retries=2))

    assert log.has(fragment, logging.ERROR)
    assert fake_watch.sleeps == [5, 5]
    assert not (healthy_dir / "autoconf.healthy.pod").exists()


def test_a_brief_clean_close_still_counts_as_a_failure(ctrl, fake_watch, healthy_dir, monkeypatch):
    clock = iter(range(0, 1000, 1))
    monkeypatch.setattr(module, "time", lambda: next(clock))
    fake_watch.script += [[], []]

    with pytest.raises(RuntimeError):
        next(ctrl._get_stream_with_retries("pod", "lister", retries=2))

    assert fake_watch.sleeps == [5, 5]


# --- the watch loop -------------------------------------------------------------------------------------


def run_watch(ctrl, monkeypatch, batches):
    clock = iter(range(0, 100_000, 100))
    monkeypatch.setattr(module, "time", lambda: next(clock))

    def stop(_seconds):
        raise Stop

    monkeypatch.setattr(module, "sleep", stop)
    pending = iter(batches)

    def stream(watch_type, what):
        try:
            outcome = next(pending)
        except StopIteration:
            raise RuntimeError("end of script") from None
        if isinstance(outcome, BaseException):
            raise outcome
        yield from outcome

    ctrl._get_stream_with_retries = stream
    ctrl._healthy_calls = []
    with pytest.raises(Stop):
        ctrl._watch("pod", "lister")


@pytest.fixture
def wired(ctrl, fake_db, healthy_dir):
    """A controller whose watch loop can run against the fake database."""
    ctrl._first_start = True
    ctrl.get_instances = lambda: [{"name": "bw", "hostname": "bw", "health": True, "type": "pod", "env": {}}]
    ctrl.get_services = lambda: [{"SERVER_NAME": "app.example.com", "NAMESPACE": "prod", "USE_ANTIBOT": "captcha"}]
    ctrl.get_configs = lambda: ({"USE_ANTIBOT": "yes"}, {"http": {}})
    ctrl._write_expected_watch_types(["pod"])
    return ctrl


def test_a_relevant_event_deploys_the_configuration(wired, fake_db, monkeypatch):
    log = attach_log(wired)
    wired._record_event("Ingress", "prod", "web", "ADDED")

    run_watch(wired, monkeypatch, [[evt(with_kind(k.V1Service(metadata=meta("s")), "Service"))]])

    assert fake_db.saved_configs[0]["app.example.com_USE_ANTIBOT"] == "captcha"
    assert fake_db.saved_configs[0]["USE_ANTIBOT"] == "yes"
    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert wired._first_start is False
    assert log.has("Successfully deployed new configuration", logging.INFO)
    assert log.has("Detected Kubernetes changes: Ingress prod/web (ADDED)", logging.INFO)


def test_a_change_free_event_only_syncs_status(wired, fake_db, monkeypatch):
    wired.update_needed = lambda *a, **k: False
    wired._sync_status = MagicMock()

    run_watch(wired, monkeypatch, [[evt(with_kind(k.V1Service(metadata=meta("s")), "Service"))]])

    wired._sync_status.assert_called_once_with()
    assert fake_db.saved_configs == []


def test_irrelevant_events_do_not_apply(wired, fake_db, monkeypatch):
    wired._first_start = False

    run_watch(wired, monkeypatch, [[evt(with_kind(pod(), "Pod"))]])

    assert fake_db.saved_configs == []
    assert wired._pending_apply is False


def test_a_busy_scheduler_delays_the_apply(wired, fake_db, monkeypatch):
    fake_db.metadata = {"is_initialized": True, "instances_changed": True}
    sleeps = []
    clock = iter(range(0, 100_000, 100))
    monkeypatch.setattr(module, "time", lambda: next(clock))

    def sleep(seconds):
        sleeps.append(seconds)
        fake_db.metadata = {"is_initialized": True}
        if len(sleeps) > 1:
            raise Stop

    monkeypatch.setattr(module, "sleep", sleep)
    wired._get_stream_with_retries = lambda *a: iter([evt(with_kind(k.V1Service(metadata=meta("s")), "Service"))])
    log = attach_log(wired)

    with pytest.raises(Stop):
        wired._watch("pod", "lister")

    assert sleeps[0] == 1
    assert len(fake_db.saved_configs) == 1
    assert log.has("Scheduler is already applying a configuration, retrying in 1 second", logging.INFO)


def test_apply_failures_and_exceptions_are_reported(wired, fake_db, monkeypatch):
    log = attach_log(wired)
    wired.apply_config = lambda force=False: False
    service = with_kind(k.V1Service(metadata=meta("s")), "Service")

    run_watch(wired, monkeypatch, [[evt(service)]])
    assert log.has("Error while deploying new configuration", logging.ERROR)

    def boom(force=False):
        raise RuntimeError("db gone")

    wired.apply_config = boom
    wired.update_needed = lambda *a, **k: True
    run_watch(wired, monkeypatch, [[evt(service)]])
    assert log.has("Exception while deploying new configuration :\ndb gone", logging.ERROR)
    assert fake_db.set_metadata_calls == []
    assert wired._internal_lock.acquire(timeout=0.1)


def test_api_errors_while_reading_events_are_retried_but_expiry_is_not_an_error(wired, monkeypatch):
    log = attach_log(wired)

    run_watch(wired, monkeypatch, [ApiException(status=410, reason="gone")])
    assert not log.has("API exception while reading k8s event")

    run_watch(wired, monkeypatch, [ApiException(status=500, reason="boom")])
    assert log.has("API exception while reading k8s event (type = pod)", logging.ERROR)

    run_watch(wired, monkeypatch, [RuntimeError("weird")])
    assert log.has("Unknown exception while reading k8s event (type = pod)", logging.ERROR)


def test_process_events_runs_one_thread_per_watcher_and_the_backend_worker(ctrl, healthy_dir, monkeypatch):
    ctrl.watchers = {"pod": "l1", "service": "l2"}
    started, joined = [], []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=False):
            self.target, self.args, self.daemon = target, args, daemon

        def start(self):
            started.append((self.target.__name__, self.args, self.daemon))

        def join(self):
            joined.append(self.args)

    monkeypatch.setattr(module, "Thread", FakeThread)
    ctrl._start_settings_recheck_worker = lambda: started.append(("recheck", (), None))
    ctrl._start_lock_watchdog = lambda path: started.append(("watchdog", (path,), None))

    ctrl.process_events()

    assert ("_pending_backends_worker", (), True) in started
    assert ("_watch", ("pod", "l1"), False) in started and ("_watch", ("service", "l2"), False) in started
    assert [a for a in joined] == [("pod", "l1"), ("service", "l2")]
    assert ("watchdog", (healthy_dir / "autoconf.healthy",), None) in started
    assert (healthy_dir / "autoconf.healthy.expected").read_text() == "pod\nservice\n"


def test_base_class_has_no_watchers_and_no_status_patching():
    with pytest.raises(NotImplementedError):
        KubernetesController._get_watchers(None)
    with pytest.raises(NotImplementedError):
        KubernetesController._patch_controller_status(None, ["1.2.3.4"])


# --- reverse proxy helpers ------------------------------------------------------------------------------


def test_reverse_proxy_url_is_checked_against_the_setting_regex(ctrl):
    assert ctrl._is_valid_reverse_proxy_url("anything") is True

    ctrl._settings = {"REVERSE_PROXY_URL": {"regex": r"^/[\w/]*$"}}

    assert ctrl._is_valid_reverse_proxy_url("/api/v1") is True
    assert ctrl._is_valid_reverse_proxy_url("api") is False
    assert ctrl._is_valid_reverse_proxy_url("/a b") is False


def test_missing_backend_is_queued_once(ctrl, monkeypatch):
    monkeypatch.setattr(module, "time", lambda: 1000.0)

    ctrl.note_missing_backend("prod", "api")
    ctrl.note_missing_backend("prod", "api")
    ctrl.note_missing_backend("", "api")
    ctrl.note_missing_backend("prod", "")

    assert ctrl._pending_backends == {("prod", "api"): {"attempts": 0.0, "next_retry_at": 1001.0}}


# --- the pending-backend worker -------------------------------------------------------------------------


def run_backend_worker(ctrl, monkeypatch, now=1000.0):
    ctrl._trigger_apply_if_idle = MagicMock()
    ctrl._retry_deferred_apply = MagicMock()
    monkeypatch.setattr(module, "time", lambda: now)

    def stop(_seconds):
        raise Stop

    monkeypatch.setattr(module, "sleep", stop)
    with pytest.raises(Stop):
        ctrl._pending_backends_worker()


def test_visible_backend_leaves_the_queue_and_triggers_an_apply(ctrl, monkeypatch):
    ctrl._pending_backends = {("prod", "api"): {"attempts": 2.0, "next_retry_at": 0.0}}
    ctrl._corev1.list_namespaced_service.return_value = SimpleNamespace(items=[object()])
    log = attach_log(ctrl)

    run_backend_worker(ctrl, monkeypatch)

    assert ctrl._pending_backends == {}
    assert ctrl._pending_apply is True
    assert ctrl._last_event_time == 1000.0 - ctrl._debounce_delay - 1
    ctrl._trigger_apply_if_idle.assert_called_once_with()
    assert log.has("Pending backend prod/api is now visible", logging.INFO)


def test_backend_not_yet_due_is_left_alone(ctrl, monkeypatch):
    ctrl._pending_backends = {("prod", "api"): {"attempts": 0.0, "next_retry_at": 5000.0}}

    run_backend_worker(ctrl, monkeypatch)

    ctrl._corev1.list_namespaced_service.assert_not_called()
    assert ctrl._pending_backends[("prod", "api")]["attempts"] == 0.0


def test_missing_backend_backs_off_exponentially(ctrl, monkeypatch):
    ctrl._pending_backends = {("prod", "api"): {"attempts": 1.0, "next_retry_at": 0.0}}
    ctrl._corev1.list_namespaced_service.return_value = SimpleNamespace(items=[])

    run_backend_worker(ctrl, monkeypatch)

    assert ctrl._pending_backends[("prod", "api")] == {"attempts": 2.0, "next_retry_at": 1000.0 + 1.0 * 2**2}


def test_backend_is_dropped_after_the_last_attempt(ctrl, monkeypatch):
    ctrl._pending_backends = {("prod", "api"): {"attempts": 4.0, "next_retry_at": 0.0}}
    ctrl._corev1.list_namespaced_service.side_effect = RuntimeError("api down")
    log = attach_log(ctrl)

    run_backend_worker(ctrl, monkeypatch)

    assert ctrl._pending_backends == {}
    assert log.has("Giving up on pending backend prod/api after 5 attempts", logging.WARNING)
    ctrl._trigger_apply_if_idle.assert_not_called()


def test_worker_logs_and_survives_an_unexpected_error(ctrl, monkeypatch):
    ctrl._pending_backends_lock = None
    log = attach_log(ctrl)

    run_backend_worker(ctrl, monkeypatch)

    assert log.has("Error in pending backends worker", logging.ERROR)


def test_deferred_apply_waits_for_its_time(ctrl, monkeypatch):
    ctrl._trigger_apply_if_idle = MagicMock()
    monkeypatch.setattr(module, "time", lambda: 100.0)

    ctrl._retry_deferred_apply()
    ctrl._apply_retry_at = 150.0
    ctrl._retry_deferred_apply()
    ctrl._trigger_apply_if_idle.assert_not_called()

    ctrl._apply_retry_at = 100.0
    ctrl._retry_deferred_apply()
    ctrl._trigger_apply_if_idle.assert_called_once_with()
    assert ctrl._apply_retry_at is None


# --- _trigger_apply_if_idle -----------------------------------------------------------------------------


@pytest.fixture
def idle(wired):
    wired._pending_apply = True
    return wired


def test_trigger_does_nothing_without_a_pending_apply(wired, fake_db):
    wired._pending_apply = False

    wired._trigger_apply_if_idle()

    assert fake_db.saved_configs == []


def test_trigger_applies_the_recovered_configuration(idle, fake_db):
    log = attach_log(idle)

    idle._trigger_apply_if_idle()

    assert fake_db.saved_configs[0]["app.example.com_USE_ANTIBOT"] == "captcha"
    assert idle._pending_apply is False
    assert fake_db.set_metadata_calls == [{"autoconf_loaded": True}]
    assert log.has("Backend retry worker: successfully deployed recovered configuration", logging.INFO)


def test_trigger_skips_an_unchanged_configuration(idle, fake_db):
    idle.update_needed = lambda *a, **k: False
    idle._sync_status = MagicMock()

    idle._trigger_apply_if_idle()

    idle._sync_status.assert_called_once_with()
    assert fake_db.saved_configs == []


def test_trigger_defers_while_the_scheduler_is_busy(idle, fake_db, monkeypatch):
    fake_db.metadata = {"is_initialized": True, "custom_configs_changed": True}
    monkeypatch.setattr(module, "time", lambda: 500.0)

    idle._trigger_apply_if_idle()

    assert idle._pending_apply is True
    assert idle._apply_retry_at == 501.0
    assert fake_db.saved_configs == []


def test_trigger_reports_a_failed_or_crashing_apply(idle, fake_db):
    log = attach_log(idle)
    idle.apply_config = lambda force=False: False
    idle._trigger_apply_if_idle()
    assert log.has("Backend retry worker: error while deploying new configuration", logging.ERROR)

    idle._pending_apply = True

    def boom(force=False):
        raise RuntimeError("db gone")

    idle.apply_config = boom
    idle._trigger_apply_if_idle()
    assert log.has("Backend retry worker: exception while deploying new configuration: db gone", logging.ERROR)

    idle._pending_apply = True
    idle.get_instances = MagicMock(side_effect=ValueError("late"))
    idle._trigger_apply_if_idle()
    assert log.has("Backend retry worker: unexpected error: late", logging.ERROR)


# --- load balancer address ------------------------------------------------------------------------------


def lb_service(type_="LoadBalancer", ingress=None, lb=True, status=True, spec=True):
    status_obj = k.V1ServiceStatus(load_balancer=k.V1LoadBalancerStatus(ingress=ingress) if lb else None) if status else None
    return k.V1Service(spec=k.V1ServiceSpec(type=type_) if spec else None, status=status_obj)


def node(*addresses):
    return k.V1Node(status=k.V1NodeStatus(addresses=[k.V1NodeAddress(type=t, address=a) for t, a in addresses]) if addresses else None)


def test_load_balancer_ips_and_hostnames_are_collected(ctrl):
    ctrl._corev1.read_namespaced_service.return_value = lb_service(
        ingress=[k.V1LoadBalancerIngress(ip="1.2.3.4"), k.V1LoadBalancerIngress(hostname="lb.example.com"), k.V1LoadBalancerIngress()]
    )

    assert ctrl._get_loadbalancer_ip("bunkerweb", "bunkerweb") == ["1.2.3.4", "lb.example.com"]


@pytest.mark.parametrize(
    ("service", "fragment"),
    [
        (lb_service(spec=False), "has no spec"),
        (lb_service(status=False), "has no status"),
        (lb_service(lb=False), "has no LoadBalancer status"),
        (lb_service(ingress=[]), "No ingress entries found"),
        (lb_service(ingress=[k.V1LoadBalancerIngress()]), "No IP or hostname found"),
    ],
)
def test_load_balancer_without_an_address_yields_nothing(ctrl, service, fragment):
    ctrl._corev1.read_namespaced_service.return_value = service
    log = attach_log(ctrl)

    assert ctrl._get_loadbalancer_ip("bunkerweb", "bunkerweb") is None
    assert log.has(fragment, logging.WARNING)


def test_node_port_service_returns_node_addresses_preferring_external(ctrl):
    ctrl._corev1.read_namespaced_service.return_value = lb_service("NodePort")
    ctrl._corev1.list_node.return_value = SimpleNamespace(
        items=[
            node(("InternalIP", "10.0.0.1"), ("ExternalIP", "5.5.5.5")),
            node(("InternalIP", "10.0.0.2")),
            node(),
            node(("InternalIP", "10.0.0.2")),
            node(("Hostname", "h")),
        ]
    )

    assert ctrl._get_loadbalancer_ip("bunkerweb", "bunkerweb") == ["5.5.5.5", "10.0.0.2"]


def test_node_port_service_without_usable_nodes(ctrl):
    ctrl._corev1.read_namespaced_service.return_value = lb_service("NodePort")
    log = attach_log(ctrl)

    ctrl._corev1.list_node.return_value = SimpleNamespace(items=[])
    assert ctrl._get_loadbalancer_ip("a", "b") is None
    assert log.has("No nodes found in the cluster", logging.WARNING)

    ctrl._corev1.list_node.return_value = SimpleNamespace(items=[node()])
    assert ctrl._get_loadbalancer_ip("a", "b") is None
    assert log.has("No node IPs found for NodePort service a in b", logging.WARNING)

    ctrl._corev1.list_node.side_effect = RuntimeError("denied")
    assert ctrl._get_loadbalancer_ip("a", "b") is None
    assert log.has("Error retrieving node IPs for NodePort service a in b: denied", logging.ERROR)


@pytest.mark.parametrize(
    ("error", "fragment", "level"),
    [
        (ApiException(status=404, reason="nf"), "Service a not found in namespace b", logging.WARNING),
        (ApiException(status=500, reason="boom"), "API error retrieving service a in b: 500 - boom", logging.ERROR),
        (RuntimeError("x"), "Unexpected error retrieving LoadBalancer IP for service a in b: x", logging.ERROR),
    ],
)
def test_load_balancer_lookup_errors_are_reported_not_raised(ctrl, error, fragment, level):
    ctrl._corev1.read_namespaced_service.side_effect = error
    log = attach_log(ctrl)

    assert ctrl._get_loadbalancer_ip("a", "b") is None
    assert log.has(fragment, level)


def test_load_balancer_lookup_needs_a_name_and_namespace(ctrl):
    assert ctrl._get_loadbalancer_ip("", "b") is None
    assert ctrl._get_loadbalancer_ip("a", "") is None
    ctrl._corev1.read_namespaced_service.assert_not_called()


@pytest.mark.parametrize(("value", "expected"), [("1.2.3.4", True), ("2001:db8::1", True), ("lb.example.com", False), ("1.2.3", False), ("", False)])
def test_ip_address_detection(value, expected):
    assert KubernetesController._is_ip_address(value) is expected


# --- apply_config ---------------------------------------------------------------------------------------


def test_apply_config_patches_status_only_after_a_good_apply(wired, fake_db):
    wired._instances = [{"name": "bw", "hostname": "bw", "health": True, "type": "pod", "env": {}}]
    wired._services = [{"SERVER_NAME": "app.example.com"}]
    wired._configs = {}
    wired._extra_config = {}
    wired._maybe_patch_status = MagicMock()
    wired._sync_status = MagicMock()

    assert wired.apply_config() is True
    wired._maybe_patch_status.assert_called_once_with()
    wired._sync_status.assert_called_with(True)
    assert wired._last_apply_ok is True

    fake_db.save_config = lambda *a, **k: "boom"
    wired._services = [{"SERVER_NAME": "other.example.com"}]
    wired._maybe_patch_status.reset_mock()
    assert wired.apply_config() is False
    wired._maybe_patch_status.assert_not_called()
    wired._sync_status.assert_called_with(False)


def test_apply_config_reports_a_crash_to_the_status_hook_and_reraises(wired):
    wired.apply = MagicMock(side_effect=RuntimeError("down"))
    wired._sync_status = MagicMock()

    with pytest.raises(RuntimeError):
        wired.apply_config()

    assert wired._last_apply_ok is False
    wired._sync_status.assert_called_once_with(False)


def test_status_patching_needs_an_address_and_is_opt_out(ctrl):
    ctrl._patch_controller_status = MagicMock()
    ctrl._get_loadbalancer_ip = MagicMock(return_value=None)

    ctrl._maybe_patch_status()
    ctrl._patch_controller_status.assert_not_called()

    ctrl._get_loadbalancer_ip.return_value = ["1.2.3.4"]
    ctrl._maybe_patch_status()
    ctrl._patch_controller_status.assert_called_once_with(["1.2.3.4"])

    ctrl._patch_controller_status.reset_mock()
    ctrl._status_patch_enabled = lambda: False
    ctrl._maybe_patch_status()
    ctrl._patch_controller_status.assert_not_called()


def test_progress_api_client_ticks_the_lock_after_each_call(k8s_env, monkeypatch):
    monkeypatch.setattr(k.ApiClient, "call_api", lambda self, *args, **kwargs: "result")
    lock = MagicMock()

    assert module.ProgressApiClient(lock).call_api("/x", "GET") == "result"

    lock.progress.assert_called_once_with()


def test_dead_peer_socket_options_cover_keepalive_and_user_timeout():
    options = module._dead_peer_socket_options()

    assert (module.SOL_SOCKET, module.SO_KEEPALIVE, 1) in options
    assert (module.IPPROTO_TCP, module.TCP_USER_TIMEOUT, 60000) in options
