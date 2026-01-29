#!/usr/bin/env python3

from os import getenv
from traceback import format_exc
from typing import List

from kubernetes import client
from kubernetes.client.exceptions import ApiException

from controllers.KubernetesController import KubernetesController


class IngressController(KubernetesController):
    def __init__(self):
        super().__init__()
        self._networkingv1 = client.NetworkingV1Api()

        self._ingress_class = getenv("KUBERNETES_INGRESS_CLASS", "")
        if self._ingress_class:
            self._logger.info(f"Using Ingress class: {self._ingress_class}")

    def _get_controller_services(self) -> list:
        services = []
        ingresses = self._networkingv1.list_ingress_for_all_namespaces(watch=False).items
        for ingress in ingresses:
            if self._ingress_class:
                ingress_class_name = getattr(ingress.spec, "ingress_class_name", None)
                if ingress_class_name != self._ingress_class:
                    self._logger.debug(f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because its ingress class is not allowed")
                    continue

            if self._namespaces and ingress.metadata.namespace not in self._namespaces:
                self._logger.debug(
                    f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because its namespace is not in the allowed namespaces"
                )
                continue

            if ingress.metadata.annotations and any(self._should_ignore_annotation(annotation) for annotation in ingress.metadata.annotations):
                self._logger.debug(f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because of ignored annotations")
                continue

            services.append(ingress)
        return services

    def _to_services(self, controller_service) -> List[dict]:
        if not controller_service.spec or not controller_service.spec.rules:
            return []

        namespace = controller_service.metadata.namespace
        services = []
        server_names = set()

        for rule in controller_service.spec.rules:
            if not rule.host:
                self._logger.warning("Ignoring unsupported ingress rule without host.")
                continue

            service = {}
            service["SERVER_NAME"] = rule.host
            server_names.add(rule.host)
            if not rule.http:
                services.append(service)
                continue

            for location, path in enumerate(rule.http.paths, start=self._reverse_proxy_suffix_start):  # type: ignore
                if not path.path:
                    self._logger.warning("Ignoring unsupported ingress rule without path.")
                    continue
                elif not path.backend.service:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service.")
                    continue
                elif not path.backend.service.port:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service port.")
                    continue

                service_list = self._corev1.list_namespaced_service(
                    namespace,
                    watch=False,
                    field_selector=f"metadata.name={path.backend.service.name}",
                ).items

                if not service_list:
                    self._logger.warning(f"Ignoring ingress rule with service {path.backend.service.name} : service not found.")
                    continue

                port = 80
                if path.backend.service.port.name:
                    k8s_service = service_list[0]
                    for svc_port in k8s_service.spec.ports:
                        if svc_port.name == path.backend.service.port.name:
                            port = svc_port.port
                            break
                else:
                    port = path.backend.service.port.number

                reverse_proxy_host = f"{self._service_protocol}://{path.backend.service.name}.{namespace}.svc.{self._domain_name}"
                if port != 80:
                    reverse_proxy_host += f":{port}"

                service.update(
                    {
                        "USE_REVERSE_PROXY": "yes",
                        f"REVERSE_PROXY_HOST_{location}" if location else "REVERSE_PROXY_HOST": reverse_proxy_host,
                        f"REVERSE_PROXY_URL_{location}" if location else "REVERSE_PROXY_URL": path.path,
                    }
                )
            services.append(service)

        if controller_service.metadata.annotations:
            for service in services:
                server_name = service["SERVER_NAME"].strip().split(" ")[0]

                for annotation, value in controller_service.metadata.annotations.items():
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
                        for setting in service.copy():
                            if setting.startswith(f"{server_name}_REVERSE_PROXY_HOST"):
                                if not reverse_proxy_found:
                                    reverse_proxy_found = True
                                    suffix = setting.removeprefix(f"{server_name}_REVERSE_PROXY_HOST").removeprefix("_")
                                    service[f"{server_name}_REVERSE_PROXY_HOST"] = service.pop(setting).replace(f"{self._service_protocol}://", "", 1)
                                    service[f"{server_name}_REVERSE_PROXY_URL"] = service.pop(
                                        f"{server_name}_REVERSE_PROXY_URL_{suffix}" if suffix else f"{server_name}_REVERSE_PROXY_URL", "/"
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

        if controller_service.spec.tls:
            for tls in controller_service.spec.tls:
                if tls.hosts and tls.secret_name:
                    for host in tls.hosts:
                        for service in services:
                            if host in service["SERVER_NAME"].split():
                                secrets_tls = self._corev1.list_namespaced_secret(
                                    namespace,
                                    watch=False,
                                    field_selector=f"metadata.name={tls.secret_name}",
                                ).items

                                if not secrets_tls:
                                    self._logger.warning(f"Ignoring tls setting for {host} : secret {tls.secret_name} not found.")
                                    break

                                secret_tls = secrets_tls[0]
                                if not secret_tls.data:
                                    self._logger.warning(f"Ignoring tls setting for {host} : secret {tls.secret_name} contains no data.")
                                    break
                                elif "tls.crt" not in secret_tls.data or "tls.key" not in secret_tls.data:
                                    self._logger.warning(f"Ignoring tls setting for {host} : secret {tls.secret_name} is missing tls data.")
                                    break

                                service["USE_CUSTOM_SSL"] = "yes"
                                service["CUSTOM_SSL_CERT_DATA"] = secret_tls.data["tls.crt"]
                                service["CUSTOM_SSL_KEY_DATA"] = secret_tls.data["tls.key"]

        return services

    def _is_custom_event(self, kind, obj, annotations, namespace, name) -> bool:
        if kind != "Ingress":
            return False

        if self._ingress_class:
            ingress_class_name = getattr(obj.spec, "ingress_class_name", None)
            return ingress_class_name and ingress_class_name == self._ingress_class

        return True

    def _get_watchers(self):
        return {
            "pod": self._corev1.list_pod_for_all_namespaces,
            "ingress": self._networkingv1.list_ingress_for_all_namespaces,
            "configmap": self._corev1.list_config_map_for_all_namespaces,
            "service": self._corev1.list_service_for_all_namespaces,
            "secret": self._corev1.list_secret_for_all_namespaces,
        }

    def _patch_ingress_status(self, ingress, ip: str) -> bool:
        if not ip:
            self._logger.warning("Cannot patch ingress without IP address")
            return False

        if not ingress or not ingress.metadata:
            self._logger.error("Invalid ingress object provided for status patching")
            return False

        ingress_name = ingress.metadata.name
        ingress_namespace = ingress.metadata.namespace

        if not ingress_name or not ingress_namespace:
            self._logger.error("Ingress name or namespace is empty, cannot patch status")
            return False

        patch_body = {"status": {"loadBalancer": {"ingress": []}}}
        ip_match = self._ip_pattern.match(ip)

        if ip_match:
            patch_body["status"]["loadBalancer"]["ingress"].append({"ip": ip})
        else:
            patch_body["status"]["loadBalancer"]["ingress"].append({"hostname": ip})

        try:
            self._networkingv1.patch_namespaced_ingress_status(name=ingress_name, namespace=ingress_namespace, body=patch_body)
            self._logger.info(
                f"Successfully patched status of ingress {ingress_name} in namespace {ingress_namespace} with {'IP' if ip_match else 'hostname'} {ip}"
            )
            return True
        except ApiException as e:
            if e.status == 404:
                self._logger.warning(f"Ingress {ingress_name} not found in namespace {ingress_namespace}, skipping status patch")
            elif e.status == 403:
                self._logger.warning(f"Insufficient permissions to patch ingress {ingress_name} status in namespace {ingress_namespace}")
            elif e.status == 422:
                self._logger.error(f"Invalid patch data for ingress {ingress_name} in namespace {ingress_namespace}: {e.reason}")
                self._logger.debug(f"Patch body was: {patch_body}")
            else:
                self._logger.error(f"API error patching ingress {ingress_name} in namespace {ingress_namespace}: {e.status} - {e.reason}")
            self._logger.debug(format_exc())
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error patching ingress {ingress_name} in namespace {ingress_namespace}: {e}")
            self._logger.debug(format_exc())
            return False

    def _patch_controller_status(self, ip: str) -> None:
        for ingress in self._get_controller_services():
            self._patch_ingress_status(ingress, ip)
