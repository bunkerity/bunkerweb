"""GatewayController: Gateway API discovery, which Gateways and Routes are in scope, and what each Route kind turns into."""

import logging
from unittest.mock import MagicMock

import pytest
from _autoconf_helpers import attach_log
from kubernetes import client as k
from kubernetes.client.exceptions import ApiException

import controllers.GatewayController as module
from gateway_fakes import ALL_PLURALS, OURS, backend, crds, gateway_class, gw, route, served

# --- discovery --------------------------------------------------------------------------------------------


def test_every_served_resource_is_detected(gateway_build):
    ctrl = gateway_build()

    assert ctrl._resource_versions == {plural: "v1" for plural in ALL_PLURALS}
    assert ctrl._gateway_api_available is True
    assert ctrl._status_enabled is True
    assert set(ctrl._get_watchers()) == {
        "pod",
        "configmap",
        "service",
        "secret",
        "gateway",
        "httproute",
        "grpcroute",
        "tlsroute",
        "tcproute",
        "udproute",
        "gatewayclass",
    }


def test_fallback_version_is_reported_and_kept(gateway_build):
    ctrl = gateway_build(crds(("v1beta1",)))

    assert ctrl._resource_versions["gateways"] == "v1beta1"
    assert ctrl._gateway_api_version == "v1beta1"
    assert ("v1", "gateways") in ctrl.api.list_calls and ("v1beta1", "gateways") in ctrl.api.list_calls


def test_the_preferred_version_is_tried_first(gateway_build):
    ctrl = gateway_build(crds(("v1", "v1alpha2")), KUBERNETES_GATEWAY_API_VERSION="v1alpha2")

    assert ctrl.api.list_calls[0] == ("v1alpha2", "gateways")
    assert ctrl._resource_versions["gateways"] == "v1alpha2"


def test_unsupported_configured_version_defaults_to_v1(gateway_build):
    ctrl = gateway_build(KUBERNETES_GATEWAY_API_VERSION="v9")

    assert ctrl._resource_versions["gateways"] == "v1"


def test_without_the_crds_the_controller_idles(gateway_build):
    ctrl = gateway_build({})

    assert ctrl._gateway_api_available is False
    assert ctrl._status_enabled is False
    assert ctrl._list_custom_objects("gateways") == []
    assert set(ctrl._get_watchers()) == {"pod", "configmap", "service", "secret"}
    assert ctrl._status_patch_enabled() is False


def test_missing_experimental_routes_are_skipped_with_an_install_hint(gateway_build):
    table = crds()
    for plural in ("grpcroutes", "tcproutes"):
        del table[plural]
    ctrl = gateway_build(table)

    assert "grpcroutes" not in ctrl._resource_versions
    watchers = ctrl._get_watchers()
    assert "grpcroute" not in watchers and "tcproute" not in watchers and "httproute" in watchers


def test_only_missing_standard_routes_get_no_hint(gateway_build):
    table = crds()
    del table["httproutes"]
    ctrl = gateway_build(table)

    assert "httproute" not in ctrl._get_watchers()


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (ApiException(status=403, reason="Forbidden"), "Insufficient permissions to access gateways in Gateway API v1"),
        (ApiException(status=500, reason="Oops"), "Error while probing gateways in Gateway API v1: 500 - Oops"),
        (RuntimeError("tls"), "Unexpected error while probing gateways in Gateway API v1: tls"),
    ],
)
def test_probe_errors_are_reported_and_the_resource_stays_unavailable(gateway_build, error, fragment):
    table = crds()
    table["gateways"] = error

    ctrl = gateway_build(table)

    assert ctrl._gateway_api_available is False
    assert ctrl.init_log.has(fragment, logging.ERROR)


def test_gateway_classes_are_read_when_gateways_exist_and_flag_status_support(gateway_build):
    table = crds()
    del table["gatewayclasses"]
    ctrl = gateway_build(table)

    assert ctrl._status_enabled is False
    assert "gatewayclass" not in ctrl._get_watchers()


def test_foreign_class_filtering_needs_readable_classes(gateway_build):
    on = gateway_build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    off = gateway_build()
    pinned = gateway_build(KUBERNETES_SKIP_FOREIGN_CLASSES="yes", KUBERNETES_GATEWAY_CLASS="bw")

    assert (on._gateway_classes_readable, off._gateway_classes_readable, pinned._gateway_classes_readable) == (True, False, False)


def test_unreadable_classes_with_filtering_on_warn_once(gateway_build):
    table = crds()
    table["gatewayclasses"] = ApiException(status=403, reason="Forbidden")
    ctrl = gateway_build(table, KUBERNETES_SKIP_FOREIGN_CLASSES="yes")

    assert ctrl._gateway_classes_readable is False
    assert ctrl._gateway_classes_warned is True
    ctrl._warn_gateway_classes("again")
    assert ctrl._foreign_gateway_classes() is None


def test_foreign_classes_are_those_of_other_controllers(gateway_build):
    classes = [gateway_class("bw", OURS), gateway_class("istio", "istio.io/gateway-controller"), {"metadata": {}, "spec": {"controllerName": "x"}}]
    ctrl = gateway_build(crds(gatewayclasses=classes), KUBERNETES_SKIP_FOREIGN_CLASSES="yes")

    assert ctrl._foreign_gateway_classes() == {"istio"}


def test_listing_errors_are_logged_and_yield_nothing(gateway_build):
    ctrl = gateway_build()
    ctrl.api.crds["gateways"] = (("v1",), [])
    log = attach_log(ctrl)

    ctrl.api.list_cluster_custom_object = MagicMock(side_effect=ApiException(status=500, reason="boom"))
    assert ctrl._list_custom_objects("gateways") == []
    assert log.has("API error listing gateways: 500 - boom", logging.ERROR)

    ctrl.api.list_cluster_custom_object = MagicMock(side_effect=RuntimeError("x"))
    assert ctrl._list_custom_objects("gateways") == []
    assert log.has("Unexpected error listing gateways: x", logging.ERROR)

    ctrl.api.list_cluster_custom_object = MagicMock(return_value=["not", "a", "dict"])
    assert ctrl._list_custom_objects("gateways") == []
    assert ctrl._list_custom_objects("unknown-plural") == []


# --- scope: Gateways (QAR Q8) -----------------------------------------------------------------------------


def test_every_named_gateway_is_in_scope_by_default(gateway_build):
    ctrl = gateway_build()
    served(ctrl, [gw("a"), gw("b", "dev"), {"metadata": {"name": "nameless"}}, {"metadata": {"namespace": "prod"}}])

    assert set(ctrl._gateways_cache) == {("prod", "a"), ("dev", "b")}


def test_gateways_outside_the_namespaces_are_ignored(gateway_build):
    ctrl = gateway_build(NAMESPACES="prod")
    served(ctrl, [gw("in", "prod"), gw("out", "dev")])

    assert set(ctrl._gateways_cache) == {("prod", "in")}


def test_gateways_with_ignored_annotations_are_ignored(gateway_build):
    ctrl = gateway_build(KUBERNETES_IGNORE_ANNOTATIONS="skip")
    served(ctrl, [gw("kept"), gw("skipped", annotations={"bunkerweb.io/skip": "1"})])

    assert set(ctrl._gateways_cache) == {("prod", "kept")}


def test_configured_gateway_class_excludes_the_others(gateway_build):
    ctrl = gateway_build(KUBERNETES_GATEWAY_CLASS="bw")
    served(ctrl, [gw("mine", class_name="bw"), gw("theirs", class_name="istio"), gw("none", class_name=None)])

    assert set(ctrl._gateways_cache) == {("prod", "mine")}


def test_foreign_class_gateways_are_skipped_when_the_option_is_on(gateway_build):
    classes = [gateway_class("bw", OURS), gateway_class("istio", "istio.io/gateway-controller")]
    ctrl = gateway_build(crds(gatewayclasses=classes), KUBERNETES_SKIP_FOREIGN_CLASSES="yes")
    served(ctrl, [gw("mine", class_name="bw"), gw("theirs", class_name="istio"), gw("unlisted", class_name="mystery")], classes=classes)

    assert set(ctrl._gateways_cache) == {("prod", "mine"), ("prod", "unlisted")}


# --- scope: Routes (QAR Q8) -------------------------------------------------------------------------------


def test_only_routes_attached_to_an_allowed_gateway_are_served(gateway_build):
    ctrl = gateway_build()
    mine = route(name="mine")
    cross_ns = route(name="cross", namespace="apps", parents=[{"name": "gw", "namespace": "prod"}])
    wrong_ns = route(name="wrong", namespace="apps", parents=[{"name": "gw"}])
    stranger = route(name="stranger", parents=[{"name": "other-gw"}])
    orphan = route(name="orphan", parents=[])
    junk = route(name="junk", parents=["gw", {"name": ""}, {"name": "gw", "namespace": "nowhere"}])

    routes = served(ctrl, [gw()], mine, cross_ns, wrong_ns, stranger, orphan, junk)

    assert [r["metadata"]["name"] for r in routes] == ["cross", "mine"]


def test_routes_of_a_foreign_gateway_class_are_not_served(gateway_build):
    ctrl = gateway_build(KUBERNETES_GATEWAY_CLASS="bw")

    routes = served(
        ctrl,
        [gw("mine", class_name="bw"), gw("theirs", class_name="istio")],
        route(name="a", parents=[{"name": "mine"}]),
        route(name="b", parents=[{"name": "theirs"}]),
    )

    assert [r["metadata"]["name"] for r in routes] == ["a"]


def test_route_namespaces_and_ignored_annotations_are_enforced(gateway_build):
    ctrl = gateway_build(NAMESPACES="prod", KUBERNETES_IGNORE_ANNOTATIONS="skip")

    routes = served(
        ctrl,
        [gw()],
        route(name="ok"),
        route(name="skipped", annotations={"bunkerweb.io/skip": "1"}),
        route(name="out", namespace="dev", parents=[{"name": "gw", "namespace": "prod"}]),
        {"kind": "HTTPRoute", "metadata": {"name": "", "namespace": "prod"}, "spec": {}},
    )

    assert [r["metadata"]["name"] for r in routes] == ["ok"]


def test_routes_of_every_kind_are_collected_and_sorted(gateway_build):
    ctrl = gateway_build()

    routes = served(ctrl, [gw()], route("TCPRoute", "t"), route("HTTPRoute", "b"), route("GRPCRoute", "a", namespace="prod"))

    assert [r["metadata"]["name"] for r in routes] == ["a", "b", "t"]
    assert ctrl._routes_cache == routes
    assert ctrl._get_controller_services() == routes


# --- listener helpers -------------------------------------------------------------------------------------


def test_listener_selection_follows_section_hostname_and_protocol(gateway_build):
    ctrl = gateway_build()
    listeners = [
        {"name": "web", "port": 80, "protocol": "HTTP", "hostname": "*.example.com"},
        {"name": "secure", "port": 443, "protocol": "HTTPS", "hostname": "app.example.com"},
        {"name": "raw", "port": 9000, "protocol": "TCP"},
    ]
    served(ctrl, [gw(listeners=listeners)])
    r = route()

    def names(**kw):
        return [listener["name"] for listener, _, _ in ctrl._get_route_listeners(r, **kw)]

    assert names() == ["web", "secure", "raw"]
    assert names(hostname="app.example.com") == ["web", "secure", "raw"]
    assert names(hostname="other.org") == ["raw"]
    assert names(protocols=["https", "tcp"]) == ["secure", "raw"]
    assert [listener["name"] for listener, _, _ in ctrl._get_route_listeners(route(parents=[{"name": "gw", "sectionName": "raw"}]))] == ["raw"]
    assert ctrl._get_route_listeners(route(parents=["x", {"name": ""}, {"name": "ghost"}])) == []


def test_hostname_matching_is_case_insensitive_and_wildcard_aware(gateway_build):
    ctrl = gateway_build()

    assert ctrl._hostname_matches("API.Example.com", "*.example.com") is True
    assert ctrl._hostname_matches("example.org", "*.example.com") is False
    assert ctrl._hostname_matches("anything", None) is True


def test_listener_protocol_precedence(gateway_build):
    ctrl = gateway_build()
    served(ctrl, [gw(listeners=[{"name": "a", "protocol": "HTTP"}, {"name": "b", "protocol": "HTTPS"}, {"name": "c", "protocol": "TCP"}])])
    r = route()

    assert ctrl._get_listener_protocol(r, "h") == "TCP"
    assert ctrl._get_listener_protocol(r, "h", ["HTTP", "HTTPS"]) == "HTTPS"
    assert ctrl._get_listener_protocol(r, "h", ["HTTP"]) == "HTTP"
    assert ctrl._get_listener_protocol(r, "h", ["UDP"]) == ""


def test_unknown_listener_protocol_falls_back_to_the_service_protocol(gateway_build):
    ctrl = gateway_build(KUBERNETES_SERVICE_PROTOCOL="https")
    served(ctrl, [gw(listeners=[{"name": "a", "protocol": "FANCY"}])])

    assert ctrl._get_listener_protocol(route(), "h") == "HTTPS"


def test_listener_port_and_hostnames(gateway_build):
    ctrl = gateway_build()
    served(
        ctrl,
        [
            gw(
                listeners=[
                    {"name": "a", "port": 8080, "protocol": "HTTP", "hostname": "x.example.com"},
                    {"name": "b", "port": 9090, "protocol": "HTTP", "hostname": "x.example.com"},
                    {"name": "c", "protocol": "HTTP"},
                ]
            )
        ],
    )
    log = attach_log(ctrl)

    assert ctrl._get_listener_port(route()) == 8080
    assert log.has("Multiple listener ports found for prod/r, using the first one", logging.WARNING)
    assert ctrl._get_listener_hostnames(route()) == ["x.example.com"]
    assert ctrl._get_listener_port(route(parents=[{"name": "gw", "sectionName": "c"}])) is None
    assert ctrl._get_listener_port(route(parents=[{"name": "ghost"}])) is None


def test_default_server_name(gateway_build):
    ctrl = gateway_build()

    assert ctrl._route_default_server_name("TCP", "prod", "db") == "db.prod.tcp"
    assert ctrl._route_default_server_name("tls", None, None) == "route.tls"


# --- backend refs -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("refs", "expected", "fragment"),
    [
        ([], None, "rule without backendRefs"),
        (["junk"], None, None),
        ([{"name": "a", "port": 80, "kind": "Bucket"}], None, "unsupported kind Bucket"),
        ([{"name": "a"}], None, "without name/port"),
        ([{"port": 80}], None, "without name/port"),
        ([{"name": "a", "port": 80}], ("a", 80, "prod"), None),
        ([{"name": "a", "port": 80, "namespace": "other"}], ("a", 80, "other"), None),
        ([{"name": "a", "port": 80}, {"name": "b", "port": 81}], ("a", 80, "prod"), "multiple backendRefs"),
    ],
)
def test_backend_ref_selection(gateway_build, refs, expected, fragment):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    assert ctrl._get_backend_ref(refs, "prod", "r", "HTTPRoute") == expected
    if fragment:
        assert log.has(fragment, logging.WARNING)


def test_backend_without_any_namespace_is_refused(gateway_build):
    ctrl = gateway_build()

    assert ctrl._get_backend_ref([{"name": "a", "port": 80}], None, "r", "HTTPRoute") is None


@pytest.mark.parametrize(
    ("match", "url"),
    [
        (None, "/"),
        ("x", "/"),
        ({}, "/"),
        ({"method": "x"}, "/"),
        ({"method": {"service": "pkg.Svc", "method": "Do"}}, "/pkg.Svc/Do"),
        ({"method": {"service": "/pkg.Svc/"}}, "/pkg.Svc/"),
        ({"method": {"method": "Do"}}, "/"),
    ],
)
def test_grpc_match_paths(gateway_build, match, url):
    assert gateway_build()._grpc_match_path(match) == url


# --- HTTPRoute -------------------------------------------------------------------------------------------


def http_rule(path_value="/api", backends=None, path_type="PathPrefix", matches=True):
    rule = {"backendRefs": backends if backends is not None else [backend()]}
    if matches:
        rule["matches"] = [{"path": {"type": path_type, "value": path_value}}]
    return rule


def to_services(ctrl, gateways, r, classes=None):
    served(ctrl, gateways, r, classes=classes)
    return ctrl._to_services(r)


def test_http_route_becomes_a_reverse_proxy_service(gateway_build):
    ctrl = gateway_build()

    assert to_services(ctrl, [gw()], route(hostnames=["app.example.com"], rules=[http_rule("/api")])) == [
        {
            "SERVER_NAME": "app.example.com",
            "NAMESPACE": "prod",
            "USE_REVERSE_PROXY": "yes",
            "REVERSE_PROXY_HOST_1": "http://api.prod.svc.cluster.local:8080",
            "REVERSE_PROXY_URL_1": "/api",
        }
    ]


def test_http_route_defaults_and_numbering(gateway_build):
    ctrl = gateway_build(KUBERNETES_REVERSE_PROXY_SUFFIX_START="0", KUBERNETES_SERVICE_PROTOCOL="https", KUBERNETES_DOMAIN_NAME="corp.local")
    rules = [http_rule("/a", [backend("a", 80)]), {"backendRefs": [backend("b", 81, namespace="infra")]}]

    [svc] = to_services(ctrl, [gw()], route(hostnames=["a.example.com", "b.example.com"], rules=rules))

    assert svc["SERVER_NAME"] == "a.example.com b.example.com"
    assert (svc["REVERSE_PROXY_HOST"], svc["REVERSE_PROXY_URL"]) == ("https://a.prod.svc.corp.local", "/a")
    assert (svc["REVERSE_PROXY_HOST_1"], svc["REVERSE_PROXY_URL_1"]) == ("https://b.infra.svc.corp.local:81", "/")


def test_every_match_of_a_rule_gets_its_own_location(gateway_build):
    ctrl = gateway_build()
    rule = {"backendRefs": [backend()], "matches": [{"path": {"value": "/one"}}, {"path": {"value": "/two"}}, {"headers": []}]}

    [svc] = to_services(ctrl, [gw()], route(hostnames=["a.example.com"], rules=[rule]))

    assert [svc[f"REVERSE_PROXY_URL_{n}"] for n in (1, 2, 3)] == ["/one", "/two", "/"]


def test_regular_expression_paths_are_anchored(gateway_build):
    ctrl = gateway_build()
    rules = [http_rule(r"/v\d+/.*", path_type="RegularExpression"), http_rule("^/already", path_type="RegularExpression")]

    [svc] = to_services(ctrl, [gw()], route(hostnames=["a.example.com"], rules=rules))

    assert svc["REVERSE_PROXY_URL_1"] == r"^/v\d+/.*"
    assert svc["REVERSE_PROXY_URL_2"] == "^/already"


def test_invalid_paths_and_rules_without_backends_are_skipped(gateway_build):
    ctrl = gateway_build()
    ctrl._settings = {"REVERSE_PROXY_URL": {"regex": r"^/[\w/]*$"}}
    log = attach_log(ctrl)
    rules = [http_rule("bad path"), http_rule("/ok"), {"backendRefs": []}]

    [svc] = to_services(ctrl, [gw()], route(hostnames=["a.example.com"], rules=rules))

    assert svc["REVERSE_PROXY_URL_1"] == "/ok" and "REVERSE_PROXY_URL_2" not in svc
    assert log.has("not a valid REVERSE_PROXY_URL", logging.WARNING)


def test_hostnames_come_from_the_listener_when_the_route_has_none(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)
    listener = {"name": "http", "port": 80, "protocol": "HTTP", "hostname": "listen.example.com"}

    [svc] = to_services(ctrl, [gw(listeners=[listener])], route(rules=[http_rule()]))

    assert svc["SERVER_NAME"] == "listen.example.com"
    assert log.has("HTTPRoute prod/r uses listener hostnames: listen.example.com", logging.INFO)


def test_http_route_without_any_hostname_or_listener_is_ignored(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    assert to_services(ctrl, [gw()], route(rules=[http_rule()])) == []
    assert log.has("Ignoring HTTPRoute prod/r without hostnames", logging.WARNING)


def test_http_route_on_a_tcp_only_gateway_is_ignored(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    assert to_services(ctrl, [gw(listeners=[{"name": "raw", "port": 9000, "protocol": "TCP"}])], route(hostnames=["a.example.com"], rules=[http_rule()])) == []
    assert log.has("no compatible HTTP/HTTPS/TLS listener found", logging.WARNING)


def https_gateway(secret_ref=None):
    tls = {"mode": "Terminate", "certificateRefs": [secret_ref or {"name": "cert"}]}
    return gw(listeners=[{"name": "https", "port": 443, "protocol": "HTTPS", "hostname": "app.example.com", "tls": tls}])


def tls_secret(data, namespace="prod"):
    return k.V1Secret(metadata=k.V1ObjectMeta(name="cert", namespace=namespace), data=data)


def test_listener_certificate_secret_becomes_a_custom_certificate(gateway_build):
    ctrl = gateway_build()
    ctrl._corev1.read_namespaced_secret.return_value = tls_secret({"tls.crt": "CERT", "tls.key": "KEY"})

    [svc] = to_services(ctrl, [https_gateway()], route(hostnames=["app.example.com"], rules=[http_rule()]))

    assert (svc["USE_CUSTOM_SSL"], svc["CUSTOM_SSL_CERT_DATA"], svc["CUSTOM_SSL_KEY_DATA"]) == ("yes", "CERT", "KEY")
    ctrl._corev1.read_namespaced_secret.assert_called_once_with(name="cert", namespace="prod", _request_timeout=module.API_REQUEST_TIMEOUT)


def test_certificate_refs_may_point_at_another_namespace(gateway_build):
    ctrl = gateway_build()
    ctrl._corev1.read_namespaced_secret.return_value = tls_secret({"tls.crt": "C", "tls.key": "K"}, "certs")

    to_services(ctrl, [https_gateway({"name": "cert", "namespace": "certs"})], route(hostnames=["app.example.com"], rules=[http_rule()]))

    assert ctrl._corev1.read_namespaced_secret.call_args.kwargs["namespace"] == "certs"


@pytest.mark.parametrize(
    ("secret", "fragment"),
    [
        (ApiException(status=404, reason="nf"), "Secret cert not found in namespace prod"),
        (ApiException(status=500, reason="boom"), "API error retrieving secret cert in namespace prod: 500 - boom"),
        (RuntimeError("x"), "Unexpected error retrieving secret cert in namespace prod: x"),
        (tls_secret({"tls.crt": "C"}), "Secret prod/cert is missing tls data"),
        (tls_secret(None), None),
    ],
)
def test_an_unusable_certificate_leaves_the_service_plain(gateway_build, secret, fragment):
    ctrl = gateway_build()
    if isinstance(secret, BaseException):
        ctrl._corev1.read_namespaced_secret.side_effect = secret
    else:
        ctrl._corev1.read_namespaced_secret.return_value = secret
    log = attach_log(ctrl)

    [svc] = to_services(ctrl, [https_gateway()], route(hostnames=["app.example.com"], rules=[http_rule()]))

    assert "USE_CUSTOM_SSL" not in svc
    if fragment:
        assert log.has(fragment)


def test_certificate_refs_of_other_kinds_or_passthrough_listeners_are_ignored(gateway_build):
    ctrl = gateway_build()
    listeners = [
        {"name": "pass", "port": 443, "protocol": "TLS", "tls": {"mode": "Passthrough", "certificateRefs": [{"name": "cert"}]}},
        {"name": "https", "port": 8443, "protocol": "HTTPS", "tls": {"certificateRefs": [{"name": "x", "kind": "ConfigMap"}, "junk", {"kind": "Secret"}]}},
        {"name": "bare", "port": 9443, "protocol": "HTTPS", "tls": {}},
    ]

    [svc] = to_services(ctrl, [gw(listeners=listeners)], route(hostnames=["app.example.com"], rules=[http_rule()]))

    assert "USE_CUSTOM_SSL" not in svc
    ctrl._corev1.read_namespaced_secret.assert_not_called()


# --- annotations ------------------------------------------------------------------------------------------


def test_gateway_and_route_annotations_are_applied_with_the_route_winning(gateway_build):
    ctrl = gateway_build()
    gateway = gw(annotations={"bunkerweb.io/USE_ANTIBOT": "captcha", "bunkerweb.io/LIMIT_REQ_RATE": "5r/s", "other.io/x": "1"})
    r = route(hostnames=["a.example.com"], rules=[http_rule()], annotations={"bunkerweb.io/USE_ANTIBOT": "javascript"})

    [svc] = to_services(ctrl, [gateway], r)

    assert svc["a.example.com_USE_ANTIBOT"] == "javascript"
    assert svc["a.example.com_LIMIT_REQ_RATE"] == "5r/s"
    assert not any("other.io" in key for key in svc)


def test_ignored_and_server_name_annotations_do_not_apply(gateway_build):
    ctrl = gateway_build(KUBERNETES_IGNORE_ANNOTATIONS="USE_ANTIBOT")
    log = attach_log(ctrl)
    r = route(
        hostnames=["a.example.com"],
        rules=[http_rule()],
        annotations={"bunkerweb.io/USE_ANTIBOT": "captcha", "bunkerweb.io/SERVER_NAME": "evil.example.com", "bunkerweb.io/UNKNOWN_THING": "1"},
    )

    [svc] = to_services(ctrl, [gw()], r)

    assert svc["SERVER_NAME"] == "a.example.com"
    assert not any(key.endswith("USE_ANTIBOT") for key in svc)
    assert svc["UNKNOWN_THING"] == "1"
    assert log.has("SERVER_NAME can't be set globally via annotations", logging.WARNING)


def test_annotations_prefixed_for_another_host_do_not_leak_into_this_one(gateway_build):
    ctrl = gateway_build()
    r = route(hostnames=["a.example.com", "b.example.com"], rules=[http_rule()], annotations={"bunkerweb.io/b.example.com_USE_ANTIBOT": "captcha"})

    [svc] = to_services(ctrl, [gw()], r)

    assert not any(key == "b.example.com_USE_ANTIBOT" for key in svc)


def test_stream_service_annotation_keeps_one_reverse_proxy_without_scheme(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)
    annotations = {
        "bunkerweb.io/a.example.com_SERVER_TYPE": "stream",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_HOST": "http://first:1",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_HOST_2": "http://second:2",
        "bunkerweb.io/a.example.com_REVERSE_PROXY_URL_2": "/two",
    }

    [svc] = to_services(ctrl, [gw()], route(hostnames=["a.example.com"], rules=[http_rule()], annotations=annotations))

    assert svc["a.example.com_REVERSE_PROXY_HOST"] == "first:1"
    assert svc["a.example.com_REVERSE_PROXY_URL"] == "/"
    assert "a.example.com_REVERSE_PROXY_HOST_2" not in svc and "a.example.com_REVERSE_PROXY_URL_2" not in svc
    assert log.has("is a stream service", logging.WARNING)


# --- GRPCRoute --------------------------------------------------------------------------------------------


def test_grpc_route_becomes_a_grpc_service(gateway_build):
    ctrl = gateway_build()
    rules = [{"matches": [{"method": {"service": "pkg.Svc", "method": "Do"}}], "backendRefs": [backend("g", 9000)]}, {"backendRefs": [backend("h", 80)]}]

    [svc] = to_services(ctrl, [gw()], route("GRPCRoute", hostnames=["g.example.com"], rules=rules))

    assert svc == {
        "SERVER_NAME": "g.example.com",
        "NAMESPACE": "prod",
        "USE_GRPC": "yes",
        "GRPC_HOST_1": "grpc://g.prod.svc.cluster.local:9000",
        "GRPC_URL_1": "/pkg.Svc/Do",
        "GRPC_HOST_2": "grpc://h.prod.svc.cluster.local",
        "GRPC_URL_2": "/",
    }


def test_grpc_over_https_uses_grpcs_and_its_default_port(gateway_build):
    ctrl = gateway_build(KUBERNETES_SERVICE_PROTOCOL="https")
    rules = [{"backendRefs": [backend("a", 443)]}, {"backendRefs": [backend("b", 8443)]}]

    [svc] = to_services(ctrl, [gw()], route("GRPCRoute", hostnames=["g.example.com"], rules=rules))

    assert svc["GRPC_HOST_1"] == "grpcs://a.prod.svc.cluster.local"
    assert svc["GRPC_HOST_2"] == "grpcs://b.prod.svc.cluster.local:8443"


def test_grpc_route_edge_cases(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    assert to_services(ctrl, [gw()], route("GRPCRoute", rules=[{"backendRefs": [backend()]}])) == []
    assert log.has("Ignoring GRPCRoute prod/r without hostnames", logging.WARNING)

    assert to_services(ctrl, [gw(listeners=[{"name": "raw", "protocol": "TCP"}])], route("GRPCRoute", hostnames=["g.example.com"])) == []
    assert log.has("Ignoring GRPCRoute prod/r: no compatible HTTP/HTTPS/TLS listener found", logging.WARNING)

    [svc] = to_services(ctrl, [gw()], route("GRPCRoute", hostnames=["g.example.com"]))
    assert "GRPC_HOST_1" not in svc
    assert log.has("Ignoring GRPCRoute prod/r without rules", logging.WARNING)


def test_grpc_route_takes_hostnames_from_the_listener(gateway_build):
    ctrl = gateway_build()

    [svc] = to_services(
        ctrl,
        [gw(listeners=[{"name": "h", "protocol": "HTTPS", "hostname": "l.example.com", "port": 443}])],
        route("GRPCRoute", rules=[{"backendRefs": [backend()]}]),
    )

    assert svc["SERVER_NAME"] == "l.example.com"


# --- TLSRoute ---------------------------------------------------------------------------------------------


def tls_gateway(port=443, hostname="tls.example.com"):
    return gw(listeners=[{"name": "tls", "port": port, "protocol": "TLS", "hostname": hostname, "tls": {"mode": "Passthrough"}}])


def test_tls_route_becomes_a_stream_service(gateway_build):
    ctrl = gateway_build()

    [svc] = to_services(
        ctrl, [tls_gateway(8443, "db.example.com")], route("TLSRoute", hostnames=["db.example.com"], rules=[{"backendRefs": [backend("db", 5432)]}])
    )

    assert svc == {
        "SERVER_NAME": "db.example.com",
        "NAMESPACE": "prod",
        "SERVER_TYPE": "stream",
        "USE_TCP": "yes",
        "USE_UDP": "no",
        "LISTEN_STREAM_PORT_SSL": "8443",
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_HOST": "db.prod.svc.cluster.local:5432",
        "REVERSE_PROXY_URL": "/",
    }


def test_tls_route_server_name_sources(gateway_build):
    ctrl = gateway_build()
    rules = [{"backendRefs": [backend("db", 80)]}]
    log = attach_log(ctrl)

    [override] = to_services(
        ctrl, [tls_gateway()], route("TLSRoute", hostnames=["x.example.com"], rules=rules, annotations={"bunkerweb.io/SERVER_NAME": "forced.example.com extra"})
    )
    [listener] = to_services(ctrl, [tls_gateway()], route("TLSRoute", rules=rules))
    [fallback] = to_services(ctrl, [gw(listeners=[{"name": "raw", "port": 1, "protocol": "TCP"}])], route("TLSRoute", rules=rules))

    assert override["SERVER_NAME"] == "forced.example.com"
    assert listener["SERVER_NAME"] == "tls.example.com"
    assert fallback["SERVER_NAME"] == "r.prod.tls"
    assert override["REVERSE_PROXY_HOST"] == "db.prod.svc.cluster.local"
    assert log.has("overrides hostnames with forced.example.com", logging.INFO)
    assert log.has("has no hostnames, using r.prod.tls", logging.WARNING)


def test_tls_route_port_comes_only_from_a_listener_matching_its_hostname(gateway_build):
    ctrl = gateway_build()

    [svc] = to_services(
        ctrl, [tls_gateway(8443, "other.example.com")], route("TLSRoute", hostnames=["db.example.com"], rules=[{"backendRefs": [backend("db", 80)]}])
    )

    assert "LISTEN_STREAM_PORT_SSL" not in svc


def test_tls_route_uses_only_its_first_rule(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    [svc] = to_services(
        ctrl,
        [tls_gateway()],
        route("TLSRoute", hostnames=["a.example.com"], rules=[{"backendRefs": [backend("one", 80)]}, {"backendRefs": [backend("two", 80)]}]),
    )

    assert svc["REVERSE_PROXY_HOST"] == "one.prod.svc.cluster.local"
    assert log.has("has multiple rules, using only the first one", logging.WARNING)


def test_tls_route_without_rules_serves_no_backend(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    [svc] = to_services(ctrl, [tls_gateway()], route("TLSRoute", hostnames=["a.example.com"]))

    assert "REVERSE_PROXY_HOST" not in svc
    assert log.has("Ignoring TLSRoute prod/r without rules", logging.WARNING)


# --- TCPRoute / UDPRoute ----------------------------------------------------------------------------------


def stream_gateway(protocol, port=9000, hostname=None):
    listener = {"name": "raw", "port": port, "protocol": protocol}
    if hostname:
        listener["hostname"] = hostname
    return gw(listeners=[listener])


@pytest.mark.parametrize(("kind", "protocol", "tcp", "udp"), [("TCPRoute", "TCP", "yes", "no"), ("UDPRoute", "UDP", "no", "yes")])
def test_tcp_and_udp_routes_become_stream_services(gateway_build, kind, protocol, tcp, udp):
    ctrl = gateway_build()

    [svc] = to_services(ctrl, [stream_gateway(protocol, 5353)], route(kind, name="dns", rules=[{"backendRefs": [backend("dns", 53)]}]))

    assert svc == {
        "SERVER_NAME": f"dns.prod.{protocol.lower()}",
        "NAMESPACE": "prod",
        "SERVER_TYPE": "stream",
        "USE_TCP": tcp,
        "USE_UDP": udp,
        "LISTEN_STREAM_PORT": "5353",
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_HOST": "dns.prod.svc.cluster.local:53",
        "REVERSE_PROXY_URL": "/",
    }


def test_stream_route_server_name_sources_and_rule_handling(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)
    rules = [{"backendRefs": [backend("one", 80)]}, {"backendRefs": [backend("two", 80)]}]

    [by_listener] = to_services(ctrl, [stream_gateway("TCP", hostname="tcp.example.com")], route("TCPRoute", rules=rules))
    [override] = to_services(ctrl, [stream_gateway("TCP")], route("TCPRoute", rules=rules, annotations={"bunkerweb.io/SERVER_NAME": "forced.example.com"}))
    [empty] = to_services(ctrl, [stream_gateway("UDP")], route("UDPRoute"))

    assert by_listener["SERVER_NAME"] == "tcp.example.com"
    assert by_listener["REVERSE_PROXY_HOST"] == "one.prod.svc.cluster.local"
    assert override["SERVER_NAME"] == "forced.example.com"
    assert "REVERSE_PROXY_HOST" not in empty
    assert log.has("TCPRoute prod/r has multiple rules, using only the first one", logging.WARNING)
    assert log.has("Ignoring UDPRoute prod/r without rules", logging.WARNING)


def test_a_route_without_a_usable_backend_keeps_the_service_without_a_proxy(gateway_build):
    ctrl = gateway_build()

    [svc] = to_services(ctrl, [stream_gateway("TCP")], route("TCPRoute", rules=[{"backendRefs": []}]))

    assert "USE_REVERSE_PROXY" not in svc


def test_unsupported_route_kinds_are_ignored(gateway_build):
    ctrl = gateway_build()
    log = attach_log(ctrl)

    assert ctrl._to_services({"kind": "WeirdRoute", "metadata": {"name": "w", "namespace": "prod"}, "spec": {}}) == []
    assert log.has("Ignoring unsupported Gateway API route kind weirdroute in prod/w", logging.WARNING)


def test_service_annotations_of_a_route_are_read_from_its_metadata(gateway_build):
    ctrl = gateway_build()

    assert ctrl._get_service_annotations(route(annotations={"a": "b"})) == {"a": "b"}
    assert ctrl._get_service_annotations({}) == {}


# --- events and watchers ---------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute", "Gateway"])
def test_gateway_api_kinds_are_relevant_events(gateway_build, kind):
    assert gateway_build()._is_custom_event(kind, {}, {}, "prod", "x") is True


def test_gateway_class_events_need_class_filtering_or_status_support(gateway_build):
    table = crds()
    del table["gatewayclasses"]
    assert gateway_build(table)._is_custom_event("GatewayClass", {}, {}, None, "x") is False
    assert gateway_build()._is_custom_event("GatewayClass", {}, {}, None, "x") is True
    assert gateway_build()._is_custom_event("Other", {}, {}, None, "x") is False


def test_watcher_closures_list_with_the_detected_version(gateway_build):
    ctrl = gateway_build(crds(("v1beta1",)))

    ctrl._get_watchers()["httproute"](limit=5)

    assert ctrl.api.list_calls[-1] == ("v1beta1", "httproutes")


def evt(kind, name="r", generation=1, typ="MODIFIED", annotations=None, labels=None, uid=None):
    metadata = {"name": name, "namespace": "prod", "generation": generation}
    if annotations:
        metadata["annotations"] = annotations
    if labels:
        metadata["labels"] = labels
    if uid:
        metadata["uid"] = uid
    return {"type": typ, "object": {"kind": kind, "metadata": metadata}}


def test_the_echo_of_a_status_write_is_dropped_but_spec_changes_are_not(gateway_build):
    ctrl = gateway_build()

    assert ctrl._is_status_only_event(evt("HTTPRoute")) is False
    assert ctrl._is_status_only_event(evt("HTTPRoute")) is True
    assert ctrl._is_status_only_event(evt("HTTPRoute", generation=2)) is False
    assert ctrl._is_status_only_event(evt("HTTPRoute", generation=2, annotations={"bunkerweb.io/X": "1"})) is False
    assert ctrl._is_status_only_event(evt("HTTPRoute", generation=2, annotations={"bunkerweb.io/X": "1"}, labels={"a": "b"})) is False
    assert ctrl._is_status_only_event(evt("HTTPRoute", generation=2, annotations={"bunkerweb.io/X": "1"}, labels={"a": "b"})) is True


def test_a_deleted_object_is_forgotten_so_its_return_is_new(gateway_build):
    ctrl = gateway_build()
    ctrl._is_status_only_event(evt("Gateway", uid="u1"))

    assert ctrl._is_status_only_event(evt("Gateway", uid="u1", typ="DELETED")) is False
    assert ctrl._is_status_only_event(evt("Gateway", uid="u1")) is False


def test_events_of_other_kinds_are_never_status_only(gateway_build):
    ctrl = gateway_build()

    assert ctrl._is_status_only_event({"type": "MODIFIED", "object": {"kind": "Pod", "metadata": {}}}) is False
    assert ctrl._is_status_only_event({"type": "MODIFIED", "object": object()}) is False
    assert ctrl._is_status_only_event({"type": "MODIFIED"}) is False
