#!/usr/bin/env python3

from contextlib import suppress
from os import getenv
from re import compile as re_compile, split as re_split
from time import sleep, time
from traceback import format_exc
from typing import List, Optional, Tuple
from threading import Thread, Lock

from kubernetes import client, config, watch
from kubernetes.client import Configuration
from kubernetes.client.exceptions import ApiException

from Controller import Controller


class IngressController(Controller):
    def __init__(self):
        self.__internal_lock = Lock()
        self.__pending_apply = False
        self.__last_event_time = 0.0
        self.__debounce_delay = 2  # seconds
        super().__init__("kubernetes")
        config.load_incluster_config()
        self.__managed_configmaps = set()

        Configuration._default.verify_ssl = getenv("KUBERNETES_VERIFY_SSL", "yes").lower().strip() == "yes"
        self._logger.info(f"SSL verification is {'enabled' if Configuration._default.verify_ssl else 'disabled'}")

        ssl_ca_cert = getenv("KUBERNETES_SSL_CA_CERT", "")
        if ssl_ca_cert:
            Configuration._default.ssl_ca_cert = ssl_ca_cert
            self._logger.info("Using custom SSL CA certificate")

        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()
        self.__ip_pattern = re_compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")

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

        self.__service_name = getenv("BUNKERWEB_SERVICE_NAME", "bunkerweb")
        self.__namespace = getenv("BUNKERWEB_NAMESPACE", "bunkerweb")

        self.__ignored_annotations_exact = set()
        self.__ignored_annotation_suffixes = set()
        ignore_annotations = getenv("KUBERNETES_IGNORE_ANNOTATIONS", "")
        if ignore_annotations:
            tokens = [token.strip() for token in re_split(r"[,\s]+", ignore_annotations) if token.strip()]
            for token in tokens:
                if "/" in token:
                    self.__ignored_annotations_exact.add(token)
                    if token.startswith("bunkerweb.io/"):
                        suffix = token.split("/", 1)[1]
                        if suffix:
                            self.__ignored_annotation_suffixes.add(suffix)
                else:
                    self.__ignored_annotation_suffixes.add(token)
                    self.__ignored_annotations_exact.add(f"bunkerweb.io/{token}")

            self._logger.info("Ignoring annotations while collecting instances: " + ", ".join(sorted(self.__ignored_annotations_exact)))

        self.__reverse_proxy_suffix_start = getenv("KUBERNETES_REVERSE_PROXY_SUFFIX_START", "1").strip()
        if not self.__reverse_proxy_suffix_start.isdigit() or int(self.__reverse_proxy_suffix_start) < 0:
            self._logger.warning(f"Invalid KUBERNETES_REVERSE_PROXY_SUFFIX_START value {self.__reverse_proxy_suffix_start}, defaulting to 1")
            self.__reverse_proxy_suffix_start = "1"
        self.__reverse_proxy_suffix_start = int(self.__reverse_proxy_suffix_start)

    def __should_ignore_annotation(self, annotation: str) -> bool:
        if annotation in self.__ignored_annotations_exact:
            return True
        if annotation.removeprefix("bunkerweb.io/") in self.__ignored_annotation_suffixes:
            return True
        return False

    def _get_controller_instances(self) -> list:
        instances = []
        pods = self.__corev1.list_pod_for_all_namespaces(watch=False).items
        for pod in pods:
            metadata = pod.metadata
            if not metadata:
                continue

            annotations = metadata.annotations or {}
            if "bunkerweb.io/INSTANCE" not in annotations:
                continue

            if self._namespaces and metadata.namespace not in self._namespaces:
                self._logger.info(f"Skipping pod {metadata.namespace}/{metadata.name} because its namespace is not in the allowed namespaces")
                continue

            if any(self.__should_ignore_annotation(annotation) for annotation in annotations):
                self._logger.info(f"Skipping pod {metadata.namespace}/{metadata.name} because of ignored annotations")
                continue

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
                    self._logger.info(f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because its ingress class is not allowed")
                    continue

            # Skip if the namespace is not in the allowed namespaces (when specified)
            if self._namespaces and ingress.metadata.namespace not in self._namespaces:
                self._logger.info(
                    f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because its namespace is not in the allowed namespaces"
                )
                continue

            if ingress.metadata.annotations and any(self.__should_ignore_annotation(annotation) for annotation in ingress.metadata.annotations):
                self._logger.info(f"Skipping ingress {ingress.metadata.namespace}/{ingress.metadata.name} because of ignored annotations")
                continue

            # Add the ingress to services if it passes all checks
            services.append(ingress)
        return services

    def _to_instances(self, controller_instance) -> List[dict]:
        instance = {
            "name": controller_instance.metadata.name,
            "hostname": (
                f"{controller_instance.status.pod_ip.replace('.','-') if controller_instance.status.pod_ip else controller_instance.metadata.name}.{controller_instance.metadata.namespace}.pod.{self.__domain_name}"
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
        server_names = set()

        # parse rules
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

            for location, path in enumerate(rule.http.paths, start=self.__reverse_proxy_suffix_start):  # type: ignore
                if not path.path:
                    self._logger.warning("Ignoring unsupported ingress rule without path.")
                    continue
                elif not path.backend.service:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service.")
                    continue
                elif not path.backend.service.port:
                    self._logger.warning("Ignoring unsupported ingress rule without backend service port.")
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
                        f"REVERSE_PROXY_HOST_{location}" if location else "REVERSE_PROXY_HOST": reverse_proxy_host,
                        f"REVERSE_PROXY_URL_{location}" if location else "REVERSE_PROXY_URL": path.path,
                    }
                )
            services.append(service)

        # parse annotations
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

                # Handle stream services
                for server_name in service["SERVER_NAME"].strip().split(" "):
                    if service.get(f"{server_name}_SERVER_TYPE", service.get("SERVER_TYPE", "http")) == "stream":
                        reverse_proxy_found = False
                        warned = False
                        for setting in service.copy():
                            if setting.startswith(f"{server_name}_REVERSE_PROXY_HOST"):
                                if not reverse_proxy_found:
                                    reverse_proxy_found = True
                                    suffix = setting.removeprefix(f"{server_name}_REVERSE_PROXY_HOST").removeprefix("_")
                                    service[f"{server_name}_REVERSE_PROXY_HOST"] = service.pop(setting).replace(f"{self.__service_protocol}://", "", 1)
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

    def get_configs(self) -> Tuple[dict, dict]:
        configs = {config_type: {} for config_type in self._supported_config_types}
        config = {}
        managed_configmaps = set()
        for configmap in self.__corev1.list_config_map_for_all_namespaces(watch=False).items:
            if not configmap.metadata.annotations or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations:
                continue

            if self._namespaces and configmap.metadata.namespace not in self._namespaces:
                self._logger.info(
                    f"Skipping ConfigMap {configmap.metadata.namespace}/{configmap.metadata.name} because its namespace is not in the allowed namespaces"
                )
                continue

            if any(self.__should_ignore_annotation(annotation) for annotation in configmap.metadata.annotations):
                self._logger.info(f"Skipping ConfigMap {configmap.metadata.namespace}/{configmap.metadata.name} because of ignored annotations")
                continue

            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in set(self._supported_config_types) | {"settings"}:
                self._logger.warning(f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}")
                continue
            elif not configmap.data:
                self._logger.warning(f"Ignoring blank ConfigMap {configmap.metadata.name}")
                continue

            config_site = ""
            extra_services = []
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
                if not self._is_service_present(configmap.metadata.annotations["bunkerweb.io/CONFIG_SITE"]):
                    self._logger.warning(
                        f"Ignoring config {configmap.metadata.name} because {configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']} doesn't exist"
                    )
                    continue
                config_site = f"{configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']}/"

                for service in self._services:
                    service_name = service.get("SERVER_NAME", "")
                    if not service_name:
                        continue
                    extra_services.append(service_name.strip().split(" ")[0])

            managed_configmaps.add(f"{configmap.metadata.namespace}/{configmap.metadata.name}")

            if config_type == "settings":
                config_site = config_site.replace("/", "_")
                for config_name, config_data in configmap.data.items():
                    if config_site and not config_name.startswith(config_site):
                        config_name = f"{config_site}{config_name}"

                    if not self._db.is_valid_setting(config_name, value=config_data, multisite=bool(config_site), extra_services=extra_services)[0]:
                        self._logger.warning(f"Ignoring invalid setting {config_name} for ConfigMap {configmap.metadata.name}")
                        continue

                    config[config_name] = config_data
            else:
                for config_name, config_data in configmap.data.items():
                    configs[config_type][f"{config_site}{config_name}"] = config_data

        self.__managed_configmaps = managed_configmaps
        return config, configs

    def __process_event(self, event):
        if self._first_start:
            return True

        obj = event["object"]
        if not obj:
            return False

        if obj.metadata and self._namespaces and obj.metadata.namespace not in self._namespaces:
            self._logger.info(f"Skipping {obj.kind} {obj.metadata.namespace}/{obj.metadata.name} because its namespace is not in the allowed namespaces")
            return False

        annotations = obj.metadata.annotations if obj.metadata else None
        data = getattr(obj, "data", None)

        if annotations and any(self.__should_ignore_annotation(annotation) for annotation in annotations):
            self._logger.info(f"Skipping {obj.kind} {obj.metadata.namespace}/{obj.metadata.name} because of ignored annotations")
            return False

        ret = False
        if obj.kind == "Pod":
            ret = annotations and "bunkerweb.io/INSTANCE" in annotations
        elif obj.kind == "Ingress":
            if self.__ingress_class:
                ingress_class_name = getattr(obj.spec, "ingress_class_name", None)
                ret = ingress_class_name and ingress_class_name == self.__ingress_class
            else:
                ret = True
        elif obj.kind == "ConfigMap":
            cfg_name = ""
            if obj.metadata and obj.metadata.namespace and obj.metadata.name:
                cfg_name = f"{obj.metadata.namespace}/{obj.metadata.name}"
            event_type = event.get("type")
            is_managed = bool(cfg_name and cfg_name in self.__managed_configmaps)
            if event_type == "DELETED":
                ret = is_managed
            else:
                ret = bool((annotations and "bunkerweb.io/CONFIG_TYPE" in annotations) or is_managed)
        elif obj.kind == "Service":
            ret = True
        elif obj.kind == "Secret":
            ret = data and "tls.crt" in data and "tls.key" in data

        if ret:
            self._logger.debug(f"Processing event {event['type']} for {obj.kind} {obj.metadata.name if obj.metadata else 'unknown'}")

        return ret

    def __get_stream_with_retries(self, watch_type, what, retries=5):
        """
        Retry logic for streaming events with a capped retry limit.
        """
        attempt = 0
        ignored = False
        while attempt < retries:
            try:
                if not ignored:
                    self._logger.info(f"Starting Kubernetes watch for {watch_type}, attempt {attempt + 1}/{retries}")
                ignored = False
                yield from watch.Watch().stream(what)
            except ApiException as e:
                if e.status == 410 and "Expired: too old resource version: " in e.reason:
                    self._logger.debug(f"{e.reason} while watching {watch_type}, resetting watch stream")
                    ignored = True
                    attempt += 1
                    continue
                self._logger.debug(format_exc())
                self._logger.error(f"Unexpected ApiException while watching {watch_type}:\n{e}")
            except Exception as e:
                self._logger.debug(format_exc())
                self._logger.error(f"Unexpected error while watching {watch_type}:\n{e}")
            attempt += 1
            self._logger.warning(f"Retrying {watch_type} in 5 seconds...")
            sleep(5)
        self._logger.error(f"Failed to watch {watch_type} after {retries} retries.")

    def __watch(self, watch_type):
        while True:
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
                for event in self.__get_stream_with_retries(watch_type, what):
                    applied = False
                    self.__internal_lock.acquire()
                    locked = True
                    if not self.__process_event(event):
                        self.__internal_lock.release()
                        locked = False
                        continue
                    self._first_start = False

                    # Mark event received and update time
                    self.__pending_apply = True
                    self.__last_event_time = time()
                    self._logger.debug(f"Kubernetes event ({watch_type}) received, will batch if more arrive...")
                    self.__internal_lock.release()
                    locked = False

                    # Wait for debounce period
                    while (time() - self.__last_event_time) < self.__debounce_delay:
                        sleep(0.1)

                    # Debounce period passed, try to apply
                    self.__internal_lock.acquire()
                    locked = True

                    # Check if another event updated the time while we were waiting
                    if (time() - self.__last_event_time) < self.__debounce_delay:
                        self.__internal_lock.release()
                        locked = False
                        continue

                    if not self.__pending_apply:
                        self.__internal_lock.release()
                        locked = False
                        continue

                    self.__pending_apply = False

                    to_apply = False
                    while not applied:
                        waiting = self.have_to_wait()
                        self._update_settings()
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._extra_config, self._configs = self.get_configs()

                        if not to_apply and not self.update_needed(self._instances, self._services, self._configs, self._extra_config):
                            if locked:
                                self.__internal_lock.release()
                                locked = False
                            applied = True
                            continue

                        to_apply = True
                        if waiting:
                            self._logger.info("Scheduler is already applying a configuration, retrying in 1 second ...")
                            sleep(1)
                            continue

                        self._logger.info("Batched kubernetes event(s), deploying configuration...")
                        try:
                            ret = self.apply_config()
                            if not ret:
                                self._logger.error("Error while deploying new configuration ...")
                            else:
                                self._logger.info("Successfully deployed new configuration 🚀")

                                self._set_autoconf_load_db()
                        except BaseException as e:
                            self._logger.debug(format_exc())
                            self._logger.error(f"Exception while deploying new configuration :\n{e}")
                        applied = True

                    if locked:
                        self.__internal_lock.release()
                        locked = False
            except ApiException as e:
                if e.status != 410:
                    self._logger.debug(format_exc())
                    self._logger.error(f"API exception while reading k8s event (type = {watch_type}) :\n{e}")
                    error = True
            except BaseException as e:
                self._logger.debug(format_exc())
                self._logger.error(f"Unknown exception while reading k8s event (type = {watch_type}) :\n{e}")
                error = True
            finally:
                if locked:
                    with suppress(BaseException):
                        self.__internal_lock.release()
                    locked = False

                if error is True:
                    self._logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def __get_loadbalancer_ip(self, name: str, namespace: str) -> Optional[str]:
        try:
            if not name or not namespace:
                self._logger.warning("Service name or namespace is empty, cannot retrieve LoadBalancer IP")
                return None

            service = self.__corev1.read_namespaced_service(name=name, namespace=namespace)

            if not service.status:
                self._logger.warning(f"Service {name} in {namespace} has no status")
                return None

            if not service.status.load_balancer:
                self._logger.warning(f"Service {name} in {namespace} has no LoadBalancer status")
                return None

            ingress_list = service.status.load_balancer.ingress
            if not ingress_list:
                self._logger.warning(f"No ingress entries found in LoadBalancer status for service {name} in {namespace}")
                return None

            for ingress_entry in ingress_list:
                if ingress_entry.ip:
                    self._logger.debug(f"Found LoadBalancer IP {ingress_entry.ip} for service {name} in {namespace}")
                    return ingress_entry.ip
                elif ingress_entry.hostname:
                    self._logger.debug(f"Found LoadBalancer hostname {ingress_entry.hostname} for service {name} in {namespace}")
                    return ingress_entry.hostname

            self._logger.warning(f"No IP or hostname found in LoadBalancer ingress entries for service {name} in {namespace}")

        except ApiException as e:
            if e.status == 404:
                self._logger.warning(f"Service {name} not found in namespace {namespace}")
            else:
                self._logger.error(f"API error retrieving service {name} in {namespace}: {e.status} - {e.reason}")
                self._logger.debug(format_exc())
        except Exception as e:
            self._logger.error(f"Unexpected error retrieving LoadBalancer IP for service {name} in {namespace}: {e}")
            self._logger.debug(format_exc())

        return None

    def __patch_ingress_status(self, ingress, ip: str):
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

        # Determine if IP is an actual IP address or hostname
        patch_body = {"status": {"loadBalancer": {"ingress": []}}}
        ip_match = self.__ip_pattern.match(ip)

        if ip_match:
            patch_body["status"]["loadBalancer"]["ingress"].append({"ip": ip})
        else:
            patch_body["status"]["loadBalancer"]["ingress"].append({"hostname": ip})

        try:
            self.__networkingv1.patch_namespaced_ingress_status(name=ingress_name, namespace=ingress_namespace, body=patch_body)
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

    def apply_config(self) -> bool:
        result = self.apply(self._instances, self._services, configs=self._configs, first=not self._loaded, extra_config=self._extra_config)
        if result:
            ip = self.__get_loadbalancer_ip(self.__service_name, self.__namespace)
            for ingress in self._get_controller_services():
                self.__patch_ingress_status(ingress, ip)
        return result

    def process_events(self):
        self._set_autoconf_load_db()
        watch_types = ("pod", "ingress", "configmap", "service", "secret")
        threads = [Thread(target=self.__watch, args=(watch_type,)) for watch_type in watch_types]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
