from os import getenv
from time import sleep
from traceback import format_exc
from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException
from threading import Thread, Lock
from sys import exit as sys_exit

from Controller import Controller
from ConfigCaller import ConfigCaller
from logger import setup_logger


class IngressController(Controller, ConfigCaller):
    def __init__(self):
        Controller.__init__(self, "kubernetes")
        ConfigCaller.__init__(self)
        config.load_incluster_config()
        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()
        self.__internal_lock = Lock()
        self.__logger = setup_logger("Ingress-controller", getenv("LOG_LEVEL", "INFO"))

    def _get_controller_instances(self):
        controller_instances = []
        for pod in self.__corev1.list_pod_for_all_namespaces(watch=False).items:
            if (
                pod.metadata.annotations != None
                and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
            ):
                controller_instances.append(pod)
        return controller_instances

    def _to_instances(self, controller_instance):
        instance = {}
        instance["name"] = controller_instance.metadata.name
        instance["hostname"] = controller_instance.status.pod_ip
        health = False
        if controller_instance.status.conditions is not None:
            for condition in controller_instance.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    health = True
                    break
        instance["health"] = health
        instance["env"] = {}
        for env in controller_instance.spec.containers[0].env:
            if env.value is not None:
                instance["env"][env.name] = env.value
            else:
                instance["env"][env.name] = ""
        for controller_service in self._get_controller_services():
            if controller_service.metadata.annotations is not None:
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

    def _get_controller_services(self):
        return self.__networkingv1.list_ingress_for_all_namespaces(watch=False).items

    def _to_services(self, controller_service):
        if controller_service.spec is None or controller_service.spec.rules is None:
            return []
        services = []
        # parse rules
        for rule in controller_service.spec.rules:
            if rule.host is None:
                self.__logger.warning(
                    "Ignoring unsupported ingress rule without host.",
                )
                continue
            service = {}
            service["SERVER_NAME"] = rule.host
            if rule.http is None:
                services.append(service)
                continue
            location = 1
            for path in rule.http.paths:
                if path.path is None:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without path.",
                    )
                    continue
                if path.backend.service is None:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service.",
                    )
                    continue
                if path.backend.service.port is None:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service port.",
                    )
                    continue
                if path.backend.service.port.number is None:
                    self.__logger.warning(
                        "Ignoring unsupported ingress rule without backend service port number.",
                    )
                    continue
                service_list = self.__corev1.list_service_for_all_namespaces(
                    watch=False,
                    field_selector=f"metadata.name={path.backend.service.name}",
                ).items
                if len(service_list) == 0:
                    self.__logger.warning(
                        f"Ignoring ingress rule with service {path.backend.service.name} : service not found.",
                    )
                    continue
                reverse_proxy_host = f"http://{path.backend.service.name}.{service_list[0].metadata.namespace}.svc.cluster.local:{path.backend.service.port.number}"
                service["USE_REVERSE_PROXY"] = "yes"
                service[f"REVERSE_PROXY_HOST_{location}"] = reverse_proxy_host
                service[f"REVERSE_PROXY_URL_{location}"] = path.path
                location += 1
            services.append(service)

        # parse tls
        if controller_service.spec.tls is not None:
            self.__logger.warning("Ignoring unsupported tls.")

        # parse annotations
        if controller_service.metadata.annotations is not None:
            for service in services:
                for (
                    annotation,
                    value,
                ) in controller_service.metadata.annotations.items():
                    if not annotation.startswith("bunkerweb.io/"):
                        continue
                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    if not variable.startswith(
                        f"{service['SERVER_NAME'].split(' ')[0]}_"
                    ):
                        continue
                    variable = variable.replace(
                        f"{service['SERVER_NAME'].split(' ')[0]}_", "", 1
                    )
                    if self._is_multisite_setting(variable):
                        service[variable] = value
        return services

    def _get_static_services(self):
        services = []
        variables = {}
        for instance in self.__corev1.list_pod_for_all_namespaces(watch=False).items:
            if (
                instance.metadata.annotations is None
                or not "bunkerweb.io/INSTANCE" in instance.metadata.annotations
            ):
                continue
            for env in instance.spec.containers[0].env:
                if env.value is None:
                    variables[env.name] = ""
                else:
                    variables[env.name] = env.value
        server_names = []
        if "SERVER_NAME" in variables and variables["SERVER_NAME"] != "":
            server_names = variables["SERVER_NAME"].split(" ")
        for server_name in server_names:
            service = {}
            service["SERVER_NAME"] = server_name
            for variable, value in variables.items():
                prefix = variable.split("_")[0]
                real_variable = variable.replace(f"{prefix}_", "", 1)
                if prefix == server_name and self._is_multisite_setting(real_variable):
                    service[real_variable] = value
            services.append(service)
        return services

    def get_configs(self):
        configs = {}
        supported_config_types = [
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
        ]
        for config_type in supported_config_types:
            configs[config_type] = {}
        for configmap in self.__corev1.list_config_map_for_all_namespaces(
            watch=False
        ).items:
            if (
                configmap.metadata.annotations is None
                or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations
            ):
                continue
            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in supported_config_types:
                self.__logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}",
                )
                continue
            if not configmap.data:
                self.__logger.warning(
                    f"Ignoring blank ConfigMap {configmap.metadata.name}",
                )
                continue
            config_site = ""
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
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
        else:
            raise Exception(f"unsupported watch_type {watch_type}")
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
                        "Catched kubernetes event, deploying new configuration ...",
                    )
                    try:
                        ret = self.apply_config()
                        if not ret:
                            self.__logger.error(
                                "Error while deploying new configuration ...",
                            )
                            error = True
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
                        error = True
            except ApiException as e:
                if e.status != 410:
                    self.__logger.error(
                        f"Exception while reading k8s event (type = {watch_type}) :\n{format_exc()}",
                    )
            except:
                self.__logger.error(
                    f"Unknown exception while reading k8s event (type = {watch_type}) :\n{format_exc()}",
                )
            finally:
                if locked:
                    self.__internal_lock.release()
                    locked = False

                if error is True:
                    self.__logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def apply_config(self):
        ret = self._config.apply(self._instances, self._services, configs=self._configs)
        return ret

    def process_events(self):
        watch_types = ["pod", "ingress", "configmap"]
        threads = []
        for watch_type in watch_types:
            threads.append(Thread(target=self.__watch, args=(watch_type,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
