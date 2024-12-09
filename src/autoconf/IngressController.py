#!/usr/bin/env python3

from contextlib import suppress
from os import getenv
from time import sleep
from traceback import format_exc
from typing import List
from kubernetes import client, config, watch
from kubernetes.client import Configuration
from kubernetes.client.exceptions import ApiException
from threading import Thread, Lock

from Controller import Controller


class IngressController(Controller):
    def __init__(self):
        self.__internal_lock = Lock()
        super().__init__("kubernetes")
        config.load_incluster_config()

        Configuration._default.verify_ssl = getenv("KUBERNETES_VERIFY_SSL", "yes").lower().strip() == "yes"
        self._logger.info(f"SSL verification is {'enabled' if Configuration._default.verify_ssl else 'disabled'}")

        ssl_ca_cert = getenv("KUBERNETES_SSL_CA_CERT", "")
        if ssl_ca_cert:
            Configuration._default.ssl_ca_cert = ssl_ca_cert
            self._logger.info("Using custom SSL CA certificate")

        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()

        self.__use_fqdn = getenv("USE_KUBERNETES_FQDN", "yes").lower().strip() == "yes"
        self._logger.info(f"Using Pod {'FQDN' if self.__use_fqdn else 'IP'} as hostname")

        self.__ingress_class = getenv("KUBERNETES_INGRESS_CLASS", "")
        if self.__ingress_class:
            self._logger.info(f"Using Ingress class: {self.__ingress_class}")

        self.__domain_name = getenv("KUBERNETES_DOMAIN_NAME", "cluster.local")
        self._logger.info(f"Using domain name: {self.__domain_name}")

        self.__service_protocol = getenv("KUBERNETES_SERVICE_PROTOCOL", "http").lower().strip()
        if self.__service_protocol not in ("http", "https"):
            self._logger.warning(f"Unsupported service protocol {self.__service_protocol}")
            self.__service_protocol = "http"
        self._logger.info(f"Using service protocol: {self.__service_protocol}")

    def _get_controller_instances(self) -> list:
        instances = []
        pods = self.__corev1.list_pod_for_all_namespaces(watch=False).items
        for pod in pods:
            if (
                pod.metadata.annotations
                and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                and (pod.metadata.namespace in self._namespaces if self._namespaces else True)
            ):
                instances.append(pod)
        return instances

    def _get_controller_services(self) -> list:
        services = []
        ingresses = self.__networkingv1.list_ingress_for_all_namespaces(watch=False).items
        for ingress in ingresses:
            # Skip if ingress class doesn't match (when specified)
            if self.__ingress_class:
                ingress_class_name = getattr(ingress.spec, "ingress_class_name", None)
                if ingress_class_name != self.__ingress_class:
                    continue

            # Skip if the namespace is not in the allowed namespaces (when specified)
            if self._namespaces and ingress.metadata.namespace not in self._namespaces:
                continue

            # Add the ingress to services if it passes all checks
            services.append(ingress)
        return services

    def _to_instances(self, controller_instance) -> List[dict]:
        instance = {
            "name": controller_instance.metadata.name,
            "hostname": (
                f"{controller_instance.status.pod_ip.replace('.','-')}.{controller_instance.metadata.namespace}.pod.{self.__domain_name}"
                if self.__use_fqdn
                else (controller_instance.status.pod_ip or controller_instance.metadata.name)
            ),
            "health": False,
            "type": "pod",
            "env": {},
        }

        if controller_instance.status.conditions:
            for condition in controller_instance.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    instance["health"] = True
                    break

        pod = None
        for container in controller_instance.spec.containers:
            if container.name == "bunkerweb":
                pod = container
                break

        if not pod:
            self._logger.warning(f"Missing container bunkerweb in pod {controller_instance.metadata.name}")
        elif pod.env:
            for env in pod.env:
                instance["env"][env.name] = env.value or ""

        for controller_service in self._get_controller_services():
            if controller_service.metadata.annotations:
                for annotation, value in controller_service.metadata.annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue
                    instance["env"][annotation.replace("bunkerweb.io/", "", 1)] = value

        return [instance]

    def _to_services(self, controller_service) -> List[dict]:
        if not controller_service.spec or not controller_service.spec.rules:
            return []

        namespace = controller_service.metadata.namespace
        services = []
        # parse rules
        for rule in controller_service.spec.rules:
            if not rule.host:
                self._logger.warning("Ignoring unsupported ingress rule without host.")
                continue

            service = {}
            service["SERVER_NAME"] = rule.host
            if not rule.http:
                services.append(service)
                continue

            for location, path in enumerate(rule.http.paths, start=1):
                if not path.path:
                    self._logger.warning("Ignoring unsupported ingress rule without path.")
                    continue
                elif not path.backend.service:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service.")
                    continue
                elif not path.backend.service.port:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service port.")
                    continue
                elif not path.backend.service.port.number and not path.backend.service.port.name:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service port number or name.")
                    continue

                service_list = self.__corev1.list_namespaced_service(
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

                reverse_proxy_host = f"{self.__service_protocol}://{path.backend.service.name}.{namespace}.svc.{self.__domain_name}"
                if port != 80:
                    reverse_proxy_host += f":{port}"

                service.update(
                    {
                        "USE_REVERSE_PROXY": "yes",
                        f"REVERSE_PROXY_HOST_{location}": reverse_proxy_host,
                        f"REVERSE_PROXY_URL_{location}": path.path,
                    }
                )
            services.append(service)

        # parse annotations
        if controller_service.metadata.annotations:
            for service in services:
                for annotation, value in controller_service.metadata.annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue

                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    server_name = service["SERVER_NAME"].strip().split(" ")[0]
                    service[variable.replace(f"{server_name}_", "", 1)] = value

        # parse tls
        if controller_service.spec.tls:
            for tls in controller_service.spec.tls:
                if tls.hosts and tls.secret_name:
                    for host in tls.hosts:
                        for service in services:
                            if host in service["SERVER_NAME"].split(" "):
                                secrets_tls = self.__corev1.list_namespaced_secret(
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

    def get_configs(self) -> dict:
        configs = {config_type: {} for config_type in self._supported_config_types}
        for configmap in self.__corev1.list_config_map_for_all_namespaces(watch=False).items:
            if (
                not configmap.metadata.annotations
                or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations
                or not (configmap.metadata.namespace in self._namespaces if self._namespaces else True)
            ):
                continue

            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in self._supported_config_types:
                self._logger.warning(f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}")
                continue
            elif not configmap.data:
                self._logger.warning(f"Ignoring blank ConfigMap {configmap.metadata.name}")
                continue

            config_site = ""
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
                if not self._is_service_present(configmap.metadata.annotations["bunkerweb.io/CONFIG_SITE"]):
                    self._logger.warning(
                        f"Ignoring config {configmap.metadata.name} because {configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']} doesn't exist"
                    )
                    continue
                config_site = f"{configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']}/"

            for config_name, config_data in configmap.data.items():
                configs[config_type][f"{config_site}{config_name}"] = config_data
        return configs

    def __process_event(self, event):
        obj = event["object"]
        if not obj:
            return False

        if obj.metadata and self._namespaces and obj.metadata.namespace not in self._namespaces:
            return False

        annotations = obj.metadata.annotations if obj.metadata else None
        data = getattr(obj, "data", None)

        ret = False
        if obj.kind == "Pod":
            ret = annotations and "bunkerweb.io/INSTANCE" in annotations
        elif obj.kind == "Ingress":
            if self.__ingress_class:
                ingress_class_name = getattr(obj.spec, "ingress_class_name", None)
                if not ingress_class_name or ingress_class_name != self.__ingress_class:
                    ret = False
            else:
                ret = True
        elif obj.kind == "ConfigMap":
            ret = annotations and "bunkerweb.io/CONFIG_TYPE" in annotations
        elif obj.kind == "Service":
            ret = True
        elif obj.kind == "Secret":
            ret = data and "tls.crt" in data and "tls.key" in data

        if ret:
            self._logger.debug(f"Processing event {event['type']} for {obj.kind} {obj.metadata.name if obj.metadata else 'unknown'}")

        return ret

    def __watch(self, watch_type):
        while True:
            w = watch.Watch()
            what = None
            if watch_type == "pod":
                what = self.__corev1.list_pod_for_all_namespaces
            elif watch_type == "ingress":
                what = self.__networkingv1.list_ingress_for_all_namespaces
            elif watch_type == "configmap":
                what = self.__corev1.list_config_map_for_all_namespaces
            elif watch_type == "service":
                what = self.__corev1.list_service_for_all_namespaces
            elif watch_type == "secret":
                what = self.__corev1.list_secret_for_all_namespaces
            else:
                raise Exception(f"Unsupported watch_type {watch_type}")

            locked = False
            error = False
            applied = False
            try:
                for event in w.stream(what):
                    applied = False
                    self.__internal_lock.acquire()
                    locked = True
                    if not self.__process_event(event):
                        self.__internal_lock.release()
                        locked = False
                        continue

                    to_apply = False
                    while not applied:
                        waiting = self.have_to_wait()
                        self._update_settings()
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._configs = self.get_configs()

                        if not to_apply and not self.update_needed(self._instances, self._services, configs=self._configs):
                            if locked:
                                self.__internal_lock.release()
                                locked = False
                            applied = True
                            continue

                        to_apply = True
                        if waiting:
                            sleep(1)
                            continue

                        self._logger.info(f"Caught kubernetes event ({watch_type}), deploying new configuration ...")
                        try:
                            ret = self.apply_config()
                            if not ret:
                                self._logger.error("Error while deploying new configuration ...")
                            else:
                                self._logger.info("Successfully deployed new configuration 🚀")

                                self._set_autoconf_load_db()
                        except:
                            self._logger.error(f"Exception while deploying new configuration :\n{format_exc()}")
                        applied = True

                    if locked:
                        self.__internal_lock.release()
                        locked = False
            except ApiException as e:
                if e.status != 410:
                    self._logger.error(f"API exception while reading k8s event (type = {watch_type}) :\n{format_exc()}")
                    error = True
            except:
                self._logger.error(f"Unknown exception while reading k8s event (type = {watch_type}) :\n{format_exc()}")
                error = True
            finally:
                if locked:
                    with suppress(BaseException):
                        self.__internal_lock.release()
                    locked = False

                if error is True:
                    self._logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def apply_config(self) -> bool:
        return self.apply(
            self._instances,
            self._services,
            configs=self._configs,
            first=not self._loaded,
        )

    def process_events(self):
        self._set_autoconf_load_db()
        watch_types = ("pod", "ingress", "configmap", "service", "secret")
        threads = [Thread(target=self.__watch, args=(watch_type,)) for watch_type in watch_types]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
