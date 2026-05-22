#!/usr/bin/env python3

from contextlib import suppress
from logging import DEBUG
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
        self._event_loggable_kinds = {"Ingress", "Gateway", "HTTPRoute", "GRPCRoute", "TLSRoute", "TCPRoute", "UDPRoute", "ConfigMap", "Secret"}
        # Pending-backend retry: when _to_services can't find a referenced backend
        # Service (often because watch events race ahead of GET consistency on AKS),
        # the (namespace, service_name) is recorded here. A background worker polls
        # with exponential backoff and re-triggers an apply once the backend shows
        # up — otherwise update_needed would silently return False and the
        # controller would go quiet until an unrelated event happens to arrive.
        self._pending_backends_lock = Lock()
        self._pending_backends: Dict[Tuple[str, str], Dict[str, float]] = {}
        self._pending_backends_max_attempts = 5
        self._pending_backends_base_delay = 1.0  # seconds; doubles each attempt (1, 2, 4, 8, 16 → max ~31s)
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

    # ------------------------------------------------------------------
    # Multi-Ingress merge helpers
    # ------------------------------------------------------------------

    def _build_multiple_groups_lookup(self) -> Dict[str, str]:
        """Build {setting_name: group_id} from self._settings for settings
        that have a ``"multiple"`` field (e.g. REVERSE_PROXY_HOST -> "reverse-proxy")."""
        lookup: Dict[str, str] = {}
        for setting_name, meta in self._settings.items():
            group = meta.get("multiple")
            if group:
                lookup[setting_name] = group
        return lookup

    def _extract_slots(self, service: dict, multiple_lookup: Dict[str, str], server_name_prefix: str) -> Dict[str, Dict[int, Dict[str, tuple]]]:
        """Extract numbered slots from *service* dict.

        Returns ``{group_id: {slot_num: {base_setting: (original_key, value, was_prefixed)}}}``

        Matched keys are **removed** from *service* in-place so that only
        scalar settings remain.
        """
        slots: Dict[str, Dict[int, Dict[str, tuple]]] = {}
        keys_to_remove = []

        for key in list(service.keys()):
            raw_key = key
            was_prefixed = False
            setting_part = key

            # Strip server_name prefix if present
            if server_name_prefix and key.startswith(server_name_prefix):
                setting_part = key.removeprefix(server_name_prefix)
                was_prefixed = True

            # Check for exact match (slot 0 / unsuffixed)
            if setting_part in multiple_lookup:
                group_id = multiple_lookup[setting_part]
                base_setting = setting_part
                slot_num = 0
                slots.setdefault(group_id, {}).setdefault(slot_num, {})[base_setting] = (raw_key, service[key], was_prefixed)
                keys_to_remove.append(key)
                continue

            # Check for {BASE}_{N} pattern
            last_underscore = setting_part.rfind("_")
            if last_underscore > 0:
                base_candidate = setting_part[:last_underscore]
                candidate_suffix = setting_part[last_underscore + 1 :]  # noqa: E203
                if candidate_suffix.isdigit() and base_candidate in multiple_lookup:
                    suffix_num = int(candidate_suffix)
                    group_id = multiple_lookup[base_candidate]
                    slots.setdefault(group_id, {}).setdefault(suffix_num, {})[base_candidate] = (raw_key, service[key], was_prefixed)
                    keys_to_remove.append(key)
                    continue

        for key in keys_to_remove:
            del service[key]

        return slots

    def _write_slots(self, service: dict, all_slots: Dict[str, List[Dict[str, tuple]]], server_name_prefix: str) -> None:
        """Write renumbered slots back into *service*.

        *all_slots* is ``{group_id: [slot_dict, ...]}`` where each
        ``slot_dict`` is ``{base_setting: (original_key, value, was_prefixed)}``.

        Enumeration starts from ``self._reverse_proxy_suffix_start``.
        Index 0 means unsuffixed key; index > 0 means ``_{N}`` suffix.
        The server-name prefix is restored if the original key had it.
        """
        for slot_list in all_slots.values():
            for idx, slot_dict in enumerate(slot_list, start=self._reverse_proxy_suffix_start):
                for base_setting, (_orig_key, value, was_prefixed) in slot_dict.items():
                    if idx == 0:
                        new_setting = base_setting
                    else:
                        new_setting = f"{base_setting}_{idx}"
                    if was_prefixed:
                        new_key = f"{server_name_prefix}{new_setting}"
                    else:
                        new_key = new_setting
                    service[new_key] = value

    # OR-merge keys: if any service has "yes", the merged result is "yes"
    _OR_MERGE_KEYS = frozenset({"USE_REVERSE_PROXY", "USE_GRPC", "USE_CUSTOM_SSL"})

    # Keys that legitimately differ between Ingresses sharing a primary host
    # (e.g. alias lists in SERVER_NAME) — last-wins is still applied, but no
    # WARN log is emitted because the operator did not actually misconfigure
    # anything. NAMESPACE never reaches the conflict branch because the
    # cross-namespace check at the top of the merge loop short-circuits first.
    _CONFLICT_LOG_SKIP_KEYS = frozenset({"SERVER_NAME", "NAMESPACE"})

    # Substrings that mark an annotation value as sensitive. Conflict logs that
    # would otherwise echo the old/new value verbatim substitute "<redacted>"
    # for any key matching one of these substrings, so secrets do not leak into
    # scheduler logs that may be shipped to centralized log sinks. Operators
    # who need the raw values for debugging can drop the controller logger to
    # DEBUG (the most verbose level the project ships) — the redaction is
    # bypassed in that mode.
    _SENSITIVE_KEY_SUBSTRINGS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE_KEY", "AUTH_BASIC")

    def _format_conflict_value(self, key: str, value) -> str:
        """Return ``repr(value)`` unless ``key`` looks sensitive.

        When the controller logger is enabled for ``DEBUG`` the original value
        is always shown — operators on debug/trace verbosity have explicitly
        opted into verbose output, so silent redaction would defeat the purpose
        of turning the level up in the first place.
        """
        if self._logger.isEnabledFor(DEBUG):
            return repr(value)
        upper_key = key.upper()
        for marker in self._SENSITIVE_KEY_SUBSTRINGS:
            if marker in upper_key:
                return "'<redacted>'"
        return repr(value)

    def _merge_services_by_server_name(self, services: list) -> list:
        """Merge services that share the same primary SERVER_NAME.

        This combines numbered-suffix settings from multiple Ingresses/Routes
        into a single service with renumbered slots.
        """
        if not services:
            return []

        # Group by primary hostname (first token of SERVER_NAME)
        groups: Dict[str, List[dict]] = {}
        order: list = []  # preserve first-seen order
        for svc in services:
            primary = svc.get("SERVER_NAME", "").split(" ")[0]
            if primary not in groups:
                groups[primary] = []
                order.append(primary)
            groups[primary].append(svc)

        multiple_lookup = self._build_multiple_groups_lookup()
        result = []

        for primary in order:
            group = groups[primary]

            # No duplicates — passthrough
            if len(group) == 1:
                result.append(group[0])
                continue

            # Namespace ownership: first service establishes the owner namespace
            owner_namespace = group[0].get("NAMESPACE")

            # Merged service starts as a copy of the first service's scalar keys
            merged: dict = {}
            or_merge_accum: Dict[str, bool] = {k: False for k in self._OR_MERGE_KEYS}
            collected_slots: Dict[str, list] = {}  # group_id -> [slot_dict, ...]

            server_name_prefix = f"{primary}_"

            for svc in group:
                # Cross-namespace check (fail-closed: if either has a namespace, they must match)
                svc_ns = svc.get("NAMESPACE")
                if owner_namespace or svc_ns:
                    if svc_ns != owner_namespace:
                        self._logger.warning(f"Skipping service for {primary} from namespace {svc_ns}: already owned by namespace {owner_namespace}")
                        continue

                # Extract multiple-group slots (modifies svc in-place, leaving only scalars)
                svc_slots = self._extract_slots(svc, multiple_lookup, server_name_prefix)

                # Collect slots per group
                for group_id, numbered_slots in svc_slots.items():
                    collected_slots.setdefault(group_id, [])
                    for _slot_num, slot_dict in sorted(numbered_slots.items()):
                        collected_slots[group_id].append(slot_dict)

                # OR-merge accumulation
                for key in self._OR_MERGE_KEYS:
                    # Check both prefixed and unprefixed variants
                    if "yes" in (svc.get(key, "").lower(), svc.get(f"{server_name_prefix}{key}", "").lower()):
                        or_merge_accum[key] = True

                # Scalar settings: last-wins. When two Ingresses targeting the
                # same primary host disagree on the same scalar annotation, the
                # later one overwrites the earlier — log a WARN so operators can
                # see they have conflicting Ingress annotations rather than
                # silently shipping whichever one happened to be processed last.
                # SERVER_NAME / NAMESPACE are excluded because alias-list
                # differences are a legitimate merge case, not a misconfig.
                # Sensitive-looking keys have their values redacted so secrets
                # passed through Ingress annotations do not leak into logs.
                for key, value in svc.items():
                    if (key not in self._OR_MERGE_KEYS and not key.startswith(server_name_prefix)) or key in ("SERVER_NAME", "NAMESPACE"):
                        if key in merged and merged[key] != value and key not in self._CONFLICT_LOG_SKIP_KEYS:
                            old_repr = self._format_conflict_value(key, merged[key])
                            new_repr = self._format_conflict_value(key, value)
                            self._logger.warning(
                                f"Conflicting annotation for {primary}: {key}={old_repr} overwritten by {new_repr} from another Ingress/Route — last-wins"
                            )
                        merged[key] = value
                    elif key.startswith(server_name_prefix):
                        stripped = key.removeprefix(server_name_prefix)
                        if stripped not in self._OR_MERGE_KEYS:
                            if key in merged and merged[key] != value and stripped not in self._CONFLICT_LOG_SKIP_KEYS:
                                old_repr = self._format_conflict_value(stripped, merged[key])
                                new_repr = self._format_conflict_value(stripped, value)
                                self._logger.warning(
                                    f"Conflicting annotation for {primary}: {stripped}={old_repr} overwritten by {new_repr} from another Ingress/Route — last-wins"
                                )
                            merged[key] = value

            # Deterministic sort: for each group, sort slot lists by their content
            for group_id in collected_slots:
                collected_slots[group_id].sort(key=lambda slot: tuple(sorted((k, v[1]) for k, v in slot.items())))

            # Write renumbered slots into merged service
            self._write_slots(merged, collected_slots, server_name_prefix)

            # Apply OR-merge
            for key, any_yes in or_merge_accum.items():
                if any_yes:
                    merged[key] = "yes"

            result.append(merged)

        return result

    def get_services(self) -> list:
        services = super().get_services()
        return self._merge_services_by_server_name(services)

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

                    while not applied:
                        waiting = self.have_to_wait()
                        self._update_settings()
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._extra_config, self._configs = self.get_configs()

                        if not self.update_needed(self._instances, self._services, self._configs, self._extra_config):
                            if locked:
                                self._internal_lock.release()
                                locked = False
                            applied = True
                            continue

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
        watchers = self._get_watchers()
        threads = [Thread(target=self._watch, args=(watch_type, watcher)) for watch_type, watcher in watchers.items()]
        backend_retry_thread = Thread(target=self._pending_backends_worker, daemon=True)
        backend_retry_thread.start()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def note_missing_backend(self, namespace: str, service_name: str) -> None:
        """Record a referenced-but-not-yet-visible backend Service so the retry
        worker can poll for it and re-trigger an apply once it exists."""
        if not namespace or not service_name:
            return
        key = (namespace, service_name)
        with self._pending_backends_lock:
            entry = self._pending_backends.get(key)
            if entry is None:
                self._pending_backends[key] = {"attempts": 0.0, "next_retry_at": time() + self._pending_backends_base_delay}
                self._logger.debug(f"Queued missing backend {namespace}/{service_name} for retry")

    def _pending_backends_worker(self) -> None:
        """Background worker: retries backend Service lookups with exponential
        backoff and triggers a fresh apply cycle as soon as a queued backend
        becomes visible to a GET. Keeps running for the lifetime of the process."""
        while True:
            try:
                now = time()
                ready_keys: List[Tuple[str, str]] = []
                give_up_keys: List[Tuple[str, str]] = []
                with self._pending_backends_lock:
                    due = [(k, v) for k, v in self._pending_backends.items() if v["next_retry_at"] <= now]

                for key, entry in due:
                    namespace, service_name = key
                    try:
                        items = self._corev1.list_namespaced_service(
                            namespace,
                            watch=False,
                            field_selector=f"metadata.name={service_name}",
                        ).items
                    except BaseException as e:
                        self._logger.debug(f"Error polling for pending backend {namespace}/{service_name}: {e}")
                        items = []

                    if items:
                        ready_keys.append(key)
                        continue

                    with self._pending_backends_lock:
                        current = self._pending_backends.get(key)
                        if current is None:
                            continue
                        current["attempts"] += 1
                        if current["attempts"] >= self._pending_backends_max_attempts:
                            give_up_keys.append(key)
                            continue
                        current["next_retry_at"] = now + self._pending_backends_base_delay * (2 ** int(current["attempts"]))

                if ready_keys:
                    with self._pending_backends_lock:
                        for key in ready_keys:
                            self._pending_backends.pop(key, None)
                    for namespace, service_name in ready_keys:
                        self._logger.info(f"Pending backend {namespace}/{service_name} is now visible, triggering re-apply")
                    # Force the watch loop to run a fresh apply cycle.
                    with self._internal_lock:
                        self._pending_apply = True
                        # Put the event in the past so the debounce check already considers it elapsed.
                        self._last_event_time = time() - self._debounce_delay - 1
                    self._trigger_apply_if_idle()

                if give_up_keys:
                    with self._pending_backends_lock:
                        for key in give_up_keys:
                            self._pending_backends.pop(key, None)
                    for namespace, service_name in give_up_keys:
                        self._logger.warning(f"Giving up on pending backend {namespace}/{service_name} after {self._pending_backends_max_attempts} attempts")
            except BaseException as e:
                self._logger.debug(format_exc())
                self._logger.error(f"Error in pending backends worker: {e}")
            sleep(0.5)

    def _trigger_apply_if_idle(self) -> None:
        """Kick off an immediate apply cycle from outside the watch loop.

        The normal apply path lives inside `_watch` and only runs when a watch
        event wakes a thread. If the backend retry worker unblocks a previously
        dropped rule and no fresh watch event arrives, we would wait forever —
        so we run an apply directly here under the internal lock.
        """
        try:
            with self._internal_lock:
                if not self._pending_apply:
                    return
                self._pending_apply = False
                self._log_event_summary()
                self._update_settings()
                self._instances = self.get_instances()
                self._services = self.get_services()
                self._extra_config, self._configs = self.get_configs()
                if not self.update_needed(self._instances, self._services, self._configs, self._extra_config):
                    self._logger.debug("Backend retry worker: no config change detected, skipping apply")
                    return
                if self.have_to_wait():
                    # Let the normal watch loop retry — don't busy-wait here.
                    self._pending_apply = True
                    self._last_event_time = time()
                    return
                self._logger.info("Backend retry worker: deploying recovered configuration...")
                try:
                    ret = self.apply_config()
                    if not ret:
                        self._logger.error("Backend retry worker: error while deploying new configuration")
                    else:
                        self._logger.info("Backend retry worker: successfully deployed recovered configuration")
                        self._set_autoconf_load_db()
                except BaseException as e:
                    self._logger.debug(format_exc())
                    self._logger.error(f"Backend retry worker: exception while deploying new configuration: {e}")
        except BaseException as e:
            self._logger.debug(format_exc())
            self._logger.error(f"Backend retry worker: unexpected error: {e}")

    def _get_loadbalancer_ip(self, name: str, namespace: str) -> Optional[List[str]]:
        try:
            if not name or not namespace:
                self._logger.warning("Service name or namespace is empty, cannot retrieve LoadBalancer IP")
                return None

            service = self._corev1.read_namespaced_service(name=name, namespace=namespace)

            if not service.spec:
                self._logger.warning(f"Service {name} in {namespace} has no spec")
                return None

            service_type = service.spec.type

            # Handle NodePort services by returning node IPs
            if service_type == "NodePort":
                self._logger.debug(f"Service {name} in {namespace} is of type NodePort, retrieving node IPs")
                try:
                    nodes = self._corev1.list_node(watch=False).items
                    if not nodes:
                        self._logger.warning("No nodes found in the cluster")
                        return None

                    node_ips = []
                    for node in nodes:
                        if not node.status or not node.status.addresses:
                            continue

                        # Prefer ExternalIP, fall back to InternalIP
                        external_ip = None
                        internal_ip = None
                        for address in node.status.addresses:
                            if address.type == "ExternalIP":
                                external_ip = address.address
                            elif address.type == "InternalIP":
                                internal_ip = address.address

                        # Use ExternalIP if available, otherwise use InternalIP
                        node_ip = external_ip or internal_ip
                        if node_ip and node_ip not in node_ips:
                            node_ips.append(node_ip)

                    if node_ips:
                        self._logger.info(f"Found {len(node_ips)} node IP(s) for NodePort service {name} in {namespace}: {', '.join(node_ips)}")
                        return node_ips
                    else:
                        self._logger.warning(f"No node IPs found for NodePort service {name} in {namespace}")
                        return None

                except Exception as e:
                    self._logger.error(f"Error retrieving node IPs for NodePort service {name} in {namespace}: {e}")
                    self._logger.debug(format_exc())
                    return None

            # Handle LoadBalancer services with the existing logic
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

            ips = []
            for ingress_entry in ingress_list:
                if ingress_entry.ip:
                    self._logger.debug(f"Found LoadBalancer IP {ingress_entry.ip} for service {name} in {namespace}")
                    ips.append(ingress_entry.ip)
                elif ingress_entry.hostname:
                    self._logger.debug(f"Found LoadBalancer hostname {ingress_entry.hostname} for service {name} in {namespace}")
                    ips.append(ingress_entry.hostname)

            if ips:
                return ips

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

    def _patch_controller_status(self, ips: List[str]) -> None:
        raise NotImplementedError

    def _maybe_patch_status(self) -> None:
        if not self._status_patch_enabled():
            return

        ips = self._get_loadbalancer_ip(self._service_name, self._namespace)
        if not ips:
            return

        self._patch_controller_status(ips)

    def apply_config(self) -> bool:
        result = self.apply(self._instances, self._services, configs=self._configs, first=not self._loaded, extra_config=self._extra_config)
        if result:
            self._maybe_patch_status()
        return result
