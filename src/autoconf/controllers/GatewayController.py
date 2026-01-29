#!/usr/bin/env python3

from fnmatch import fnmatchcase
from os import getenv
from traceback import format_exc
from typing import Any, Dict, List, Optional, Tuple

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from controllers.KubernetesController import KubernetesController


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
        if self._gateway_api_version not in ("v1", "v1beta1"):
            self._logger.warning(f"Unsupported KUBERNETES_GATEWAY_API_VERSION {self._gateway_api_version}, defaulting to v1")
            self._gateway_api_version = "v1"

        self._gateway_api_available = self._check_gateway_api()

    def _check_gateway_api(self) -> bool:
        fallback_version = "v1beta1" if self._gateway_api_version == "v1" else "v1"
        versions = [self._gateway_api_version, fallback_version]
        for version in versions:
            try:
                self._custom_objects.list_cluster_custom_object(self._gateway_api_group, version, "gateways", limit=1)
                if version != self._gateway_api_version:
                    self._logger.info(f"Gateway API {self._gateway_api_version} not available, falling back to {version}")
                    self._gateway_api_version = version
                return True
            except ApiException as e:
                if e.status == 404:
                    self._logger.warning(f"Gateway API {version} not available (404)")
                    continue
                if e.status == 403:
                    self._logger.error(f"Insufficient permissions to access Gateway API {version}")
                    return False
                self._logger.error(f"Error while probing Gateway API {version}: {e.status} - {e.reason}")
                self._logger.debug(format_exc())
                return False
            except Exception as e:
                self._logger.error(f"Unexpected error while probing Gateway API {version}: {e}")
                self._logger.debug(format_exc())
                return False

        self._logger.warning("Gateway API CRDs not detected, controller will stay idle")
        return False

    def _hostname_matches(self, hostname: str, pattern: Optional[str]) -> bool:
        if not pattern:
            return True
        return fnmatchcase(hostname.lower(), pattern.lower())

    def _list_custom_objects(self, plural: str) -> List[Dict[str, Any]]:
        if not self._gateway_api_available:
            return []
        try:
            data = self._custom_objects.list_cluster_custom_object(
                self._gateway_api_group,
                self._gateway_api_version,
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
        for route in self._list_custom_objects("httproutes"):
            metadata = route.get("metadata") or {}
            namespace = metadata.get("namespace")
            name = metadata.get("name")
            if not namespace or not name:
                continue

            if self._namespaces and namespace not in self._namespaces:
                self._logger.debug(f"Skipping HTTPRoute {namespace}/{name} because its namespace is not allowed")
                continue

            annotations = metadata.get("annotations") or {}
            if annotations and any(self._should_ignore_annotation(annotation) for annotation in annotations):
                self._logger.debug(f"Skipping HTTPRoute {namespace}/{name} because of ignored annotations")
                continue

            if not self._route_targets_allowed_gateway(route, gateways):
                self._logger.debug(f"Skipping HTTPRoute {namespace}/{name} because it does not target an allowed Gateway")
                continue

            routes.append(route)

        self._gateways_cache = gateways
        return routes

    def _get_controller_services(self) -> list:
        return self._get_controller_routes()

    def _get_service_annotations(self, controller_service) -> Dict[str, str]:
        metadata = controller_service.get("metadata") or {}
        return metadata.get("annotations") or {}

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
        metadata, spec = (route.get("metadata") or {}), (route.get("spec") or {})
        route_namespace = metadata.get("namespace")
        parent_refs = spec.get("parentRefs") or []

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
            listeners = (gateway.get("spec") or {}).get("listeners") or []
            for listener in listeners:
                if section_name and listener.get("name") != section_name:
                    continue

                protocol = (listener.get("protocol") or "").upper()
                if protocol not in ("HTTPS", "TLS"):
                    continue

                listener_hostname = listener.get("hostname")
                if listener_hostname and not self._hostname_matches(hostname, listener_hostname):
                    continue

                tls = listener.get("tls") or {}
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

    def _to_services(self, controller_service) -> List[dict]:
        metadata = controller_service.get("metadata") or {}
        spec = controller_service.get("spec") or {}
        namespace = metadata.get("namespace")
        name = metadata.get("name")

        hostnames = spec.get("hostnames") or []
        if not hostnames:
            self._logger.warning(f"Ignoring HTTPRoute {namespace}/{name} without hostnames")
            return []

        services: List[Dict[str, Any]] = []
        server_names = set(hostnames)
        rules = spec.get("rules") or []

        for host in hostnames:
            service: Dict[str, Any] = {"SERVER_NAME": host}
            location = self._reverse_proxy_suffix_start

            if not rules:
                services.append(service)
                continue

            for rule in rules:
                matches = rule.get("matches") or [None]
                backend_refs = rule.get("backendRefs") or []
                if not backend_refs:
                    self._logger.warning(f"Ignoring HTTPRoute rule without backendRefs in {namespace}/{name}")
                    continue

                backend_ref = backend_refs[0]
                if len(backend_refs) > 1:
                    self._logger.warning(f"HTTPRoute {namespace}/{name} has multiple backendRefs for a rule, using only the first one")

                if not isinstance(backend_ref, dict):
                    continue

                kind = backend_ref.get("kind") or "Service"
                if kind != "Service":
                    self._logger.warning(f"Ignoring HTTPRoute backendRef with unsupported kind {kind} in {namespace}/{name}")
                    continue

                backend_name = backend_ref.get("name")
                backend_port = backend_ref.get("port")
                if not backend_name or not backend_port:
                    self._logger.warning(f"Ignoring HTTPRoute backendRef without name/port in {namespace}/{name}")
                    continue

                backend_namespace = backend_ref.get("namespace") or namespace
                if not backend_namespace:
                    self._logger.warning(f"Ignoring HTTPRoute backendRef without namespace in {namespace}/{name}")
                    continue

                for match in matches:
                    path_value = "/"
                    if isinstance(match, dict):
                        path = match.get("path")
                        if isinstance(path, dict) and path.get("value"):
                            path_value = path.get("value")

                    reverse_proxy_host = f"{self._service_protocol}://{backend_name}.{backend_namespace}.svc.{self._domain_name}"
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

        annotations = metadata.get("annotations") or {}
        if annotations:
            for service in services:
                server_name = service["SERVER_NAME"].strip().split(" ")[0]

                for annotation, value in annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue
                    setting = annotation.replace("bunkerweb.io/", "", 1)
                    success, _ = self._db.is_valid_setting(setting, value=value, multisite=True)
                    if success and not setting.startswith(f"{server_name}_"):
                        if any(setting.startswith(f"{s}_") for s in server_names):
                            continue
                        if setting == "SERVER_NAME":
                            self._logger.warning("Variable SERVER_NAME can't be set globally via annotations, ignoring it")
                            continue
                        setting = f"{server_name}_{setting}"
                    service[setting] = value

                for server_name in service["SERVER_NAME"].strip().split():
                    if service.get(f"{server_name}_SERVER_TYPE", service.get("SERVER_TYPE", "http")) == "stream":
                        reverse_proxy_found = False
                        warned = False
                        for setting in list(service.keys()):
                            if setting.startswith(f"{server_name}_REVERSE_PROXY_HOST"):
                                if not reverse_proxy_found:
                                    reverse_proxy_found = True
                                    suffix = setting.removeprefix(f"{server_name}_REVERSE_PROXY_HOST").removeprefix("_")
                                    service[f"{server_name}_REVERSE_PROXY_HOST"] = service.pop(setting).replace(f"{self._service_protocol}://", "", 1)
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
        return kind in ("HTTPRoute", "Gateway")

    def _get_watchers(self):
        watchers = {
            "pod": self._corev1.list_pod_for_all_namespaces,
            "configmap": self._corev1.list_config_map_for_all_namespaces,
            "service": self._corev1.list_service_for_all_namespaces,
            "secret": self._corev1.list_secret_for_all_namespaces,
        }

        if not self._gateway_api_available:
            return watchers

        def list_gateways(**kwargs):
            return self._custom_objects.list_cluster_custom_object(
                self._gateway_api_group,
                self._gateway_api_version,
                "gateways",
                **kwargs,
            )

        def list_httproutes(**kwargs):
            return self._custom_objects.list_cluster_custom_object(
                self._gateway_api_group,
                self._gateway_api_version,
                "httproutes",
                **kwargs,
            )

        watchers.update(
            {
                "gateway": list_gateways,
                "httproute": list_httproutes,
            }
        )

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
