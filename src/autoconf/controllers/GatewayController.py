#!/usr/bin/env python3

from fnmatch import fnmatchcase
from os import getenv
from traceback import format_exc
from typing import Any, Dict, List, Optional, Tuple

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from controllers.KubernetesController import KubernetesController

GATEWAY_API_VERSIONS = ("v1", "v1alpha2", "v1alpha3", "v1beta1", "v1alpha1")


class GatewayController(KubernetesController):
    def __init__(self):
        super().__init__()
        self._custom_objects = client.CustomObjectsApi()
        self._gateways_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

        self._gateway_class = getenv("KUBERNETES_GATEWAY_CLASS", "").strip()
        if self._gateway_class:
            self._logger.info(f"Using Gateway class: {self._gateway_class}")

        self._gateway_api_group = "gateway.networking.k8s.io"
        self._gateway_api_version = getenv("KUBERNETES_GATEWAY_API_VERSION", "v1").strip().lower()
        if self._gateway_api_version not in GATEWAY_API_VERSIONS:
            self._logger.warning(f"Unsupported KUBERNETES_GATEWAY_API_VERSION {self._gateway_api_version}, defaulting to v1")
            self._gateway_api_version = "v1"

        self._resource_versions = self._detect_resource_versions()
        self._gateway_api_available = "gateways" in self._resource_versions
        if self._gateway_api_available:
            self._gateway_api_version = self._resource_versions["gateways"]
            missing = [plural for plural in ("httproutes", "tlsroutes", "tcproutes", "udproutes") if plural not in self._resource_versions]
            if missing:
                missing_list = ", ".join(missing)
                self._logger.warning(
                    "Gateway API resources not available: "
                    f"{missing_list}. Skipping their watches until the next restart. "
                    "If you intend to use these routes, install the Experimental Channel CRDs: "
                    "https://gateway-api.sigs.k8s.io/guides/getting-started/#install-experimental-channel"
                )
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
        resources = ("gateways", "httproutes", "tlsroutes", "tcproutes", "udproutes")

        for plural in resources:
            for version in versions:
                try:
                    self._custom_objects.list_cluster_custom_object(self._gateway_api_group, version, plural, limit=1)
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

        return resource_versions

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
        for plural in ("httproutes", "tlsroutes", "tcproutes", "udproutes"):
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

        self._gateways_cache = gateways
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
            return self._corev1.read_namespaced_secret(name=name, namespace=namespace)
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

            service: Dict[str, Any] = {"SERVER_NAME": " ".join(hostnames)}
            location = self._reverse_proxy_suffix_start
            listener_protocol = self._get_listener_protocol(controller_service, hostnames[0], allowed_protocols=["HTTP", "HTTPS", "TLS"])
            if not listener_protocol:
                self._logger.warning(f"Ignoring HTTPRoute {namespace}/{name}: no compatible HTTP/HTTPS/TLS listener found")
                return []
            reverse_proxy_scheme = "tcp" if listener_protocol == "TCP" else listener_protocol.lower()

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
                                path_value = path.get("value")

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

            service = {"SERVER_NAME": " ".join(hostnames), "SERVER_TYPE": "stream", "USE_TCP": "yes", "USE_UDP": "no"}
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

        if route_kind == "httproute":
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
        return kind in ("HTTPRoute", "TLSRoute", "TCPRoute", "UDPRoute", "Gateway")

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
            "tlsroute": make_list("tlsroutes"),
            "tcproute": make_list("tcproutes"),
            "udproute": make_list("udproutes"),
        }

        watchers.update({key: handler for key, handler in watchers_map.items() if handler})

        return watchers

    def _status_patch_enabled(self) -> bool:
        return self._gateway_api_available

    def _patch_gateway_status(self, gateway: Dict[str, Any], ip: str) -> bool:
        if not ip:
            self._logger.warning("Cannot patch gateway without IP address")
            return False

        metadata = gateway.get("metadata") or {}
        gateway_name = metadata.get("name")
        gateway_namespace = metadata.get("namespace")

        if not gateway_name or not gateway_namespace:
            self._logger.error("Gateway name or namespace is empty, cannot patch status")
            return False

        patch_body = {"status": {"addresses": []}}
        ip_match = self._ip_pattern.match(ip)

        if ip_match:
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
            )
            self._logger.info(
                f"Successfully patched status of gateway {gateway_name} in namespace {gateway_namespace} with {'IP' if ip_match else 'hostname'} {ip}"
            )
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

    def _patch_controller_status(self, ip: str) -> None:
        for gateway in self._gateways_cache.values():
            self._patch_gateway_status(gateway, ip)
