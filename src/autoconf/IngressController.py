#!/usr/bin/python3

from os import getenv
from time import sleep
from traceback import format_exc
from typing import List
from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException
from threading import Thread, Lock

from Controller import Controller
from ConfigCaller import ConfigCaller  # type: ignore
from logger import setup_logger  # type: ignore


class IngressController(Controller, ConfigCaller):
    def __init__(self):
        Controller.__init__(self, "kubernetes")
        ConfigCaller.__init__(self)
        config.load_incluster_config()
        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()
        self.__internal_lock = Lock()
        self.__logger = setup_logger("Ingress-controller", getenv("LOG_LEVEL", "INFO"))

    def _get_controller_instances(self) -> list:
        return [
            pod
            for pod in self.__corev1.list_pod_for_all_namespaces(watch=False).items
            if (
                pod.metadata.annotations
                and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
            )
        ]

    def _to_instances(self, controller_instance) -> List[dict]:
        instance = {}
        instance["name"] = controller_instance.metadata.name
        instance["hostname"] = controller_instance.status.pod_ip
        health = False
        if controller_instance.status.conditions:
            for condition in controller_instance.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    health = True
                    break
        instance["health"] = health
        instance["env"] = {}
        pod = None
        for container in controller_instance.spec.containers:
            if container.name == "bunkerweb":
                pod = container
                break
        if not pod:
            self.__logger.warning(
                f"Missing container bunkerweb in pod {controller_instance.metadata.name}"
            )
        else:
            for env in pod.env:
                instance["env"][env.name] = env.value or ""
        for controller_service in self._get_controller_services():
            if controller_service.metadata.annotations:
                for (
                    annotation,
                    value,
                ) in controller_service.metadata.annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue
                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    if self._is_setting(variable):
                        instance["env"][variable] = value
        return [instance]

    def _get_controller_services(self) -> list:
        return self.__networkingv1.list_ingress_for_all_namespaces(watch=False).items

    def _to_services(self, controller_service) -> List[dict]:
        if not controller_service.spec or not controller_service.spec.rules:
            return []

        services = []
        # parse rules
        for rule in controller_service.spec.rules:
            if not rule.host:
                self.__logger.warning(
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
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without path.",
                    )
                    continue
                elif not path.backend.service:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service.",
                    )
                    continue
                elif not path.backend.service.port:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service port.",
                    )
                    continue
                elif not path.backend.service.port.number:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service port number.",
                    )
                    continue

                service_list = self.__corev1.list_service_for_all_namespaces(
                    watch=False,
                    field_selector=f"metadata.name={path.backend.service.name}",
                ).items

                if not service_list:
                    self.__logger.warning(
                        f"Ignoring ingress rule with service {path.backend.service.name} : service not found.",
                    )
                    continue

                reverse_proxy_host = f"http://{path.backend.service.name}.{service_list[0].metadata.namespace}.svc.cluster.local:{path.backend.service.port.number}"
                service.update(
                    {
                        "USE_REVERSE_PROXY": "yes",
                        f"REVERSE_PROXY_HOST_{location}": reverse_proxy_host,
                        f"REVERSE_PROXY_URL_{location}": path.path,
                    }
                )
                location += 1
            services.append(service)

        # parse tls
        if controller_service.spec.tls:  # TODO: support tls
            self.__logger.warning("Ignoring unsupported tls.")

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
        return services

    def _get_static_services(self) -> List[dict]:
        services = []
        variables = {}
        for instance in self.__corev1.list_pod_for_all_namespaces(watch=False).items:
            if (
                not instance.metadata.annotations
                or not "bunkerweb.io/INSTANCE" in instance.metadata.annotations
            ):
                continue

            pod = None
            for container in instance.spec.containers:
                if container.name == "bunkerweb":
                    pod = container
                    break
            if not pod:
                continue

            variables = {env.name: env.value or "" for env in pod.env}

        if "SERVER_NAME" in variables and variables["SERVER_NAME"].strip():
            for server_name in variables["SERVER_NAME"].strip().split(" "):
                service = {"SERVER_NAME": server_name}
                for variable, value in variables.items():
                    prefix = variable.split("_")[0]
                    real_variable = variable.replace(f"{prefix}_", "", 1)
                    if prefix == server_name and self._is_setting_context(
                        real_variable, "multisite"
                    ):
                        service[real_variable] = value
                services.append(service)
        return services

    def get_configs(self) -> dict:
        configs = {config_type: {} for config_type in self._supported_config_types}
        for configmap in self.__corev1.list_config_map_for_all_namespaces(
            watch=False
        ).items:
            if (
                not configmap.metadata.annotations
                or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations
            ):
                continue

            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in self._supported_config_types:
                self.__logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}",
                )
                continue
            elif not configmap.data:
                self.__logger.warning(
                    f"Ignoring blank ConfigMap {configmap.metadata.name}",
                )
                continue
            config_site = ""
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
                if not self._is_service_present(
                    configmap.metadata.annotations["bunkerweb.io/CONFIG_SITE"]
                ):
                    self.__logger.warning(
                        f"Ignoring config {configmap.metadata.name} because {configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']} doesn't exist",
                    )
                    continue
                config_site = (
                    f"{configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']}/"
                )
            for config_name, config_data in configmap.data.items():
                configs[config_type][f"{config_site}{config_name}"] = config_data
        return configs

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
        else:
            raise Exception(f"Unsupported watch_type {watch_type}")

        while True:
            locked = False
            error = False
            try:
                for _ in w.stream(what):
                    self.__internal_lock.acquire()
                    locked = True
                    self._instances = self.get_instances()
                    self._services = self.get_services()
                    self._configs = self.get_configs()
                    if not self._config.update_needed(
                        self._instances, self._services, configs=self._configs
                    ):
                        self.__internal_lock.release()
                        locked = False
                        continue
                    self.__logger.info(
                        f"Catched kubernetes event ({watch_type}), deploying new configuration ...",
                    )
                    try:
                        ret = self.apply_config()
                        if not ret:
                            self.__logger.error(
                                "Error while deploying new configuration ...",
                            )
                        else:
                            self.__logger.info(
                                "Successfully deployed new configuration 🚀",
                            )

                            if not self._config._db.is_autoconf_loaded():
                                ret = self._config._db.set_autoconf_load(True)
                                if ret:
                                    self.__logger.warning(
                                        f"Can't set autoconf loaded metadata to true in database: {ret}",
                                    )
                    except:
                        self.__logger.error(
                            f"Exception while deploying new configuration :\n{format_exc()}",
                        )
                    self.__internal_lock.release()
                    locked = False
            except ApiException as e:
                if e.status != 410:
                    self.__logger.error(
                        f"API exception while reading k8s event (type = {watch_type}) :\n{format_exc()}",
                    )
                    error = True
            except:
                self.__logger.error(
                    f"Unknown exception while reading k8s event (type = {watch_type}) :\n{format_exc()}",
                )
                error = True
            finally:
                if locked:
                    self.__internal_lock.release()
                    locked = False

                if error is True:
                    self.__logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def apply_config(self) -> bool:
        return self._config.apply(
            self._instances, self._services, configs=self._configs
        )

    def process_events(self):
        self._set_autoconf_load_db()
        watch_types = ("pod", "ingress", "configmap", "service")
        threads = [
            Thread(target=self.__watch, args=(watch_type,))
            for watch_type in watch_types
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
