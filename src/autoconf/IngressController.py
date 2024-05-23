#!/usr/bin/env python3

from contextlib import suppress
from time import sleep
from traceback import format_exc
from typing import Dict, List
from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException
from threading import Thread, Lock

from Controller import Controller


class IngressController(Controller):
    def __init__(self):
        self.__internal_lock = Lock()
        super().__init__("kubernetes")
        config.load_incluster_config()
        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()

    def _get_controller_instances(self) -> list:
        return [
            pod
            for pod in self.__corev1.list_pod_for_all_namespaces(watch=False).items
            if (pod.metadata.annotations and "bunkerweb.io/INSTANCE" in pod.metadata.annotations)
        ]

    def _to_instances(self, controller_instance) -> List[dict]:
        instance = {
            "name": controller_instance.metadata.name,
            "hostname": controller_instance.metadata.name,
            "env": self._get_scheduler_env(),
        }
        health = False
        if controller_instance.status.conditions:
            for condition in controller_instance.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    health = True
                    break
        instance["health"] = health
        return [instance]

    def _get_controller_services(self) -> list:
        return self.__networkingv1.list_ingress_for_all_namespaces(watch=False).items

    def _to_services(self, controller_service) -> List[dict]:
        if not controller_service.spec or not controller_service.spec.rules:
            return []
        namespace = controller_service.metadata.namespace
        services = []
        # parse rules
        for rule in controller_service.spec.rules:
            if not rule.host:
                self._logger.warning(
                    "Ignoring unsupported ingress rule without host.",
                )
                continue
            service = {}
            service["SERVER_NAME"] = rule.host
            if not rule.http:
                services.append(service)
                continue
            location = 1
            for path in rule.http.paths:
                if not path.path:
                    self._logger.warning(
                        "Ignoring unsupported ingress rule without path.",
                    )
                    continue
                elif not path.backend.service:
                    self._logger.warning(
                        "Ignoring unsupported ingress rule without backend service.",
                    )
                    continue
                elif not path.backend.service.port:
                    self._logger.warning(
                        "Ignoring unsupported ingress rule without backend service port.",
                    )
                    continue
                elif not path.backend.service.port.number:
                    self._logger.warning(
                        "Ignoring unsupported ingress rule without backend service port number.",
                    )
                    continue

                service_list = self.__corev1.list_service_for_all_namespaces(
                    watch=False,
                    field_selector=f"metadata.name={path.backend.service.name},metadata.namespace={namespace}",
                ).items

                if not service_list:
                    self._logger.warning(
                        f"Ignoring ingress rule with service {path.backend.service.name} : service not found.",
                    )
                    continue

                reverse_proxy_host = f"http://{path.backend.service.name}.{namespace}.svc.cluster.local:{path.backend.service.port.number}"
                service.update(
                    {
                        "USE_REVERSE_PROXY": "yes",
                        f"REVERSE_PROXY_HOST_{location}": reverse_proxy_host,
                        f"REVERSE_PROXY_URL_{location}": path.path,
                    }
                )
                location += 1
            services.append(service)

        # parse annotations
        if controller_service.metadata.annotations:
            for service in services:
                for (
                    annotation,
                    value,
                ) in controller_service.metadata.annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue

                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    server_name = service["SERVER_NAME"].strip().split(" ")[0]
                    if not variable.startswith(f"{server_name}_"):
                        continue
                    variable = variable.replace(f"{server_name}_", "", 1)
                    if self._is_setting_context(variable, "multisite"):
                        service[variable] = value

        # parse tls
        if controller_service.spec.tls:
            for tls in controller_service.spec.tls:
                if tls.hosts and tls.secret_name:
                    for host in tls.hosts:
                        for service in services:
                            if host in service["SERVER_NAME"].split(" "):
                                secrets_tls = self.__corev1.list_secret_for_all_namespaces(
                                    watch=False,
                                    field_selector=f"metadata.name={tls.secret_name},metadata.namespace={namespace}",
                                ).items
                                if len(secrets_tls) == 0:
                                    self._logger.warning(
                                        f"Ignoring tls setting for {host} : secret {tls.secret_name} not found.",
                                    )
                                    break
                                secret_tls = secrets_tls[0]
                                if not secret_tls.data:
                                    self._logger.warning(
                                        f"Ignoring tls setting for {host} : secret {tls.secret_name} contains no data.",
                                    )
                                    break
                                if "tls.crt" not in secret_tls.data or "tls.key" not in secret_tls.data:
                                    self._logger.warning(
                                        f"Ignoring tls setting for {host} : secret {tls.secret_name} is missing tls data.",
                                    )
                                    break
                                service["USE_CUSTOM_SSL"] = "yes"
                                service["CUSTOM_SSL_CERT_DATA"] = secret_tls.data["tls.crt"]
                                service["CUSTOM_SSL_KEY_DATA"] = secret_tls.data["tls.key"]
        return services

    def _get_scheduler_env(self) -> Dict[str, str]:
        variables = {}
        for instance in self.__corev1.list_pod_for_all_namespaces(watch=False).items:
            if not instance.metadata.annotations or "bunkerweb.io/SCHEDULER" not in instance.metadata.annotations:
                continue

            pod = None
            for container in instance.spec.containers:
                if container.name == "bunkerweb-scheduler":
                    pod = container
                    break
            if not pod:
                continue

            variables = {env.name: env.value or "" for env in pod.env}
        return variables

    def _get_static_services(self) -> List[dict]:
        services = []
        variables = self._get_scheduler_env()
        if "SERVER_NAME" in variables and variables["SERVER_NAME"].strip():
            for server_name in variables["SERVER_NAME"].strip().split(" "):
                service = {"SERVER_NAME": server_name}
                for variable, value in variables.items():
                    prefix = variable.split("_")[0]
                    real_variable = variable.replace(f"{prefix}_", "", 1)
                    if prefix == server_name and self._is_setting_context(real_variable, "multisite"):
                        service[real_variable] = value
                services.append(service)
        return services

    def get_configs(self) -> dict:
        configs = {config_type: {} for config_type in self._supported_config_types}
        for configmap in self.__corev1.list_config_map_for_all_namespaces(watch=False).items:
            if not configmap.metadata.annotations or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations:
                continue

            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in self._supported_config_types:
                self._logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}",
                )
                continue
            elif not configmap.data:
                self._logger.warning(
                    f"Ignoring blank ConfigMap {configmap.metadata.name}",
                )
                continue
            config_site = ""
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
                if not self._is_service_present(configmap.metadata.annotations["bunkerweb.io/CONFIG_SITE"]):
                    self._logger.warning(
                        f"Ignoring config {configmap.metadata.name} because {configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']} doesn't exist",
                    )
                    continue
                config_site = f"{configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']}/"
            for config_name, config_data in configmap.data.items():
                configs[config_type][f"{config_site}{config_name}"] = config_data
        return configs

    def __process_event(self, event):
        obj = event["object"]
        metadata = obj.metadata if obj else None
        annotations = metadata.annotations if metadata else None
        data = getattr(obj, "data", None) if obj else None
        if not obj:
            return False
        if obj.kind == "Pod":
            return annotations and "bunkerweb.io/INSTANCE" in annotations
        if obj.kind == "Ingress":
            return True
        if obj.kind == "ConfigMap":
            return annotations and "bunkerweb.io/CONFIG_TYPE" in annotations
        if obj.kind == "Service":
            return True
        if obj.kind == "Secret":
            return data and "tls.crt" in data and "tls.key" in data
        return False

    def __watch(self, watch_type):
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

        while True:
            locked = False
            error = False
            try:
                for event in w.stream(what):
                    with self.__internal_lock:
                        locked = True
                        if not self.__process_event(event):
                            locked = False
                            continue
                        self.wait_applying()
                        self._update_settings()
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._configs = self.get_configs()
                        if not self.update_needed(self._instances, self._services, configs=self._configs):
                            locked = False
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
