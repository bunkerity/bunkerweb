#!/usr/bin/env python3

from datetime import datetime, timezone
from fnmatch import fnmatchcase
from os import getenv
from threading import Event, Lock, Thread
from traceback import format_exc
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from controllers.KubernetesController import API_REQUEST_TIMEOUT, KubernetesController

GATEWAY_API_VERSIONS = ("v1", "v1alpha2", "v1alpha3", "v1beta1", "v1alpha1")
GATEWAY_API_GROUP = "gateway.networking.k8s.io"
ROUTE_PLURALS = ("httproutes", "grpcroutes", "tlsroutes", "tcproutes", "udproutes")
# Kinds whose spec changes bump metadata.generation; any other kind (Pod, Service, ConfigMap, Secret) changes without it.
GATEWAY_API_KINDS = frozenset({"GatewayClass", "Gateway", "HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute"})

# Route kinds a listener of each protocol can carry.
LISTENER_ROUTE_KINDS = {
    "HTTP": ("HTTPRoute", "GRPCRoute"),
    "HTTPS": ("HTTPRoute", "GRPCRoute"),
    "TLS": ("TLSRoute",),
    "TCP": ("TCPRoute",),
    "UDP": ("UDPRoute",),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def merge_conditions(existing: Optional[list], desired: Iterable[Tuple[str, bool, str, str]], generation: Optional[int], now: str) -> List[Dict[str, Any]]:
    """Conditions to store: `desired` is (type, ok, reason, message).

    lastTransitionTime only moves when a condition's status flips, and conditions of other types stay as they are."""
    previous = {c.get("type"): c for c in existing or [] if isinstance(c, dict)}
    merged = []
    desired_types = set()
    for condition_type, ok, reason, message in desired:
        desired_types.add(condition_type)
        status = "True" if ok else "False"
        old = previous.get(condition_type) or {}
        condition = {
            "type": condition_type,
            "status": status,
            "reason": reason,
            "message": message,
            "lastTransitionTime": old["lastTransitionTime"] if old.get("status") == status and old.get("lastTransitionTime") else now,
        }
        if isinstance(generation, int):
            condition["observedGeneration"] = generation
        merged.append(condition)
    merged.extend(condition for condition_type, condition in previous.items() if condition_type not in desired_types)
    return sorted(merged, key=lambda condition: condition.get("type") or "")


def normalize_parent_ref(parent_ref: Any, route_namespace: Optional[str]) -> Optional[Dict[str, Any]]:
    """A parentRef pointing at a Gateway, with the defaults filled in, or None for any other parent kind."""
    if not isinstance(parent_ref, dict) or not parent_ref.get("name"):
        return None
    if (parent_ref.get("group") or GATEWAY_API_GROUP) != GATEWAY_API_GROUP or (parent_ref.get("kind") or "Gateway") != "Gateway":
        return None
    namespace = parent_ref.get("namespace") or route_namespace
    if not namespace:
        return None
    normalized = {"group": GATEWAY_API_GROUP, "kind": "Gateway", "namespace": namespace, "name": parent_ref["name"]}
    for key in ("sectionName", "port"):
        if parent_ref.get(key) is not None:
            normalized[key] = parent_ref[key]
    return normalized


def _parent_key(parent_ref: Dict[str, Any]) -> Tuple[Any, ...]:
    return (parent_ref["namespace"], parent_ref["name"], parent_ref.get("sectionName"), parent_ref.get("port"))


def build_class_conditions(gateway_class: Dict[str, Any], now: str) -> List[Dict[str, Any]]:
    metadata = gateway_class.get("metadata") or {}
    return merge_conditions(
        (gateway_class.get("status") or {}).get("conditions"),
        [("Accepted", True, "Accepted", "Accepted by the BunkerWeb controller")],
        metadata.get("generation"),
        now,
    )


def count_attached_routes(gateway: Dict[str, Any], routes: List[Dict[str, Any]]) -> Dict[str, int]:
    metadata = gateway.get("metadata") or {}
    namespace, name = metadata.get("namespace"), metadata.get("name")
    listeners = (gateway.get("spec") or {}).get("listeners") or []
    counts = {listener.get("name"): 0 for listener in listeners}
    for route in routes:
        route_namespace = (route.get("metadata") or {}).get("namespace")
        attached = set()
        for raw_ref in (route.get("spec") or {}).get("parentRefs") or []:
            parent_ref = normalize_parent_ref(raw_ref, route_namespace)
            if not parent_ref or (parent_ref["namespace"], parent_ref["name"]) != (namespace, name):
                continue
            for listener in listeners:
                if parent_ref.get("sectionName") not in (None, listener.get("name")):
                    continue
                if parent_ref.get("port") not in (None, listener.get("port")):
                    continue
                attached.add(listener.get("name"))
        for listener_name in attached:
            counts[listener_name] += 1
    return counts


def build_gateway_status(gateway: Dict[str, Any], routes: List[Dict[str, Any]], applied: bool, now: str) -> Dict[str, Any]:
    """The `conditions` and `listeners` BunkerWeb owns on a Gateway. `addresses` is written separately."""
    metadata = gateway.get("metadata") or {}
    generation = metadata.get("generation")
    status = gateway.get("status") or {}
    if applied:
        programmed = ("Programmed", True, "Programmed", "The configuration was applied to BunkerWeb")
    else:
        programmed = ("Programmed", False, "Pending", "BunkerWeb could not apply the configuration, see the controller logs")
    attached = count_attached_routes(gateway, routes)
    previous_listeners = {listener.get("name"): listener for listener in status.get("listeners") or [] if isinstance(listener, dict)}
    listeners = []
    for listener in (gateway.get("spec") or {}).get("listeners") or []:
        listener_name = listener.get("name")
        kinds = LISTENER_ROUTE_KINDS.get((listener.get("protocol") or "").upper(), ())
        listeners.append(
            {
                "name": listener_name,
                "supportedKinds": [{"group": GATEWAY_API_GROUP, "kind": kind} for kind in kinds],
                "attachedRoutes": attached.get(listener_name, 0),
                "conditions": merge_conditions(
                    (previous_listeners.get(listener_name) or {}).get("conditions"),
                    [("Accepted", True, "Accepted", "Listener accepted"), programmed, ("ResolvedRefs", True, "ResolvedRefs", "References resolved")],
                    generation,
                    now,
                ),
            }
        )
    return {
        "conditions": merge_conditions(
            status.get("conditions"), [("Accepted", True, "Accepted", "Accepted by the BunkerWeb controller"), programmed], generation, now
        ),
        "listeners": listeners,
    }


def build_route_parents(
    route: Dict[str, Any], owned_gateways: Dict[Tuple[str, str], Dict[str, Any]], controller_name: str, now: str
) -> Optional[List[Dict[str, Any]]]:
    """The full `status.parents` list to store, or None when the route has no parent this controller owns.

    Entries of other controllers are kept untouched, in place; ours are matched on controllerName and parentRef."""
    metadata = route.get("metadata") or {}
    spec = route.get("spec") or {}
    route_namespace = metadata.get("namespace")
    generation = metadata.get("generation")

    bad_backend = next(
        (
            backend
            for rule in spec.get("rules") or []
            for backend in rule.get("backendRefs") or []
            if isinstance(backend, dict) and (backend.get("kind") or "Service") != "Service"
        ),
        None,
    )

    ours: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for raw_ref in spec.get("parentRefs") or []:
        parent_ref = normalize_parent_ref(raw_ref, route_namespace)
        if not parent_ref:
            continue
        gateway = owned_gateways.get((parent_ref["namespace"], parent_ref["name"]))
        if gateway is None:
            continue
        section = parent_ref.get("sectionName")
        listener_names = [listener.get("name") for listener in (gateway.get("spec") or {}).get("listeners") or []]
        if section and section not in listener_names:
            accepted = ("Accepted", False, "NoMatchingParent", f"Listener {section} does not exist on the Gateway")
        else:
            accepted = ("Accepted", True, "Accepted", "Route accepted by the BunkerWeb controller")
        if bad_backend is not None:
            resolved = ("ResolvedRefs", False, "InvalidKind", f"Unsupported backendRef kind {bad_backend.get('kind')}, only Service is supported")
        else:
            resolved = ("ResolvedRefs", True, "ResolvedRefs", "References resolved")
        ours.setdefault(_parent_key(parent_ref), {"parentRef": parent_ref, "desired": [accepted, resolved]})
    if not ours:
        return None

    parents = []
    used = set()
    for entry in (route.get("status") or {}).get("parents") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("controllerName") != controller_name:
            parents.append(entry)
            continue
        old_ref = normalize_parent_ref(entry.get("parentRef"), route_namespace)
        key = _parent_key(old_ref) if old_ref else None
        if key in ours and key not in used:
            used.add(key)
            wanted = ours[key]
            parents.append(
                {
                    "parentRef": wanted["parentRef"],
                    "controllerName": controller_name,
                    "conditions": merge_conditions(entry.get("conditions"), wanted["desired"], generation, now),
                }
            )
    for key, wanted in ours.items():
        if key not in used:
            parents.append(
                {
                    "parentRef": wanted["parentRef"],
                    "controllerName": controller_name,
                    "conditions": merge_conditions(None, wanted["desired"], generation, now),
                }
            )
    return parents


class GatewayController(KubernetesController):
    _status_enabled = False

    def __init__(self):
        super().__init__()
        self._custom_objects = client.CustomObjectsApi(api_client=self._api_client)
        self._gateways_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._routes_cache: List[Dict[str, Any]] = []
        self._seen_specs: Dict[str, Tuple[Any, ...]] = {}
        self._status_lock = Lock()
        self._status_wakeup = Event()
        self._status_snapshot: Optional[Tuple[bool, Dict[Tuple[str, str], Dict[str, Any]], List[Dict[str, Any]]]] = None
        self._status_thread: Optional[Thread] = None
        self._status_warned: Set[Tuple[str, str, str]] = set()

        self._gateway_class = getenv("KUBERNETES_GATEWAY_CLASS", "").strip()
        if self._gateway_class:
            self._logger.info(f"Using Gateway class: {self._gateway_class}")

        self._skip_foreign_classes = getenv("KUBERNETES_SKIP_FOREIGN_CLASSES", "no").strip().lower() == "yes"
        self._gateway_controller = getenv("KUBERNETES_GATEWAY_CONTROLLER", "bunkerweb.io/gateway-controller").strip()
        self._gateway_classes_warned = False

        self._gateway_api_group = "gateway.networking.k8s.io"
        self._gateway_api_version = getenv("KUBERNETES_GATEWAY_API_VERSION", "v1").strip().lower()
        if self._gateway_api_version not in GATEWAY_API_VERSIONS:
            self._logger.warning(f"Unsupported KUBERNETES_GATEWAY_API_VERSION {self._gateway_api_version}, defaulting to v1")
            self._gateway_api_version = "v1"

        self._resource_versions = self._detect_resource_versions()
        self._gateway_classes_readable = bool(self._skip_foreign_classes and not self._gateway_class and self._resource_versions.get("gatewayclasses"))
        if self._gateway_classes_readable:
            self._logger.info(f"Skipping Gateways whose GatewayClass does not use controller {self._gateway_controller}")
        self._gateway_api_available = "gateways" in self._resource_versions
        self._status_enabled = self._gateway_api_available and "gatewayclasses" in self._resource_versions
        if self._gateway_api_available:
            self._gateway_api_version = self._resource_versions["gateways"]
            missing = [plural for plural in ("httproutes", "grpcroutes", "tlsroutes", "tcproutes", "udproutes") if plural not in self._resource_versions]
            if missing:
                missing_list = ", ".join(missing)
                hint = ""
                if any(plural in {"grpcroutes", "tlsroutes", "tcproutes", "udproutes"} for plural in missing):
                    hint = (
                        " If you intend to use GRPCRoute/TLSRoute/TCPRoute/UDPRoute, install the Experimental Channel CRDs: "
                        "https://gateway-api.sigs.k8s.io/guides/getting-started/#install-experimental-channel"
                    )
                self._logger.warning(f"Gateway API resources not available: {missing_list}. Skipping their watches until the next restart.{hint}")
        else:
            self._logger.warning("Gateway API CRDs not detected, controller will stay idle")

    def _candidate_gateway_api_versions(self) -> List[str]:
        versions = [self._gateway_api_version]
        for version in GATEWAY_API_VERSIONS:
            if version not in versions:
                versions.append(version)
        return versions

    def _detect_resource_versions(self) -> Dict[str, str]:
        resource_versions: Dict[str, str] = {}
        versions = self._candidate_gateway_api_versions()
        resources = ("gateways", "httproutes", "grpcroutes", "tlsroutes", "tcproutes", "udproutes")

        for plural in resources:
            for version in versions:
                try:
                    self._custom_objects.list_cluster_custom_object(self._gateway_api_group, version, plural, limit=1, _request_timeout=API_REQUEST_TIMEOUT)
                    resource_versions[plural] = version
                    if plural == "gateways" and version != self._gateway_api_version:
                        self._logger.info(f"Gateway API {self._gateway_api_version} not available, falling back to {version}")
                    break
                except ApiException as e:
                    if e.status == 404:
                        continue
                    if e.status == 403:
                        self._logger.error(f"Insufficient permissions to access {plural} in Gateway API {version}")
                        break
                    self._logger.error(f"Error while probing {plural} in Gateway API {version}: {e.status} - {e.reason}")
                    self._logger.debug(format_exc())
                    break
                except Exception as e:
                    self._logger.error(f"Unexpected error while probing {plural} in Gateway API {version}: {e}")
                    self._logger.debug(format_exc())
                    break

        if (self._skip_foreign_classes and not self._gateway_class) or "gateways" in resource_versions:
            found = False
            last_error = ""
            for version in versions:
                try:
                    self._custom_objects.list_cluster_custom_object(
                        self._gateway_api_group, version, "gatewayclasses", limit=1, _request_timeout=API_REQUEST_TIMEOUT
                    )
                    resource_versions["gatewayclasses"] = version
                    found = True
                    break
                except ApiException as e:
                    last_error = f"{e.status} - {e.reason}"
                except Exception as e:
                    last_error = str(e)
            if not found:
                if self._skip_foreign_classes and not self._gateway_class:
                    self._warn_gateway_classes(last_error)
                else:
                    self._logger.warning(
                        f"Can't list gatewayclasses ({last_error}), Gateway API status will not be written: grant get/list/watch on gatewayclasses"
                    )

        return resource_versions

    def _warn_gateway_classes(self, reason: str) -> None:
        if not self._gateway_classes_warned:
            self._logger.warning(
                f"Can't list gatewayclasses ({reason}), Gateways of every class will be processed: grant get/list/watch on gatewayclasses to the controller"
            )
            self._gateway_classes_warned = True

    def _foreign_gateway_classes(self) -> Optional[Set[str]]:
        """Names of GatewayClasses owned by another controller, or None when ownership filtering is off or they cannot be listed."""
        if not self._gateway_classes_readable:
            return None
        items = self._list_custom_objects("gatewayclasses")
        return {
            (item.get("metadata") or {}).get("name")
            for item in items
            if (item.get("spec") or {}).get("controllerName") != self._gateway_controller and (item.get("metadata") or {}).get("name")
        }

    def _hostname_matches(self, hostname: str, pattern: Optional[str]) -> bool:
        if not pattern:
            return True
        return fnmatchcase(hostname.lower(), pattern.lower())

    def _list_custom_objects(self, plural: str) -> List[Dict[str, Any]]:
        if not self._gateway_api_available:
            return []
        version = self._resource_versions.get(plural)
        if not version:
            return []
        try:
            data = self._custom_objects.list_cluster_custom_object(
                self._gateway_api_group,
                version,
                plural,
                _request_timeout=API_REQUEST_TIMEOUT,
            )
            return data.get("items", []) if isinstance(data, dict) else []
        except ApiException as e:
            self._logger.error(f"API error listing {plural}: {e.status} - {e.reason}")
            self._logger.debug(format_exc())
        except Exception as e:
            self._logger.error(f"Unexpected error listing {plural}: {e}")
            self._logger.debug(format_exc())
        return []

    def _get_gateways(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        gateways: Dict[Tuple[str, str], Dict[str, Any]] = {}
        foreign = self._foreign_gateway_classes()
        for gateway in self._list_custom_objects("gateways"):
            metadata = gateway.get("metadata") or {}
            namespace = metadata.get("namespace")
            name = metadata.get("name")
            if not namespace or not name:
                continue

            if self._namespaces and namespace not in self._namespaces:
                self._logger.debug(f"Skipping gateway {namespace}/{name} because its namespace is not allowed")
                continue

            annotations = metadata.get("annotations") or {}
            if annotations and any(self._should_ignore_annotation(annotation) for annotation in annotations):
                self._logger.debug(f"Skipping gateway {namespace}/{name} because of ignored annotations")
                continue

            if self._gateway_class:
                spec = gateway.get("spec") or {}
                if spec.get("gatewayClassName") != self._gateway_class:
                    self._logger.debug(f"Skipping gateway {namespace}/{name} because its gatewayClassName is not allowed")
                    continue
            elif foreign and (gateway.get("spec") or {}).get("gatewayClassName") in foreign:
                self._logger.debug(f"Skipping gateway {namespace}/{name} because its GatewayClass belongs to another controller")
                continue

            gateways[(namespace, name)] = gateway
        return gateways

    def _route_targets_allowed_gateway(self, route: Dict[str, Any], gateways: Dict[Tuple[str, str], Dict[str, Any]]) -> bool:
        spec = route.get("spec") or {}
        parent_refs = spec.get("parentRefs") or []
        if not parent_refs:
            return False

        route_namespace = (route.get("metadata") or {}).get("namespace")
        for parent_ref in parent_refs:
            if not isinstance(parent_ref, dict):
                continue
            name = parent_ref.get("name")
            if not name:
                continue
            namespace = parent_ref.get("namespace") or route_namespace
            if namespace and (namespace, name) in gateways:
                return True

        return False

    def _get_controller_routes(self) -> List[Dict[str, Any]]:
        routes = []
        gateways = self._get_gateways()
        for plural in ROUTE_PLURALS:
            for route in self._list_custom_objects(plural):
                metadata = route.get("metadata") or {}
                namespace = metadata.get("namespace")
                name = metadata.get("name")
                if not namespace or not name:
                    continue

                route_kind = route.get("kind") or plural[:-1].capitalize()

                if self._namespaces and namespace not in self._namespaces:
                    self._logger.debug(f"Skipping {route_kind} {namespace}/{name} because its namespace is not allowed")
                    continue

                annotations = metadata.get("annotations") or {}
                if annotations and any(self._should_ignore_annotation(annotation) for annotation in annotations):
                    self._logger.debug(f"Skipping {route_kind} {namespace}/{name} because of ignored annotations")
                    continue

                if not self._route_targets_allowed_gateway(route, gateways):
                    self._logger.debug(f"Skipping {route_kind} {namespace}/{name} because it does not target an allowed Gateway")
                    continue

                routes.append(route)

        routes.sort(key=lambda r: ((r.get("metadata") or {}).get("namespace", ""), (r.get("metadata") or {}).get("name", "")))
        self._gateways_cache = gateways
        self._routes_cache = routes
        return routes

    def _get_controller_services(self) -> list:
        return self._get_controller_routes()

    def _get_service_annotations(self, controller_service) -> Dict[str, str]:
        metadata = controller_service.get("metadata") or {}
        return metadata.get("annotations") or {}

    def _get_gateway_annotations(self, route: Dict[str, Any]) -> List[Dict[str, str]]:
        metadata, spec = (route.get("metadata") or {}), (route.get("spec") or {})
        route_namespace = metadata.get("namespace")
        parent_refs = spec.get("parentRefs") or []
        annotations = []

        for parent_ref in parent_refs:
            if not isinstance(parent_ref, dict):
                continue
            gateway_name = parent_ref.get("name")
            if not gateway_name:
                continue
            gateway_namespace = parent_ref.get("namespace") or route_namespace
            if not gateway_namespace:
                continue

            gateway = self._gateways_cache.get((gateway_namespace, gateway_name))
            if not gateway:
                continue

            gw_annotations = (gateway.get("metadata") or {}).get("annotations") or {}
            if gw_annotations:
                annotations.append(gw_annotations)

        return annotations

    def _apply_annotations(
        self,
        services: List[Dict[str, Any]],
        service_ids: List[str],
        all_hosts: List[str],
        annotations: Dict[str, str],
    ) -> None:
        if not annotations:
            return

        for service in services:
            server_name = service["SERVER_NAME"].strip().split(" ")[0]

            for annotation, value in annotations.items():
                if not annotation.startswith("bunkerweb.io/"):
                    continue
                if self._should_ignore_annotation(annotation):
                    continue

                setting = annotation.replace("bunkerweb.io/", "", 1)
                prefixed_targets = [name for name in all_hosts if setting.startswith(f"{name}_")]
                if prefixed_targets and not setting.startswith(f"{server_name}_"):
                    continue
                success, _ = self._db.is_valid_setting(setting, value=value, multisite=True)
                if success and not setting.startswith(f"{server_name}_"):
                    if any(setting.startswith(f"{s}_") for s in all_hosts):
                        continue
                    if setting == "SERVER_NAME":
                        self._logger.warning("Variable SERVER_NAME can't be set globally via annotations, ignoring it")
                        continue
                    setting = f"{server_name}_{setting}"
                service[setting] = value

    def _get_route_listeners(
        self,
        route: Dict[str, Any],
        hostname: Optional[str] = None,
        protocols: Optional[List[str]] = None,
    ) -> List[Tuple[Dict[str, Any], str, str]]:
        metadata, spec = (route.get("metadata") or {}), (route.get("spec") or {})
        route_namespace = metadata.get("namespace")
        parent_refs = spec.get("parentRefs") or []
        listeners: List[Tuple[Dict[str, Any], str, str]] = []
        protocol_set = {proto.upper() for proto in protocols} if protocols else None

        for parent_ref in parent_refs:
            if not isinstance(parent_ref, dict):
                continue
            gateway_name = parent_ref.get("name")
            if not gateway_name:
                continue
            gateway_namespace = parent_ref.get("namespace") or route_namespace
            if not gateway_namespace:
                continue

            gateway = self._gateways_cache.get((gateway_namespace, gateway_name))
            if not gateway:
                continue

            section_name = parent_ref.get("sectionName")
            listeners_spec = (gateway.get("spec") or {}).get("listeners") or []
            for listener in listeners_spec:
                if section_name and listener.get("name") != section_name:
                    continue

                listener_hostname = listener.get("hostname")
                if hostname and listener_hostname and not self._hostname_matches(hostname, listener_hostname):
                    continue

                protocol = (listener.get("protocol") or "").upper()
                if protocol_set and protocol not in protocol_set:
                    continue

                listeners.append((listener, gateway_namespace, gateway_name))

        return listeners

    def _read_secret(self, name: str, namespace: str):
        try:
            return self._corev1.read_namespaced_secret(name=name, namespace=namespace, _request_timeout=API_REQUEST_TIMEOUT)
        except ApiException as e:
            if e.status == 404:
                self._logger.warning(f"Secret {name} not found in namespace {namespace}")
            else:
                self._logger.error(f"API error retrieving secret {name} in namespace {namespace}: {e.status} - {e.reason}")
                self._logger.debug(format_exc())
        except Exception as e:
            self._logger.error(f"Unexpected error retrieving secret {name} in namespace {namespace}: {e}")
            self._logger.debug(format_exc())
        return None

    def _get_tls_data_for_route(self, route: Dict[str, Any], hostname: str) -> Optional[Tuple[str, str]]:
        listeners = self._get_route_listeners(route, hostname=hostname, protocols=["HTTPS", "TLS"])
        for listener, gateway_namespace, gateway_name in listeners:
            protocol = (listener.get("protocol") or "").upper()

            tls = listener.get("tls") or {}
            tls_mode = (tls.get("mode") or "Terminate").strip()
            if protocol == "TLS" and tls_mode.lower() != "terminate":
                self._logger.debug(f"Skipping TLS listener {listener.get('name') or 'unnamed'} on {gateway_namespace}/{gateway_name} with mode {tls_mode}")
                continue

            cert_refs = tls.get("certificateRefs") or []
            if not cert_refs:
                continue

            for cert_ref in cert_refs:
                if not isinstance(cert_ref, dict):
                    continue
                kind = cert_ref.get("kind") or "Secret"
                if kind != "Secret":
                    continue

                secret_name = cert_ref.get("name")
                if not secret_name:
                    continue

                secret_namespace = cert_ref.get("namespace") or gateway_namespace
                secret = self._read_secret(secret_name, secret_namespace)
                if not secret or not secret.data:
                    continue

                if "tls.crt" not in secret.data or "tls.key" not in secret.data:
                    self._logger.warning(f"Secret {secret_namespace}/{secret_name} is missing tls data")
                    continue

                return secret.data["tls.crt"], secret.data["tls.key"]

        return None

    def _get_listener_protocol(self, route: Dict[str, Any], hostname: str, allowed_protocols: Optional[List[str]] = None) -> str:
        listeners = self._get_route_listeners(route, hostname=hostname, protocols=allowed_protocols)
        protocols = {listener.get("protocol", "").upper() for listener, _, _ in listeners}
        protocols.discard("")

        if not protocols:
            return ""

        if "TCP" in protocols:
            return "TCP"
        if "HTTPS" in protocols or "TLS" in protocols:
            return "HTTPS"
        if "HTTP" in protocols:
            return "HTTP"

        return self._service_protocol.upper()

    def _get_listener_port(
        self,
        route: Dict[str, Any],
        hostname: Optional[str] = None,
        protocols: Optional[List[str]] = None,
    ) -> Optional[int]:
        listeners = self._get_route_listeners(route, hostname=hostname, protocols=protocols)
        if not listeners:
            return None

        ports = []
        for listener, _, _ in listeners:
            port = listener.get("port")
            if isinstance(port, int):
                ports.append(port)

        if not ports:
            return None

        if len(set(ports)) > 1:
            route_meta = route.get("metadata") or {}
            route_name = route_meta.get("name") or "unknown"
            route_namespace = route_meta.get("namespace") or "default"
            self._logger.warning(f"Multiple listener ports found for {route_namespace}/{route_name}, using the first one")

        return ports[0]

    def _get_listener_hostnames(
        self,
        route: Dict[str, Any],
        protocols: Optional[List[str]] = None,
    ) -> List[str]:
        listeners = self._get_route_listeners(route, protocols=protocols)
        hostnames = []
        for listener, _, _ in listeners:
            hostname = listener.get("hostname")
            if hostname:
                hostnames.append(hostname)
        return list(dict.fromkeys(hostnames))

    def _route_default_server_name(self, kind: str, namespace: Optional[str], name: Optional[str]) -> str:
        base = name or "route"
        if namespace:
            base = f"{base}.{namespace}"
        return f"{base}.{kind.lower()}"

    def _get_backend_ref(
        self,
        backend_refs: List[Dict[str, Any]],
        namespace: Optional[str],
        route_name: str,
        route_kind: str,
    ) -> Optional[Tuple[str, int, str]]:
        if not backend_refs:
            self._logger.warning(f"Ignoring {route_kind} rule without backendRefs in {namespace}/{route_name}")
            return None

        backend_ref = backend_refs[0]
        if len(backend_refs) > 1:
            self._logger.warning(f"{route_kind} {namespace}/{route_name} has multiple backendRefs for a rule, using only the first one")

        if not isinstance(backend_ref, dict):
            return None

        kind = backend_ref.get("kind") or "Service"
        if kind != "Service":
            self._logger.warning(f"Ignoring {route_kind} backendRef with unsupported kind {kind} in {namespace}/{route_name}")
            return None

        backend_name = backend_ref.get("name")
        backend_port = backend_ref.get("port")
        if not backend_name or not backend_port:
            self._logger.warning(f"Ignoring {route_kind} backendRef without name/port in {namespace}/{route_name}")
            return None

        backend_namespace = backend_ref.get("namespace") or namespace
        if not backend_namespace:
            self._logger.warning(f"Ignoring {route_kind} backendRef without namespace in {namespace}/{route_name}")
            return None

        return backend_name, backend_port, backend_namespace

    def _grpc_match_path(self, match: Any) -> str:
        if not isinstance(match, dict):
            return "/"

        method = match.get("method")
        if not isinstance(method, dict):
            return "/"

        service = (method.get("service") or "").strip().strip("/")
        rpc_method = (method.get("method") or "").strip().strip("/")

        if service and rpc_method:
            return f"/{service}/{rpc_method}"
        if service:
            return f"/{service}/"

        return "/"

    def _to_services(self, controller_service) -> List[dict]:
        metadata = controller_service.get("metadata") or {}
        spec = controller_service.get("spec") or {}
        namespace = metadata.get("namespace")
        name = metadata.get("name")
        route_kind = (controller_service.get("kind") or "HTTPRoute").lower()
        annotations = dict(metadata.get("annotations") or {})
        gateway_annotations = self._get_gateway_annotations(controller_service)

        server_name_override = None
        if route_kind in ("tlsroute", "tcproute", "udproute") and "bunkerweb.io/SERVER_NAME" in annotations:
            server_name_override = annotations.pop("bunkerweb.io/SERVER_NAME").strip().split()[0]

        services: List[Dict[str, Any]] = []
        rules = spec.get("rules") or []

        if route_kind == "httproute":
            hostnames = spec.get("hostnames") or []
            if not hostnames:
                listener_hostnames = self._get_listener_hostnames(controller_service, protocols=["HTTP", "HTTPS", "TLS"])
                if listener_hostnames:
                    hostnames = listener_hostnames
                    self._logger.info(f"HTTPRoute {namespace}/{name} uses listener hostnames: {', '.join(listener_hostnames)}")
                else:
                    self._logger.warning(f"Ignoring HTTPRoute {namespace}/{name} without hostnames")
                    return []

            service: Dict[str, Any] = {"SERVER_NAME": " ".join(hostnames), "NAMESPACE": namespace}
            location = self._reverse_proxy_suffix_start
            listener_protocol = self._get_listener_protocol(controller_service, hostnames[0], allowed_protocols=["HTTP", "HTTPS", "TLS"])
            if not listener_protocol:
                self._logger.warning(f"Ignoring HTTPRoute {namespace}/{name}: no compatible HTTP/HTTPS/TLS listener found")
                return []
            # the backend scheme comes from the backend side, never from the frontend listener
            reverse_proxy_scheme = "tcp" if listener_protocol == "TCP" else self._service_protocol

            if listener_protocol == "TCP":
                service["SERVER_TYPE"] = "stream"
                listener_port = self._get_listener_port(controller_service, hostname=hostnames[0], protocols=["TCP"])
                if listener_port:
                    service["LISTEN_STREAM_PORT"] = str(listener_port)
                service["USE_TCP"] = "yes"
                service["USE_UDP"] = "no"

            if rules:
                for rule in rules:
                    matches = rule.get("matches") or [None]
                    backend_ref = self._get_backend_ref(rule.get("backendRefs") or [], namespace, name or "unknown", "HTTPRoute")
                    if not backend_ref:
                        continue
                    backend_name, backend_port, backend_namespace = backend_ref

                    for match in matches:
                        path_value = "/"
                        if isinstance(match, dict):
                            path = match.get("path")
                            if isinstance(path, dict) and path.get("value"):
                                path_value = path["value"]
                                # anchor regex paths so the template renders them as a regex location
                                if path.get("type") == "RegularExpression" and not path_value.startswith("^"):
                                    path_value = f"^{path_value}"

                        if not self._is_valid_reverse_proxy_url(path_value):
                            self._logger.warning(f"Ignoring HTTPRoute {namespace}/{name} match with path {path_value!r}: not a valid REVERSE_PROXY_URL.")
                            continue

                        if listener_protocol == "TCP":
                            reverse_proxy_host = f"{backend_name}.{backend_namespace}.svc.{self._domain_name}"
                        else:
                            reverse_proxy_host = f"{reverse_proxy_scheme}://{backend_name}.{backend_namespace}.svc.{self._domain_name}"
                        if backend_port != 80:
                            reverse_proxy_host += f":{backend_port}"

                        service.update(
                            {
                                "USE_REVERSE_PROXY": "yes",
                                f"REVERSE_PROXY_HOST_{location}" if location else "REVERSE_PROXY_HOST": reverse_proxy_host,
                                f"REVERSE_PROXY_URL_{location}" if location else "REVERSE_PROXY_URL": path_value,
                            }
                        )
                        location += 1

            services.append(service)
        elif route_kind == "grpcroute":
            hostnames = spec.get("hostnames") or []
            if not hostnames:
                listener_hostnames = self._get_listener_hostnames(controller_service, protocols=["HTTP", "HTTPS", "TLS"])
                if listener_hostnames:
                    hostnames = listener_hostnames
                    self._logger.info(f"GRPCRoute {namespace}/{name} uses listener hostnames: {', '.join(listener_hostnames)}")
                else:
                    self._logger.warning(f"Ignoring GRPCRoute {namespace}/{name} without hostnames")
                    return []

            listener_protocol = self._get_listener_protocol(controller_service, hostnames[0], allowed_protocols=["HTTP", "HTTPS", "TLS"])
            if not listener_protocol:
                self._logger.warning(f"Ignoring GRPCRoute {namespace}/{name}: no compatible HTTP/HTTPS/TLS listener found")
                return []

            grpc_scheme = "grpcs" if self._service_protocol == "https" else "grpc"
            location = self._reverse_proxy_suffix_start
            service: Dict[str, Any] = {"SERVER_NAME": " ".join(hostnames), "NAMESPACE": namespace, "USE_GRPC": "yes"}

            if rules:
                for rule in rules:
                    matches = rule.get("matches") or [None]
                    backend_ref = self._get_backend_ref(rule.get("backendRefs") or [], namespace, name or "unknown", "GRPCRoute")
                    if not backend_ref:
                        continue
                    backend_name, backend_port, backend_namespace = backend_ref

                    for match in matches:
                        grpc_url = self._grpc_match_path(match)
                        grpc_host = f"{grpc_scheme}://{backend_name}.{backend_namespace}.svc.{self._domain_name}"
                        if (grpc_scheme == "grpc" and backend_port != 80) or (grpc_scheme == "grpcs" and backend_port != 443):
                            grpc_host += f":{backend_port}"

                        service.update(
                            {
                                "USE_GRPC": "yes",
                                f"GRPC_HOST_{location}" if location else "GRPC_HOST": grpc_host,
                                f"GRPC_URL_{location}" if location else "GRPC_URL": grpc_url,
                            }
                        )
                        location += 1
            else:
                self._logger.warning(f"Ignoring GRPCRoute {namespace}/{name} without rules")

            services.append(service)
        elif route_kind == "tlsroute":
            hostnames = spec.get("hostnames") or []
            if server_name_override:
                if hostnames:
                    self._logger.info(f"TLSRoute {namespace}/{name} overrides hostnames with {server_name_override}")
                hostnames = [server_name_override]
            if not hostnames:
                listener_hostnames = self._get_listener_hostnames(controller_service, protocols=["TLS"])
                if listener_hostnames:
                    hostnames = listener_hostnames
                    self._logger.info(f"TLSRoute {namespace}/{name} uses listener hostnames: {', '.join(listener_hostnames)}")
            if not hostnames:
                default_name = self._route_default_server_name("tls", namespace, name)
                hostnames = [default_name]
                self._logger.warning(f"TLSRoute {namespace}/{name} has no hostnames, using {default_name}")

            service = {"SERVER_NAME": " ".join(hostnames), "NAMESPACE": namespace, "SERVER_TYPE": "stream", "USE_TCP": "yes", "USE_UDP": "no"}
            listener_port = self._get_listener_port(controller_service, hostname=hostnames[0], protocols=["TLS"])
            if listener_port:
                service["LISTEN_STREAM_PORT_SSL"] = str(listener_port)

            if not rules:
                self._logger.warning(f"Ignoring TLSRoute {namespace}/{name} without rules")
            else:
                for rule_index, rule in enumerate(rules):
                    if rule_index > 0:
                        self._logger.warning(f"TLSRoute {namespace}/{name} has multiple rules, using only the first one")
                        break
                    backend_ref = self._get_backend_ref(rule.get("backendRefs") or [], namespace, name or "unknown", "TLSRoute")
                    if not backend_ref:
                        continue
                    backend_name, backend_port, backend_namespace = backend_ref

                    reverse_proxy_host = f"{backend_name}.{backend_namespace}.svc.{self._domain_name}"
                    if backend_port != 80:
                        reverse_proxy_host += f":{backend_port}"

                    service.update(
                        {
                            "USE_REVERSE_PROXY": "yes",
                            "REVERSE_PROXY_HOST": reverse_proxy_host,
                            "REVERSE_PROXY_URL": "/",
                        }
                    )
            services.append(service)
        elif route_kind in ("tcproute", "udproute"):
            protocol = "UDP" if route_kind == "udproute" else "TCP"
            default_name = self._route_default_server_name(protocol.lower(), namespace, name)
            if server_name_override:
                hostnames = [server_name_override]
            else:
                listener_hostnames = self._get_listener_hostnames(controller_service, protocols=[protocol])
                hostnames = listener_hostnames or [default_name]
            listener_port = self._get_listener_port(controller_service, protocols=[protocol])
            service = {
                "SERVER_NAME": " ".join(hostnames),
                "NAMESPACE": namespace,
                "SERVER_TYPE": "stream",
                "USE_TCP": "yes" if protocol == "TCP" else "no",
                "USE_UDP": "yes" if protocol == "UDP" else "no",
            }
            if listener_port:
                service["LISTEN_STREAM_PORT"] = str(listener_port)

            if rules:
                for rule_index, rule in enumerate(rules):
                    if rule_index > 0:
                        self._logger.warning(f"{protocol}Route {namespace}/{name} has multiple rules, using only the first one")
                        break
                    backend_ref = self._get_backend_ref(rule.get("backendRefs") or [], namespace, name or "unknown", protocol + "Route")
                    if not backend_ref:
                        continue
                    backend_name, backend_port, backend_namespace = backend_ref

                    reverse_proxy_host = f"{backend_name}.{backend_namespace}.svc.{self._domain_name}"
                    if backend_port != 80:
                        reverse_proxy_host += f":{backend_port}"

                    service.update(
                        {
                            "USE_REVERSE_PROXY": "yes",
                            "REVERSE_PROXY_HOST": reverse_proxy_host,
                            "REVERSE_PROXY_URL": "/",
                        }
                    )
            else:
                self._logger.warning(f"Ignoring {protocol}Route {namespace}/{name} without rules")

            services.append(service)
        else:
            self._logger.warning(f"Ignoring unsupported Gateway API route kind {route_kind} in {namespace}/{name}")
            return []

        if services:
            service_ids = []
            all_hosts = []
            for service in services:
                if not service.get("SERVER_NAME"):
                    continue
                hosts = service["SERVER_NAME"].strip().split()
                if hosts:
                    service_ids.append(hosts[0])
                    all_hosts.extend(hosts)
            service_ids = list(dict.fromkeys(service_ids))
            all_hosts = list(dict.fromkeys(all_hosts))
            for gw_annotations in gateway_annotations:
                self._apply_annotations(services, service_ids, all_hosts, gw_annotations)
            self._apply_annotations(services, service_ids, all_hosts, annotations)

        for service in services:
            for server_name in service["SERVER_NAME"].strip().split():
                if service.get(f"{server_name}_SERVER_TYPE", service.get("SERVER_TYPE", "http")) == "stream":
                    reverse_proxy_found = False
                    warned = False
                    for setting in list(service.keys()):
                        if setting.startswith(f"{server_name}_REVERSE_PROXY_HOST"):
                            if not reverse_proxy_found:
                                reverse_proxy_found = True
                                suffix = setting.removeprefix(f"{server_name}_REVERSE_PROXY_HOST").removeprefix("_")
                                reverse_proxy_value = service.pop(setting)
                                if "://" in reverse_proxy_value:
                                    reverse_proxy_value = reverse_proxy_value.split("://", 1)[1]
                                service[f"{server_name}_REVERSE_PROXY_HOST"] = reverse_proxy_value
                                service[f"{server_name}_REVERSE_PROXY_URL"] = service.pop(
                                    f"{server_name}_REVERSE_PROXY_URL_{suffix}" if suffix else f"{server_name}_REVERSE_PROXY_URL",
                                    "/",
                                )
                                continue

                            if not warned:
                                warned = True
                                self._logger.warning(
                                    f"Service {server_name} is a stream service, we will only use the first reverse proxy config. Ignoring all others..."
                                )

                            del service[setting]
                        elif setting.startswith(f"{server_name}_REVERSE_PROXY_URL") and setting in service:
                            del service[setting]

        if route_kind in ("httproute", "grpcroute"):
            for service in services:
                server_name = service["SERVER_NAME"].strip().split(" ")[0]
                tls_data = self._get_tls_data_for_route(controller_service, server_name)
                if not tls_data:
                    continue
                cert_data, key_data = tls_data
                service["USE_CUSTOM_SSL"] = "yes"
                service["CUSTOM_SSL_CERT_DATA"] = cert_data
                service["CUSTOM_SSL_KEY_DATA"] = key_data

        return services

    def _is_custom_event(self, kind, obj, annotations, namespace, name) -> bool:
        if kind == "GatewayClass":
            return self._gateway_classes_readable or self._status_enabled
        return kind in ("HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute", "Gateway")

    def _get_watchers(self):
        watchers = {
            "pod": self._corev1.list_pod_for_all_namespaces,
            "configmap": self._corev1.list_config_map_for_all_namespaces,
            "service": self._corev1.list_service_for_all_namespaces,
            "secret": self._corev1.list_secret_for_all_namespaces,
        }

        if not self._gateway_api_available:
            return watchers

        def make_list(plural: str):
            version = self._resource_versions.get(plural)
            if not version:
                return None

            def _list(**kwargs):
                return self._custom_objects.list_cluster_custom_object(
                    self._gateway_api_group,
                    version,
                    plural,
                    **kwargs,
                )

            return _list

        watchers_map = {
            "gateway": make_list("gateways"),
            "httproute": make_list("httproutes"),
            "grpcroute": make_list("grpcroutes"),
            "tlsroute": make_list("tlsroutes"),
            "tcproute": make_list("tcproutes"),
            "udproute": make_list("udproutes"),
        }
        if self._status_enabled:
            watchers_map["gatewayclass"] = make_list("gatewayclasses")

        watchers.update({key: handler for key, handler in watchers_map.items() if handler})

        return watchers

    def _status_patch_enabled(self) -> bool:
        return self._gateway_api_available

    def _patch_gateway_status(self, gateway: Dict[str, Any], ips: List[str]) -> bool:
        if not ips:
            self._logger.warning("Cannot patch gateway without IP addresses")
            return False

        metadata = gateway.get("metadata") or {}
        gateway_name = metadata.get("name")
        gateway_namespace = metadata.get("namespace")

        if not gateway_name or not gateway_namespace:
            self._logger.error("Gateway name or namespace is empty, cannot patch status")
            return False

        patch_body = {"status": {"addresses": []}}

        # Add all IPs to the gateway status
        for ip in ips:
            if self._is_ip_address(ip):
                patch_body["status"]["addresses"].append({"type": "IPAddress", "value": ip})
            else:
                patch_body["status"]["addresses"].append({"type": "Hostname", "value": ip})

        try:
            self._custom_objects.patch_namespaced_custom_object_status(
                self._gateway_api_group,
                self._gateway_api_version,
                gateway_namespace,
                "gateways",
                gateway_name,
                patch_body,
                _request_timeout=API_REQUEST_TIMEOUT,
            )
            self._logger.info(f"Successfully patched status of gateway {gateway_name} in namespace {gateway_namespace} with {len(ips)} address(es)")
            return True
        except ApiException as e:
            if e.status == 404:
                self._logger.warning(f"Gateway {gateway_name} not found in namespace {gateway_namespace}, skipping status patch")
            elif e.status == 403:
                self._logger.warning(f"Insufficient permissions to patch gateway {gateway_name} status in namespace {gateway_namespace}")
            elif e.status == 422:
                self._logger.error(f"Invalid patch data for gateway {gateway_name} in namespace {gateway_namespace}: {e.reason}")
                self._logger.debug(f"Patch body was: {patch_body}")
            else:
                self._logger.error(f"API error patching gateway {gateway_name} in namespace {gateway_namespace}: {e.status} - {e.reason}")
            self._logger.debug(format_exc())
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error patching gateway {gateway_name} in namespace {gateway_namespace}: {e}")
            self._logger.debug(format_exc())
            return False

    def _owned_class_names(self, classes: List[Dict[str, Any]]) -> Set[str]:
        """GatewayClasses whose controllerName is ours, narrowed to KUBERNETES_GATEWAY_CLASS when it is set."""
        return {
            name
            for name in (
                (gateway_class.get("metadata") or {}).get("name")
                for gateway_class in classes
                if (gateway_class.get("spec") or {}).get("controllerName") == self._gateway_controller
            )
            if name and (not self._gateway_class or name == self._gateway_class)
        }

    def _patch_controller_status(self, ips: List[str]) -> None:
        # Addresses follow the same ownership as the conditions: never write on a Gateway of another controller.
        owned_classes = self._owned_class_names(self._list_custom_objects("gatewayclasses"))
        for gateway in self._gateways_cache.values():
            if (gateway.get("spec") or {}).get("gatewayClassName") in owned_classes:
                self._patch_gateway_status(gateway, ips)

    def _is_status_only_event(self, event) -> bool:
        """True for a watch event that carries nothing BunkerWeb reacts to, typically the echo of a status write.

        A Gateway API object changes what BunkerWeb serves through its spec (generation) and its annotations."""
        obj = event.get("object")
        if not isinstance(obj, dict) or obj.get("kind") not in GATEWAY_API_KINDS:
            return False
        metadata = obj.get("metadata") or {}
        key = metadata.get("uid") or f"{obj.get('kind')}/{metadata.get('namespace')}/{metadata.get('name')}"
        if event.get("type") == "DELETED":
            self._seen_specs.pop(key, None)
            return False
        signature = (
            metadata.get("generation"),
            tuple(sorted((metadata.get("annotations") or {}).items())),
            tuple(sorted((metadata.get("labels") or {}).items())),
        )
        previous = self._seen_specs.get(key)
        self._seen_specs[key] = signature
        return previous == signature

    def _sync_status(self, applied: Optional[bool] = None) -> None:
        if not self._status_enabled:
            return
        with self._status_lock:
            self._status_snapshot = (self._last_apply_ok if applied is None else applied, self._gateways_cache.copy(), self._routes_cache.copy())
        if self._status_thread is None:
            self._status_thread = Thread(target=self._status_worker, daemon=True)
            self._status_thread.start()
        self._status_wakeup.set()

    def _status_worker(self) -> None:
        # Status writes run outside the internal lock, so a slow or refused write never delays a configuration.
        while True:
            self._status_wakeup.wait()
            self._status_wakeup.clear()
            with self._status_lock:
                snapshot, self._status_snapshot = self._status_snapshot, None
            if snapshot:
                try:
                    self._reconcile_status(*snapshot)
                except BaseException as e:
                    self._logger.debug(format_exc())
                    self._logger.warning(f"Unexpected error while writing Gateway API status: {e}")

    def _reconcile_status(self, applied: bool, gateways: Dict[Tuple[str, str], Dict[str, Any]], routes: List[Dict[str, Any]]) -> None:
        # Ownership comes from the GatewayClass controllerName alone: whatever else BunkerWeb serves, it only reports on what it owns.
        classes = self._list_custom_objects("gatewayclasses")
        owned_classes = self._owned_class_names(classes)
        for gateway_class in classes:
            name = (gateway_class.get("metadata") or {}).get("name")
            if name not in owned_classes:
                continue
            conditions = build_class_conditions(gateway_class, utc_now())
            if conditions != (gateway_class.get("status") or {}).get("conditions"):
                self._patch_status("gatewayclasses", None, name, {"status": {"conditions": conditions}}, "GatewayClass")

        owned_gateways = {key: gateway for key, gateway in gateways.items() if (gateway.get("spec") or {}).get("gatewayClassName") in owned_classes}
        for (namespace, name), gateway in owned_gateways.items():
            status = build_gateway_status(gateway, routes, applied, utc_now())
            current = gateway.get("status") or {}
            if status["conditions"] != current.get("conditions") or status["listeners"] != current.get("listeners"):
                self._patch_status("gateways", namespace, name, {"status": status}, "Gateway")

        for route in routes:
            self._reconcile_route_status(route, owned_gateways)

    def _reconcile_route_status(self, route: Dict[str, Any], owned_gateways: Dict[Tuple[str, str], Dict[str, Any]], retry: bool = True) -> None:
        metadata = route.get("metadata") or {}
        namespace, name = metadata.get("namespace"), metadata.get("name")
        plural = (route.get("kind") or "").lower() + "s"
        if plural not in ROUTE_PLURALS:
            return
        parents = build_route_parents(route, owned_gateways, self._gateway_controller, utc_now())
        if parents is None or parents == (route.get("status") or {}).get("parents"):
            return
        body: Dict[str, Any] = {"status": {"parents": parents}}
        if metadata.get("resourceVersion"):
            body["metadata"] = {"resourceVersion": metadata["resourceVersion"]}
        if self._patch_status(plural, namespace, name, body, route.get("kind"), conflict_ok=retry) is None and retry:
            # The route changed since it was listed: merge into the fresh object instead of overwriting another controller's entry.
            try:
                fresh = self._custom_objects.get_namespaced_custom_object(
                    GATEWAY_API_GROUP, self._resource_versions[plural], namespace, plural, name, _request_timeout=API_REQUEST_TIMEOUT
                )
            except Exception as e:
                self._logger.debug(f"Cannot refresh {route.get('kind')} {namespace}/{name} after a conflict: {e}")
                return
            if isinstance(fresh, dict):
                fresh.setdefault("kind", route.get("kind"))
                self._reconcile_route_status(fresh, owned_gateways, retry=False)

    def _patch_status(
        self, plural: str, namespace: Optional[str], name: str, body: Dict[str, Any], kind: Optional[str], conflict_ok: bool = False
    ) -> Optional[bool]:
        """Patch a status subresource. True on success, False on a failure already reported, None on a conflict the caller may retry."""
        version = self._resource_versions.get(plural)
        key = (plural, namespace or "", name)
        try:
            if namespace is None:
                self._custom_objects.patch_cluster_custom_object_status(GATEWAY_API_GROUP, version, plural, name, body, _request_timeout=API_REQUEST_TIMEOUT)
            else:
                self._custom_objects.patch_namespaced_custom_object_status(
                    GATEWAY_API_GROUP, version, namespace, plural, name, body, _request_timeout=API_REQUEST_TIMEOUT
                )
            self._status_warned.discard(key)
            self._logger.debug(f"Wrote status of {kind} {namespace + '/' if namespace else ''}{name}")
            return True
        except ApiException as e:
            if e.status == 409 and conflict_ok:
                return None
            if e.status == 404:
                self._logger.debug(f"{kind} {namespace}/{name} disappeared before its status could be written")
                return False
            reason = f"{e.status} {e.reason}"
        except Exception as e:
            reason = str(e)
        if key not in self._status_warned:
            self._status_warned.add(key)
            self._logger.warning(f"Cannot write status of {kind} {namespace + '/' if namespace else ''}{name} ({reason}), configuration is not affected")
        return False
