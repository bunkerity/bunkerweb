"""Gateway API fakes: a CustomObjectsApi over a table, and object builders."""

from kubernetes.client.exceptions import ApiException

OURS = "bunkerweb.io/gateway-controller"
ALL_PLURALS = ("gateways", "httproutes", "grpcroutes", "tlsroutes", "tcproutes", "udproutes", "gatewayclasses")


class FakeCustomObjects:
    """CustomObjectsApi over a table: {plural: (served versions, items)}; anything else is a 404."""

    def __init__(self, crds):
        self.crds = crds
        self.list_calls = []
        self.patched = []

    def list_cluster_custom_object(self, group, version, plural, limit=None, _request_timeout=None):
        self.list_calls.append((version, plural))
        crd = self.crds.get(plural)
        if isinstance(crd, BaseException):
            raise crd
        if crd is None or version not in crd[0]:
            raise ApiException(status=404, reason="Not Found")
        return {"items": list(crd[1])}


def crds(versions=("v1",), **items):
    table = {plural: (versions, items.get(plural, [])) for plural in ALL_PLURALS}
    return table


def gw(name="gw", namespace="prod", class_name="bw", listeners=None, annotations=None):
    listeners = listeners if listeners is not None else [{"name": "http", "port": 80, "protocol": "HTTP"}]
    metadata = {"name": name, "namespace": namespace}
    if annotations:
        metadata["annotations"] = annotations
    return {"kind": "Gateway", "metadata": metadata, "spec": {"gatewayClassName": class_name, "listeners": listeners}}


def gateway_class(name, controller):
    return {"kind": "GatewayClass", "metadata": {"name": name}, "spec": {"controllerName": controller}}


def route(kind="HTTPRoute", name="r", namespace="prod", hostnames=None, rules=None, parents=None, annotations=None):
    metadata = {"name": name, "namespace": namespace}
    if annotations:
        metadata["annotations"] = annotations
    spec = {"parentRefs": parents if parents is not None else [{"name": "gw"}], "rules": rules if rules is not None else []}
    if hostnames is not None:
        spec["hostnames"] = hostnames
    return {"kind": kind, "metadata": metadata, "spec": spec}


def backend(name="api", port=8080, **extra):
    return {"name": name, "port": port, **extra}


def served(ctrl, gateways, *routes, classes=None):
    """Make the fake API return these objects and refresh the controller's caches."""
    by_plural = {"gateways": gateways, "gatewayclasses": classes or []}
    for r in routes:
        by_plural.setdefault(r["kind"].lower() + "s", []).append(r)
    for plural in ALL_PLURALS:
        served_versions = ctrl.api.crds[plural][0] if plural in ctrl.api.crds else ("v1",)
        ctrl.api.crds[plural] = (served_versions, by_plural.get(plural, []))
    return ctrl._get_controller_routes()
