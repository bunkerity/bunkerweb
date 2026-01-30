#!/usr/bin/env python3

from contextlib import suppress
from os import getenv
from re import compile as re_compile, split as re_split
from threading import Lock, Thread
from time import sleep, time
from traceback import format_exc
from typing import Any, Dict, List, Optional, Tuple

from kubernetes import client, config, watch
from kubernetes.client import Configuration
from kubernetes.client.exceptions import ApiException

from controllers.Controller import Controller


class KubernetesController(Controller):
    def __init__(self):
        self._internal_lock = Lock()
        self._pending_apply = False
        self._last_event_time = 0.0
        self._debounce_delay = 2  # seconds
        self._event_summary = {}
        self._event_summary_max = 8
        self._event_loggable_kinds = {"Ingress", "Gateway", "HTTPRoute", "TLSRoute", "TCPRoute", "UDPRoute", "ConfigMap", "Secret"}
        super().__init__("kubernetes")
        config.load_incluster_config()
        self._managed_configmaps = set()

        Configuration._default.verify_ssl = getenv("KUBERNETES_VERIFY_SSL", "yes").lower().strip() == "yes"
        self._logger.info(f"SSL verification is {'enabled' if Configuration._default.verify_ssl else 'disabled'}")

        ssl_ca_cert = getenv("KUBERNETES_SSL_CA_CERT", "")
        if ssl_ca_cert:
            Configuration._default.ssl_ca_cert = ssl_ca_cert
            self._logger.info("Using custom SSL CA certificate")

        self._corev1 = client.CoreV1Api()
        self._ip_pattern = re_compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")

        self._use_fqdn = getenv("USE_KUBERNETES_FQDN", "yes").lower().strip() == "yes"
        self._logger.info(f"Using Pod {'FQDN' if self._use_fqdn else 'IP'} as hostname")

        self._domain_name = getenv("KUBERNETES_DOMAIN_NAME", "cluster.local")
        self._logger.info(f"Using domain name: {self._domain_name}")

        self._service_protocol = getenv("KUBERNETES_SERVICE_PROTOCOL", "http").lower().strip()
        if self._service_protocol not in ("http", "https"):
            self._logger.warning(f"Unsupported service protocol {self._service_protocol}")
            self._service_protocol = "http"
        self._logger.info(f"Using service protocol: {self._service_protocol}")

        self._service_name = getenv("BUNKERWEB_SERVICE_NAME", "bunkerweb")
        self._namespace = getenv("BUNKERWEB_NAMESPACE", "bunkerweb")

        self._ignored_annotations_exact = set()
        self._ignored_annotation_suffixes = set()
        ignore_annotations = getenv("KUBERNETES_IGNORE_ANNOTATIONS", "")
        if ignore_annotations:
            tokens = [token.strip() for token in re_split(r"[,\s]+", ignore_annotations) if token.strip()]
            for token in tokens:
                if "/" in token:
                    self._ignored_annotations_exact.add(token)
                    if token.startswith("bunkerweb.io/"):
                        suffix = token.split("/", 1)[1]
                        if suffix:
                            self._ignored_annotation_suffixes.add(suffix)
                else:
                    self._ignored_annotation_suffixes.add(token)
                    self._ignored_annotations_exact.add(f"bunkerweb.io/{token}")

            self._logger.info("Ignoring annotations while collecting instances: " + ", ".join(sorted(self._ignored_annotations_exact)))

        self._reverse_proxy_suffix_start = getenv("KUBERNETES_REVERSE_PROXY_SUFFIX_START", "1").strip()
        if not self._reverse_proxy_suffix_start.isdigit() or int(self._reverse_proxy_suffix_start) < 0:
            self._logger.warning(f"Invalid KUBERNETES_REVERSE_PROXY_SUFFIX_START value {self._reverse_proxy_suffix_start}, defaulting to 1")
            self._reverse_proxy_suffix_start = "1"
        self._reverse_proxy_suffix_start = int(self._reverse_proxy_suffix_start)

    def _should_ignore_annotation(self, annotation: str) -> bool:
        if annotation in self._ignored_annotations_exact:
            return True
        if annotation.removeprefix("bunkerweb.io/") in self._ignored_annotation_suffixes:
            return True
        return False

    def _get_controller_instances(self) -> list:
        instances = []
        pods = self._corev1.list_pod_for_all_namespaces(watch=False).items
        for pod in pods:
            metadata = pod.metadata
            if not metadata:
                continue

            annotations = metadata.annotations or {}
            if "bunkerweb.io/INSTANCE" not in annotations:
                continue

            if self._namespaces and metadata.namespace not in self._namespaces:
                self._logger.debug(f"Skipping pod {metadata.namespace}/{metadata.name} because its namespace is not in the allowed namespaces")
                continue

            if any(self._should_ignore_annotation(annotation) for annotation in annotations):
                self._logger.debug(f"Skipping pod {metadata.namespace}/{metadata.name} because of ignored annotations")
                continue

            instances.append(pod)
        return instances

    def _get_service_annotations(self, controller_service) -> Dict[str, str]:
        metadata = getattr(controller_service, "metadata", None)
        return metadata.annotations or {} if metadata else {}

    def _to_instances(self, controller_instance) -> List[dict]:
        pod_ip = controller_instance.status.pod_ip
        pod_name = controller_instance.metadata.name
        namespace = controller_instance.metadata.namespace
        instance = {
            "name": pod_name,
            "hostname": (
                f"{(pod_ip.replace('.', '-') if pod_ip else pod_name)}.{namespace}.pod.{self._domain_name}" if self._use_fqdn else (pod_ip or pod_name)
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
            annotations = self._get_service_annotations(controller_service)
            for annotation, value in annotations.items():
                if not annotation.startswith("bunkerweb.io/"):
                    continue
                instance["env"][annotation.replace("bunkerweb.io/", "", 1)] = value

        return [instance]

    def get_configs(self) -> Tuple[dict, dict]:
        configs = {config_type: {} for config_type in self._supported_config_types}
        config = {}
        managed_configmaps = set()
        for configmap in self._corev1.list_config_map_for_all_namespaces(watch=False).items:
            if not configmap.metadata.annotations or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations:
                continue

            if self._namespaces and configmap.metadata.namespace not in self._namespaces:
                self._logger.debug(
                    f"Skipping ConfigMap {configmap.metadata.namespace}/{configmap.metadata.name} because its namespace is not in the allowed namespaces"
                )
                continue

            if any(self._should_ignore_annotation(annotation) for annotation in configmap.metadata.annotations):
                self._logger.debug(f"Skipping ConfigMap {configmap.metadata.namespace}/{configmap.metadata.name} because of ignored annotations")
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

        self._managed_configmaps = managed_configmaps
        return config, configs

    def _get_event_fields(self, obj):
        if isinstance(obj, dict):
            metadata = obj.get("metadata") or {}
            annotations = metadata.get("annotations") or {}
            namespace = metadata.get("namespace")
            name = metadata.get("name")
            kind = obj.get("kind")
            data = obj.get("data")
        else:
            metadata = obj.metadata
            annotations = metadata.annotations if metadata else None
            namespace = metadata.namespace if metadata else None
            name = metadata.name if metadata else None
            kind = obj.kind
            data = getattr(obj, "data", None)

        return kind, annotations, namespace, name, data

    def _is_custom_event(self, kind, obj, annotations, namespace, name) -> bool:
        return False

    def _process_event(self, event):
        if self._first_start:
            return True

        obj = event.get("object")
        if not obj:
            return False

        kind, annotations, namespace, name, data = self._get_event_fields(obj)

        if namespace and self._namespaces and namespace not in self._namespaces:
            self._logger.debug(f"Skipping {kind} {namespace}/{name} because its namespace is not in the allowed namespaces")
            return False

        if annotations and any(self._should_ignore_annotation(annotation) for annotation in annotations):
            self._logger.debug(f"Skipping {kind} {namespace}/{name} because of ignored annotations")
            return False

        ret = False
        if kind == "Pod":
            ret = annotations and "bunkerweb.io/INSTANCE" in annotations
        elif kind == "ConfigMap":
            cfg_name = f"{namespace}/{name}" if namespace and name else ""
            event_type = event.get("type")
            is_managed = bool(cfg_name and cfg_name in self._managed_configmaps)
            if event_type == "DELETED":
                ret = is_managed
            else:
                ret = bool((annotations and "bunkerweb.io/CONFIG_TYPE" in annotations) or is_managed)
        elif kind == "Service":
            ret = True
        elif kind == "Secret":
            ret = data and "tls.crt" in data and "tls.key" in data
        else:
            ret = self._is_custom_event(kind, obj, annotations, namespace, name)

        if ret:
            event_type = event.get("type")
            self._record_event(kind, namespace, name, event_type)
            self._logger.debug(f"Processing event {event_type} for {kind} {name or 'unknown'}")

        return ret

    def _record_event(self, kind: Optional[str], namespace: Optional[str], name: Optional[str], event_type: Optional[str]) -> None:
        if not kind or kind not in self._event_loggable_kinds:
            return

        key = (kind, namespace or "", name or "unknown")
        if key not in self._event_summary or event_type == "DELETED":
            self._event_summary[key] = event_type or "UPDATED"

    def _format_event_summary(self) -> str:
        if not self._event_summary:
            return ""

        entries = []
        for (kind, namespace, name), event_type in self._event_summary.items():
            ns_part = f"{namespace}/" if namespace else ""
            entry = f"{kind} {ns_part}{name}"
            if event_type:
                entry += f" ({event_type})"
            entries.append(entry)

        shown = entries[: self._event_summary_max]
        remaining = len(entries) - len(shown)
        summary = ", ".join(shown)
        if remaining > 0:
            summary += f", and {remaining} more"
        return summary

    def _log_event_summary(self) -> None:
        summary = self._format_event_summary()
        if summary:
            self._logger.info(f"Detected Kubernetes changes: {summary}")
        self._event_summary.clear()

    def _get_stream_with_retries(self, watch_type, what, retries=5):
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

    def _get_watchers(self) -> Dict[str, Any]:
        raise NotImplementedError

    def _watch(self, watch_type, what):
        while True:
            locked = False
            error = False
            applied = False
            try:
                for event in self._get_stream_with_retries(watch_type, what):
                    applied = False
                    self._internal_lock.acquire()
                    locked = True
                    if not self._process_event(event):
                        self._internal_lock.release()
                        locked = False
                        continue
                    self._first_start = False

                    self._pending_apply = True
                    self._last_event_time = time()
                    self._logger.debug(f"Kubernetes event ({watch_type}) received, will batch if more arrive...")
                    self._internal_lock.release()
                    locked = False

                    while (time() - self._last_event_time) < self._debounce_delay:
                        sleep(0.1)

                    self._internal_lock.acquire()
                    locked = True

                    if (time() - self._last_event_time) < self._debounce_delay:
                        self._internal_lock.release()
                        locked = False
                        continue

                    if not self._pending_apply:
                        self._internal_lock.release()
                        locked = False
                        continue

                    self._pending_apply = False
                    self._log_event_summary()

                    to_apply = False
                    while not applied:
                        waiting = self.have_to_wait()
                        self._update_settings()
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._extra_config, self._configs = self.get_configs()

                        if not to_apply and not self.update_needed(self._instances, self._services, self._configs, self._extra_config):
                            if locked:
                                self._internal_lock.release()
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
                                self._logger.info("Successfully deployed new configuration")

                                self._set_autoconf_load_db()
                        except BaseException as e:
                            self._logger.debug(format_exc())
                            self._logger.error(f"Exception while deploying new configuration :\n{e}")
                        applied = True

                    if locked:
                        self._internal_lock.release()
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
                        self._internal_lock.release()
                    locked = False

                if error is True:
                    self._logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def process_events(self):
        self._set_autoconf_load_db()
        watchers = self._get_watchers()
        threads = [Thread(target=self._watch, args=(watch_type, watcher)) for watch_type, watcher in watchers.items()]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _get_loadbalancer_ip(self, name: str, namespace: str) -> Optional[str]:
        try:
            if not name or not namespace:
                self._logger.warning("Service name or namespace is empty, cannot retrieve LoadBalancer IP")
                return None

            service = self._corev1.read_namespaced_service(name=name, namespace=namespace)

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

    def _status_patch_enabled(self) -> bool:
        return True

    def _patch_controller_status(self, ip: str) -> None:
        raise NotImplementedError

    def _maybe_patch_status(self) -> None:
        if not self._status_patch_enabled():
            return

        ip = self._get_loadbalancer_ip(self._service_name, self._namespace)
        if not ip:
            return

        self._patch_controller_status(ip)

    def apply_config(self) -> bool:
        result = self.apply(self._instances, self._services, configs=self._configs, first=not self._loaded, extra_config=self._extra_config)
        if result:
            self._maybe_patch_status()
        return result
