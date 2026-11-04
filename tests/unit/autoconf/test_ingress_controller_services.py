"""IngressController: what Ingress resources turn into, and which Ingresses are in scope at all."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log
from kubernetes import client as k
from kubernetes.client.exceptions import ApiException

import controllers.IngressController as module
from controllers.IngressController import IngressController

OURS = "bunkerweb.io/ingress-controller"


def meta(name="web", namespace="prod", annotations=None):
    return k.V1ObjectMeta(name=name, namespace=namespace, annotations=annotations)


def path(url, service="api", number=None, port_name=None, no_service=False, no_port=False):
    port = None if no_port else k.V1ServiceBackendPort(number=number, name=port_name)
    backend = k.V1IngressBackend(service=None if no_service else k.V1IngressServiceBackend(name=service, port=port))
    return k.V1HTTPIngressPath(path=url, path_type="Prefix", backend=backend)


def rule(host, *paths, http=True):
    return k.V1IngressRule(host=host, http=k.V1HTTPIngressRuleValue(paths=list(paths)) if http else None)


def ingress(name="web", namespace="prod", rules=None, annotations=None, tls=None, class_name=None):
    spec = k.V1IngressSpec(rules=rules, tls=tls, ingress_class_name=class_name)
    return k.V1Ingress(metadata=meta(name, namespace, annotations), spec=spec)


def backend_service(name="api", ports=None):
    return k.V1Service(metadata=meta(name), spec=k.V1ServiceSpec(ports=ports or [k.V1ServicePort(name="http", port=8080)]))


def ingress_class(name, controller):
    return k.V1IngressClass(metadata=k.V1ObjectMeta(name=name), spec=k.V1IngressClassSpec(controller=controller))


@pytest.fixture
def build(k8s_env, monkeypatch):
    """IngressController factory over a fake API: `services` are the Services that exist, `secrets` the TLS Secrets."""
    api = SimpleNamespace(networking=MagicMock(name="networkingv1"))
    monkeypatch.setattr(module.client, "NetworkingV1Api", lambda api_client=None: api.networking)

    used = set()

    def make(services=("api",), secrets=None, **env):
        for name in used:
            k8s_env.delenv(name, raising=False)
        used.clear()
        used.update(env)
        for name, value in env.items():
            k8s_env.setenv(name, value)
        ctrl = IngressController()
        ctrl._corev1 = MagicMock(name="corev1")
        ctrl._corev1.list_namespaced_service.side_effect = lambda namespace, **kw: SimpleNamespace(
            items=[backend_service(kw["field_selector"].split("=", 1)[1])] if kw["field_selector"].split("=", 1)[1] in services else []
        )
        ctrl._corev1.list_namespaced_secret.side_effect = lambda namespace, **kw: SimpleNamespace(
            items=[s for s in (secrets or []) if s.metadata.name == kw["field_selector"].split("=", 1)[1]]
        )
        ctrl.networking = api.networking
        return ctrl

    make.api = api  # type: ignore[attr-defined]
    return make


def serve(ctrl, *ingresses):
    ctrl.networking.list_ingress_for_all_namespaces.return_value = SimpleNamespace(items=list(ingresses))
    return ctrl._get_controller_services()


# --- ingress to service -----------------------------------------------------------------------------------


def test_host_and_path_become_a_reverse_proxy_service(build):
    ctrl = build()

    assert ctrl._to_services(ingress(rules=[rule("app.example.com", path("/api", number=8080))])) == [
        {
            "SERVER_NAME": "app.example.com",
            "NAMESPACE": "prod",
            "USE_REVERSE_PROXY": "yes",
            "REVERSE_PROXY_HOST_1": "http://api.prod.svc.cluster.local:8080",
            "REVERSE_PROXY_URL_1": "/api",
        }
    ]


def test_port_80_is_left_implicit_and_protocol_and_domain_follow_the_environment(build):
    ctrl = build(KUBERNETES_SERVICE_PROTOCOL="https", KUBERNETES_DOMAIN_NAME="corp.local")

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", number=80))]))

    assert svc["REVERSE_PROXY_HOST_1"] == "https://api.prod.svc.corp.local"


def test_named_ports_are_resolved_through_the_backend_service(build):
    ctrl = build()
    ctrl._corev1.list_namespaced_service.side_effect = lambda namespace, **kw: SimpleNamespace(
        items=[backend_service("api", [k.V1ServicePort(name="grpc", port=9000), k.V1ServicePort(name="web", port=8081)])]
    )

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", port_name="web"))]))
    [unknown] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", port_name="nope"))]))

    assert svc["REVERSE_PROXY_HOST_1"] == "http://api.prod.svc.cluster.local:8081"
    assert unknown["REVERSE_PROXY_HOST_1"] == "http://api.prod.svc.cluster.local"


def test_several_paths_get_consecutive_suffixes_from_the_configured_start(build):
    ctrl = build(KUBERNETES_REVERSE_PROXY_SUFFIX_START="0", services=("api", "web"))

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/api", "api", 8080), path("/", "web", 80))]))

    assert svc["REVERSE_PROXY_HOST"] == "http://api.prod.svc.cluster.local:8080"
    assert svc["REVERSE_PROXY_URL"] == "/api"
    assert svc["REVERSE_PROXY_HOST_1"] == "http://web.prod.svc.cluster.local"
    assert svc["REVERSE_PROXY_URL_1"] == "/"


def test_each_host_is_its_own_service(build):
    ctrl = build()

    services = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", number=80)), rule("b.example.com", path("/", number=80))]))

    assert [s["SERVER_NAME"] for s in services] == ["a.example.com", "b.example.com"]


def test_rule_without_http_keeps_just_the_host(build):
    ctrl = build()

    assert ctrl._to_services(ingress(rules=[rule("a.example.com", http=False)])) == [{"SERVER_NAME": "a.example.com", "NAMESPACE": "prod"}]


def test_ingress_without_rules_or_spec_serves_nothing(build):
    ctrl = build()
    bare = k.V1Ingress(metadata=meta())

    assert ctrl._to_services(bare) == []
    assert ctrl._to_services(ingress(rules=[])) == []


@pytest.mark.parametrize(
    ("bad_path", "fragment"),
    [
        (path("", number=80), "rule without path"),
        (path("/x", no_service=True), "rule without backend service."),
        (path("/x", no_port=True), "rule without backend service port"),
    ],
)
def test_unsupported_paths_are_skipped_with_a_warning(build, bad_path, fragment):
    ctrl = build()
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", bad_path)]))

    assert svc == {"SERVER_NAME": "a.example.com", "NAMESPACE": "prod"}
    assert log.has(fragment, logging.WARNING)


def test_host_less_rule_is_ignored(build):
    ctrl = build()
    log = attach_log(ctrl)

    assert ctrl._to_services(ingress(rules=[rule(None, path("/", number=80))])) == []
    assert log.has("Ignoring unsupported ingress rule without host", logging.WARNING)


def test_path_rejected_by_the_reverse_proxy_url_regex_is_skipped(build):
    ctrl = build()
    ctrl._settings = {"REVERSE_PROXY_URL": {"regex": r"^/[\w/]*$"}}
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("api", number=80))]))

    assert "REVERSE_PROXY_URL_1" not in svc
    assert log.has("not a valid REVERSE_PROXY_URL", logging.WARNING)


def test_missing_backend_service_is_skipped_and_queued_for_retry(build):
    ctrl = build(services=())
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(ingress(rules=[rule("a.example.com", path("/", "ghost", 80))]))

    assert "USE_REVERSE_PROXY" not in svc
    assert ("prod", "ghost") in ctrl._pending_backends
    assert log.has("service ghost : service not found", logging.WARNING)


# --- annotations ------------------------------------------------------------------------------------------


def annotated(annotations, **kw):
    return ingress(rules=[rule("a.example.com", path("/", number=80))], annotations=annotations, **kw)


def test_annotations_become_prefixed_settings(build):
    ctrl = build()

    [svc] = ctrl._to_services(annotated({"bunkerweb.io/USE_ANTIBOT": "captcha", "other.io/x": "y", "kubernetes.io/foo": "bar"}))

    assert svc["a.example.com_USE_ANTIBOT"] == "captcha"
    assert "other.io/x" not in svc and "x" not in svc


def test_unknown_settings_are_kept_verbatim_for_the_later_validation(build):
    ctrl = build()

    [svc] = ctrl._to_services(annotated({"bunkerweb.io/NOT_A_SETTING": "1"}))

    assert svc["NOT_A_SETTING"] == "1"


def test_server_name_cannot_be_set_through_an_annotation(build):
    ctrl = build()
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(annotated({"bunkerweb.io/SERVER_NAME": "evil.example.com"}))

    assert svc["SERVER_NAME"] == "a.example.com"
    assert log.has("SERVER_NAME can't be set globally via annotations", logging.WARNING)


def test_stream_service_keeps_only_the_first_reverse_proxy_without_protocol(build):
    ctrl = build()
    log = attach_log(ctrl)
    annotations = {
        "bunkerweb.io/a.example.com_SERVER_TYPE": "stream",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_HOST": "http://first:1",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_HOST_2": "http://second:2",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_URL_2": "/two",
    }

    [svc] = ctrl._to_services(annotated(annotations))

    assert svc["a.example.com_REVERSE_PROXY_HOST"] == "first:1"
    assert svc["a.example.com_REVERSE_PROXY_URL"] == "/"
    assert "a.example.com_REVERSE_PROXY_HOST_2" not in svc
    assert "a.example.com_REVERSE_PROXY_URL_2" not in svc
    assert log.has("Service a.example.com is a stream service", logging.WARNING)


# --- TLS --------------------------------------------------------------------------------------------------


def tls_secret(data):
    return k.V1Secret(metadata=meta("cert"), data=data)


def tls_ingress(hosts=("a.example.com",), secret_name="cert"):
    return ingress(rules=[rule("a.example.com", path("/", number=80))], tls=[k.V1IngressTLS(hosts=list(hosts), secret_name=secret_name)])


def test_tls_secret_becomes_a_custom_certificate(build):
    ctrl = build(secrets=[tls_secret({"tls.crt": "CERT", "tls.key": "KEY"})])

    [svc] = ctrl._to_services(tls_ingress())

    assert (svc["USE_CUSTOM_SSL"], svc["CUSTOM_SSL_CERT_DATA"], svc["CUSTOM_SSL_KEY_DATA"]) == ("yes", "CERT", "KEY")


@pytest.mark.parametrize(
    ("secrets", "fragment"),
    [
        ([], "secret cert not found"),
        ([tls_secret(None)], "secret cert contains no data"),
        ([tls_secret({"tls.crt": "CERT"})], "secret cert is missing tls data"),
    ],
)
def test_unusable_tls_secret_leaves_the_service_without_a_certificate(build, secrets, fragment):
    ctrl = build(secrets=secrets)
    log = attach_log(ctrl)

    [svc] = ctrl._to_services(tls_ingress())

    assert "USE_CUSTOM_SSL" not in svc
    assert log.has(fragment, logging.WARNING)


def test_tls_entry_for_another_host_does_not_apply(build):
    ctrl = build(secrets=[tls_secret({"tls.crt": "CERT", "tls.key": "KEY"})])

    [svc] = ctrl._to_services(tls_ingress(hosts=("other.example.com",)))

    assert "USE_CUSTOM_SSL" not in svc


# --- scope: which Ingresses are served (QAR Q8) -----------------------------------------------------------


def web(name, namespace="prod", class_name=None, annotations=None):
    return ingress(name, namespace, [rule(f"{name}.example.com", path("/", number=80))], annotations, class_name=class_name)


def names(services):
    return [i.metadata.name for i in services]


def test_every_ingress_is_served_without_any_scope(build):
    ctrl = build()

    assert names(serve(ctrl, web("b"), web("a", "dev"), web("c", class_name="nginx"))) == ["a", "b", "c"]


def test_ingresses_are_sorted_by_namespace_then_name(build):
    ctrl = build()

    got = serve(ctrl, web("z", "alpha"), web("b", "beta"), web("a", "beta"))

    assert [(i.metadata.namespace, i.metadata.name) for i in got] == [("alpha", "z"), ("beta", "a"), ("beta", "b")]


def test_configured_ingress_class_excludes_every_other_ingress(build):
    ctrl = build(KUBERNETES_INGRESS_CLASS="bunkerweb")

    got = serve(ctrl, web("mine", class_name="bunkerweb"), web("nginx", class_name="nginx"), web("classless"))

    assert names(got) == ["mine"]


def test_annotation_class_does_not_satisfy_a_configured_class(build):
    ctrl = build(KUBERNETES_INGRESS_CLASS="bunkerweb")

    got = serve(ctrl, web("legacy", annotations={"kubernetes.io/ingress.class": "bunkerweb"}))

    assert got == []


def test_namespaces_scope_excludes_other_namespaces(build):
    ctrl = build(NAMESPACES="prod")

    assert names(serve(ctrl, web("in", "prod"), web("out", "dev"))) == ["in"]


def test_ignored_annotation_excludes_the_ingress(build):
    ctrl = build(KUBERNETES_IGNORE_ANNOTATIONS="skip")

    assert names(serve(ctrl, web("kept"), web("skipped", annotations={"bunkerweb.io/skip": "1"}))) == ["kept"]


def classes_env(build, classes, **env):
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes", **env)
    ctrl.networking.list_ingress_class.return_value = SimpleNamespace(items=classes)
    return ctrl


def test_foreign_classes_are_skipped_when_the_option_is_on(build):
    api = build.api.networking
    api.list_ingress_class.return_value = SimpleNamespace(items=[ingress_class("nginx", "k8s.io/ingress-nginx"), ingress_class("bw", OURS)])
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    assert ctrl._ingress_classes_readable is True

    got = serve(
        ctrl,
        web("by-spec", class_name="nginx"),
        web("by-annotation", annotations={"kubernetes.io/ingress.class": "nginx"}),
        web("ours", class_name="bw"),
        web("classless"),
        web("unknown-class", class_name="not-listed"),
    )

    assert names(got) == ["classless", "ours", "unknown-class"]


def test_foreign_classes_are_served_when_the_option_is_off(build):
    api = build.api.networking
    api.list_ingress_class.return_value = SimpleNamespace(items=[ingress_class("nginx", "k8s.io/ingress-nginx")])
    ctrl = build()

    assert ctrl._ingress_classes_readable is False
    assert names(serve(ctrl, web("n", class_name="nginx"))) == ["n"]


def test_an_unreadable_class_list_falls_back_to_serving_everything_with_one_warning(build):
    build.api.networking.list_ingress_class.side_effect = ApiException(status=403, reason="Forbidden")
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    log = attach_log(ctrl)

    assert ctrl._ingress_classes_readable is False
    assert names(serve(ctrl, web("n", class_name="nginx"))) == ["n"]
    ctrl._warn_ingress_classes("again")
    assert not log.has("again")
    assert ctrl._probe_ingress_classes() is False


def test_probe_reports_unexpected_errors_too(build):
    build.api.networking.list_ingress_class.side_effect = OSError("no route")
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")

    assert ctrl._ingress_classes_readable is False


def test_a_failing_class_listing_reuses_the_last_known_foreign_set(build):
    api = build.api.networking
    api.list_ingress_class.return_value = SimpleNamespace(items=[ingress_class("nginx", "k8s.io/ingress-nginx")])
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    assert names(serve(ctrl, web("n", class_name="nginx"), web("o"))) == ["o"]

    api.list_ingress_class.side_effect = RuntimeError("api down")
    log = attach_log(ctrl)

    assert names(serve(ctrl, web("n", class_name="nginx"), web("o"))) == ["o"]
    assert log.has("Can't list ingressclasses: api down", logging.ERROR)


def test_a_configured_class_disables_the_foreign_class_probe(build):
    ctrl = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes", KUBERNETES_INGRESS_CLASS="bunkerweb")

    assert ctrl._ingress_classes_readable is False
    ctrl.networking.list_ingress_class.assert_not_called()


# --- events -----------------------------------------------------------------------------------------------


def test_ingress_class_events_matter_only_when_classes_are_readable(build):
    build.api.networking.list_ingress_class.return_value = SimpleNamespace(items=[])
    on = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    off = build()

    assert on._is_custom_event("IngressClass", None, None, None, "x") is True
    assert off._is_custom_event("IngressClass", None, None, None, "x") is False
    assert off._is_custom_event("Gateway", None, None, "prod", "x") is False


def test_ingress_events_follow_ownership(build):
    ctrl = build(KUBERNETES_INGRESS_CLASS="bunkerweb")
    mine, other = web("mine", class_name="bunkerweb"), web("other", class_name="nginx")

    assert ctrl._is_custom_event("Ingress", mine, {}, "prod", "mine") is True
    assert ctrl._is_custom_event("Ingress", other, {}, "prod", "other") is False


def test_an_ingress_adopted_by_the_last_relist_is_re_evaluated_even_when_it_changed_class(build):
    ctrl = build(KUBERNETES_INGRESS_CLASS="bunkerweb")
    serve(ctrl, web("mine", class_name="bunkerweb"))
    moved = web("mine", class_name="nginx")

    assert ctrl._is_custom_event("Ingress", moved, {}, "prod", "mine") is True


def test_watchers_include_ingress_classes_only_when_readable(build):
    build.api.networking.list_ingress_class.return_value = SimpleNamespace(items=[])
    on = build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")

    assert set(on._get_watchers()) == {"pod", "ingress", "configmap", "service", "secret", "ingressclass"}
    assert set(build()._get_watchers()) == {"pod", "ingress", "configmap", "service", "secret"}


# --- status -----------------------------------------------------------------------------------------------


def test_status_patch_writes_ips_and_hostnames(build):
    ctrl = build()

    assert ctrl._patch_ingress_status(web("a"), ["1.2.3.4", "2001:db8::1", "lb.example.com"]) is True

    ctrl.networking.patch_namespaced_ingress_status.assert_called_once_with(
        name="a",
        namespace="prod",
        body={"status": {"loadBalancer": {"ingress": [{"ip": "1.2.3.4"}, {"ip": "2001:db8::1"}, {"hostname": "lb.example.com"}]}}},
        _request_timeout=module.API_REQUEST_TIMEOUT,
    )


def test_status_patch_refuses_bad_input(build):
    ctrl = build()
    log = attach_log(ctrl)

    assert ctrl._patch_ingress_status(web("a"), []) is False
    assert ctrl._patch_ingress_status(None, ["1.2.3.4"]) is False
    assert ctrl._patch_ingress_status(k.V1Ingress(), ["1.2.3.4"]) is False
    assert ctrl._patch_ingress_status(ingress(name="", namespace="prod"), ["1.2.3.4"]) is False
    ctrl.networking.patch_namespaced_ingress_status.assert_not_called()
    assert log.has("Cannot patch ingress without IP addresses", logging.WARNING)
    assert log.has("Ingress name or namespace is empty", logging.ERROR)


@pytest.mark.parametrize(
    ("error", "fragment", "level"),
    [
        (ApiException(status=404, reason="nf"), "not found in namespace prod, skipping status patch", logging.WARNING),
        (ApiException(status=403, reason="no"), "Insufficient permissions to patch ingress a status", logging.WARNING),
        (ApiException(status=422, reason="bad"), "Invalid patch data for ingress a in namespace prod: bad", logging.ERROR),
        (ApiException(status=500, reason="boom"), "API error patching ingress a in namespace prod: 500 - boom", logging.ERROR),
        (RuntimeError("x"), "Unexpected error patching ingress a in namespace prod: x", logging.ERROR),
    ],
)
def test_status_patch_failures_are_contained(build, error, fragment, level):
    ctrl = build()
    ctrl.networking.patch_namespaced_ingress_status.side_effect = error
    log = attach_log(ctrl)

    assert ctrl._patch_ingress_status(web("a"), ["1.2.3.4"]) is False
    assert log.has(fragment, level)


def test_controller_status_goes_to_owned_ingresses_only(build):
    ctrl = build(KUBERNETES_INGRESS_CLASS="bunkerweb")
    ctrl.networking.list_ingress_for_all_namespaces.return_value = SimpleNamespace(
        items=[web("mine", class_name="bunkerweb"), web("theirs", class_name="nginx")]
    )

    ctrl._patch_controller_status(["1.2.3.4"])

    [call] = ctrl.networking.patch_namespaced_ingress_status.call_args_list
    assert call.kwargs["name"] == "mine"
