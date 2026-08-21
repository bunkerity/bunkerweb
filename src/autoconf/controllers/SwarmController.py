#!/usr/bin/env python3

from os import getenv
from threading import Thread, Lock
from typing import Any, Dict, List
from docker import DockerClient
from re import compile as re_compile, split as re_split
from base64 import b64decode

from docker.models.services import Service
from docker.errors import DockerException
from controllers.Controller import Controller


class SwarmController(Controller):
    def __init__(self, docker_host, *, api_client):
        super().__init__("swarm", api_client=api_client)
        self.__client = DockerClient(base_url=docker_host)
        self.__internal_lock = Lock()
        # Protected alias so the base-class settings recheck worker shares the same lock object.
        self._internal_lock = self.__internal_lock
        self.__swarm_instances = []
        self.__swarm_services = []
        self.__swarm_configs = []
        self.__warned_custom_conf_services = set()
        self.__warned_non_global_instances = set()
        self.__ignored_labels_exact = set()
        self.__ignored_label_suffixes = set()
        ignore_labels = getenv("SWARM_IGNORE_LABELS", "")
        if ignore_labels:
            tokens = [token.strip() for token in re_split(r"[,\s]+", ignore_labels) if token.strip()]
            for token in tokens:
                if "." in token:
                    self.__ignored_labels_exact.add(token)
                    if token.startswith("bunkerweb."):
                        suffix = token.split(".", 1)[1]
                        if suffix:
                            self.__ignored_label_suffixes.add(suffix)
                else:
                    self.__ignored_label_suffixes.add(token)
                    self.__ignored_labels_exact.add(f"bunkerweb.{token}")

            self._logger.info("Ignoring Swarm labels while collecting instances: " + ", ".join(sorted(self.__ignored_labels_exact)))

    def __should_ignore_label(self, label: str) -> bool:
        if label in self.__ignored_labels_exact:
            return True
        if label.removeprefix("bunkerweb.") in self.__ignored_label_suffixes:
            return True
        return False

    def _get_controller_swarm_services(self, label_key: str) -> List[Service]:
        """
        Fetch Swarm services based on a specific label and filter them by namespace.

        Args:
            label_key (str): The key of the label to filter services by (e.g., "bunkerweb.INSTANCE").

        Returns:
            List[Service]: A list of services matching the label and namespace criteria.
        """
        try:
            # Retrieve services with the specific label
            services: List[Service] = self.__client.services.list(filters={"label": label_key})
        except DockerException as e:
            self._logger.error(f"Failed to retrieve services with label '{label_key}': {e}")
            raise

        namespace_set = set(self._namespaces or [])
        valid_services = []

        for service in services:
            try:
                # Safely retrieve and validate labels
                labels = service.attrs.get("Spec", {}).get("Labels", {})
                if not isinstance(labels, dict):
                    self._logger.warning(f"Unexpected label format for service {service.id}: {labels}")
                    continue

                if namespace_set:
                    namespace = labels.get("bunkerweb.NAMESPACE", "")
                    if namespace not in namespace_set:
                        self._logger.debug(f"Service {service.id} does not match any namespace.")
                        continue

                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping service {getattr(service, 'name', service.id)} because of ignored labels")
                    continue

                valid_services.append(service)

            except AttributeError as e:
                self._logger.warning(f"Service {service.id} missing expected attributes: {e}")
            except Exception as e:
                self._logger.error(f"Unexpected error while processing service {service.id}: {e}")

        return valid_services

    # Image-level metadata labels that are not BunkerWeb settings. The BunkerWeb image bakes
    # `bunkerweb.INSTANCE` (src/bw/Dockerfile), so a service carrying both SERVER_NAME and
    # INSTANCE emitted `INSTANCE=yes` as a setting -- one validation warning per cycle, forever.
    __METADATA_LABELS = frozenset(("bunkerweb.type", "bunkerweb.INSTANCE"))

    # `bunkerweb.CUSTOM_CONF_*` labels are a Docker-autoconf feature: `Config.py` ignores the
    # prefix for every controller and only DockerController reads them back off the container.
    # Under Swarm they are inert, and were inert *silently* -- every Docker-autoconf doc snippet
    # using them did nothing here with no diagnostic at all. Swarm's route is `docker config create`.
    __custom_conf_rx = re_compile(r"^bunkerweb\.CUSTOM_CONF_")

    def _get_controller_instances(self) -> List[Service]:
        """
        Fetch Swarm services labeled as 'bunkerweb.INSTANCE'.
        """
        # Reset before the pass, not after: `_to_instances` appends one id per service and the
        # base class calls it once per service per pass. Without this the list grew without bound
        # for the lifetime of the process, and a *deleted* service kept satisfying the event
        # filter in `__process_event` because its id was still in there.
        self.__swarm_instances = []
        return self._get_controller_swarm_services(label_key="bunkerweb.INSTANCE")

    def _get_controller_services(self) -> List[Service]:
        """
        Fetch Swarm services labeled as 'bunkerweb.SERVER_NAME'.
        """
        self.__swarm_services = []
        return self._get_controller_swarm_services(label_key="bunkerweb.SERVER_NAME")

    def _to_instances(self, controller_instance) -> List[dict]:
        # R6 -- a BunkerWeb instance service MUST be `mode: global`. The hostname registered for
        # an instance is `<service>.<NodeID>.<TaskID>` (below), which is only the task's real DNS
        # name under a global service; a replicated service resolves as `<service>.<slot>.<TaskID>`
        # instead. Accepting one would register instances the control plane can never reach, and
        # the operator would see a stack that boots and never converges, with no error anywhere.
        # The documentation prescribed `mode: global` in prose and nothing enforced it.
        mode = controller_instance.attrs.get("Spec", {}).get("Mode", {}) or {}
        if "Global" not in mode:
            # Log once per service, not once per reconcile pass: this runs on every event burst and
            # the operator cannot fix it from the log anyway -- they have to redeploy the service.
            # Repeating it every few seconds only buries the rest of the diagnostics.
            if controller_instance.id not in self.__warned_non_global_instances:
                self._logger.error(
                    f"Ignoring service {controller_instance.name!r} labelled bunkerweb.INSTANCE: it is not a global service "
                    f"(mode: {', '.join(mode) or 'unknown'}). A BunkerWeb instance service must be deployed with `mode: global`, "
                    "otherwise its tasks are unreachable from the control plane."
                )
                self.__warned_non_global_instances.add(controller_instance.id)
            return []

        self.__swarm_instances.append(controller_instance.id)
        instances = []
        instance_env = {}
        container_spec = controller_instance.attrs.get("Spec", {}).get("TaskTemplate", {}).get("ContainerSpec", {}) or {}
        for env in container_spec.get("Env") or []:
            if "=" not in env:
                continue
            variable, value = env.split("=", 1)
            instance_env[variable] = value

        for task in controller_instance.tasks():
            if task["DesiredState"] != "running":
                continue
            instances.append(
                {
                    "name": task["ID"],
                    "hostname": f"{controller_instance.name}.{task['NodeID']}.{task['ID']}",
                    "type": "container",
                    "health": task["Status"]["State"] == "running",
                    "env": instance_env,
                }
            )
        return instances

    def _to_services(self, controller_service) -> List[dict]:
        self.__swarm_services.append(controller_service.id)
        service = {}
        custom_conf_labels = []
        for variable, value in (controller_service.attrs.get("Spec", {}).get("Labels", {}) or {}).items():
            if self.__should_ignore_label(variable):
                continue
            if not variable.startswith("bunkerweb."):
                continue
            if self.__custom_conf_rx.match(variable):
                custom_conf_labels.append(variable)
                continue
            if variable in self.__METADATA_LABELS:
                continue
            service[variable.replace("bunkerweb.", "", 1)] = value

        if custom_conf_labels and controller_service.id not in self.__warned_custom_conf_services:
            # Warn once per service rather than once per reconcile: the reconcile runs on every
            # event, and a per-pass warning would bury every other line in the controller log.
            self.__warned_custom_conf_services.add(controller_service.id)
            self._logger.warning(
                f"Service {controller_service.name!r} carries {len(custom_conf_labels)} bunkerweb.CUSTOM_CONF_* "
                f"label(s) ({', '.join(sorted(custom_conf_labels))}) which the Swarm controller CANNOT apply -- they "
                "are a Docker-autoconf feature and are being ignored. Ship the configuration as a Swarm config object "
                "labelled bunkerweb.CONFIG_TYPE instead (`docker config create`)."
            )

        return [service]

    def get_configs(self) -> Dict[str, Dict[str, Any]]:
        self.__swarm_configs = []
        configs = {}
        for config_type in self._supported_config_types:
            configs[config_type] = {}
        for config in self.__client.configs.list(filters={"label": "bunkerweb.CONFIG_TYPE"}):
            if not config.name or not config.attrs or not config.attrs.get("Spec", {}).get("Labels", {}) or not config.attrs.get("Spec", {}).get("Data", {}):
                continue

            labels = config.attrs["Spec"].get("Labels", {}) or {}
            if any(self.__should_ignore_label(label) for label in labels):
                self._logger.info(f"Skipping Swarm config {getattr(config, 'name', config.id)} because of ignored labels")
                continue

            # NAMESPACES filtered the *event* path of this same file (__process_event) and the
            # service-discovery path, but not this one -- so a GLOBAL custom config labelled for
            # another namespace was picked up by every partition on the daemon. A config carrying
            # CONFIG_SITE was filtered only incidentally, by the _is_service_present check below.
            # DockerController filters both paths; this brings Swarm to parity.
            if self._namespaces and not any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces):
                self._logger.debug(f"Skipping Swarm config {getattr(config, 'name', config.id)}: namespace not in the allowed namespaces")
                continue

            config_type = labels["bunkerweb.CONFIG_TYPE"]
            config_name = config.name
            if config_type not in self._supported_config_types:
                self._logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for Config {config_name}",
                )
                continue
            config_site = ""
            if "bunkerweb.CONFIG_SITE" in labels:
                if not self._is_service_present(labels["bunkerweb.CONFIG_SITE"]):
                    self._logger.warning(
                        f"Ignoring config {config_name} because {labels['bunkerweb.CONFIG_SITE']} doesn't exist",
                    )
                    continue
                config_site = f"{labels['bunkerweb.CONFIG_SITE']}/"
            configs[config_type][f"{config_site}{config_name}"] = b64decode(config.attrs["Spec"]["Data"])
            self.__swarm_configs.append(config.id)
        return configs

    def apply_config(self, force: bool = False) -> bool:
        return self.apply(
            self._instances,
            self._services,
            configs=self._configs,
            first=not self._loaded,
            force=force,
        )

    def __process_event(self, event):
        if self._first_start:
            return True

        if "Actor" not in event or "ID" not in event["Actor"] or "Type" not in event:
            return False
        if event["Type"] not in ("service", "config"):
            return False
        if event["Type"] == "service":
            if event["Actor"]["ID"] in self.__swarm_instances or event["Actor"]["ID"] in self.__swarm_services:
                return True
            try:
                labels = self.__client.services.get(event["Actor"]["ID"]).attrs["Spec"].get("Labels", {}) or {}
                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping Swarm service {event['Actor']['ID']} because of ignored labels")
                    return False
                return ("bunkerweb.INSTANCE" in labels or "bunkerweb.SERVER_NAME" in labels) and (
                    not self._namespaces or any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces)
                )
            # Typed: the bare `except:` this replaces also swallowed KeyboardInterrupt and
            # SystemExit. A service that vanished between the event and this lookup raises
            # NotFound, which is the case actually worth ignoring.
            except Exception:
                return False
        if event["Type"] == "config":
            if event["Actor"]["ID"] in self.__swarm_configs:
                return True
            try:
                labels = self.__client.configs.get(event["Actor"]["ID"]).attrs["Spec"].get("Labels", {}) or {}
                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping Swarm config {event['Actor']['ID']} because of ignored labels")
                    return False
                return "bunkerweb.CONFIG_TYPE" in labels and (
                    not self._namespaces or any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces)
                )
            except Exception:
                return False
        return False

    def __event(self, event_type):
        # The debounce/batch/apply loop lives in Controller._run_event_loop: this used to be a
        # near-byte-identical copy of DockerController's, so any fix to one bypassed the other.
        self._run_event_loop(
            events=lambda: self.__client.events(decode=True, filters={"type": event_type}),
            process_event=self.__process_event,
            label="Swarm",
            lock=self.__internal_lock,
            error_suffix=f" ({event_type})",
        )

    def process_events(self):
        self._set_autoconf_loaded()
        self._start_settings_recheck_worker()
        self._logger.info("Listening for Swarm events ...")
        event_types = ("service", "config")
        threads = [Thread(target=self.__event, args=(event_type,)) for event_type in event_types]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
