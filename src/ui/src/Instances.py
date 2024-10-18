#!/usr/bin/env python3
from operator import itemgetter
from os import sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, STDOUT, run
from typing import Any, List, Optional, Tuple, Union

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from dotenv import dotenv_values  # type: ignore


class Instance:
    _id: str
    name: str
    hostname: str
    _type: str
    health: bool
    env: Any
    apiCaller: ApiCaller

    def __init__(
        self,
        _id: str,
        name: str,
        hostname: str,
        _type: str,
        status: str,
        data: Any = None,
        apiCaller: Optional[ApiCaller] = None,
    ) -> None:
        self._id = _id
        self.name = name
        self.hostname = hostname
        self._type = _type
        self.health = status == "up" and (
            (data.attrs["State"]["Health"]["Status"] == "healthy" if "Health" in data.attrs["State"] else False) if _type == "container" and data else True
        )
        self.env = data
        self.apiCaller = apiCaller or ApiCaller()

    @property
    def id(self) -> str:
        return self._id

    def reload(self) -> bool:
        if self._type == "local":
            return (
                run(
                    [join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                ).returncode
                == 0
            )

        return self.apiCaller.send_to_apis("POST", "/reload")

    def start(self) -> bool:
        if self._type == "local":
            return (
                run(
                    [join(sep, "usr", "sbin", "nginx"), "-e", "/var/log/bunkerweb/error.log"],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                ).returncode
                == 0
            )

        return self.apiCaller.send_to_apis("POST", "/start")

    def stop(self) -> bool:
        if self._type == "local":
            return (
                run(
                    [join(sep, "usr", "sbin", "nginx"), "-s", "stop"],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                ).returncode
                == 0
            )

        return self.apiCaller.send_to_apis("POST", "/stop")

    def restart(self) -> bool:
        if self._type == "local":
            proc = run(
                [join(sep, "usr", "sbin", "nginx"), "-s", "stop"],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                return False
            return (
                run(
                    [join(sep, "usr", "sbin", "nginx"), "-e", "/var/log/bunkerweb/error.log"],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                ).returncode
                == 0
            )

        return self.apiCaller.send_to_apis("POST", "/restart")

    def bans(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/bans", response=True)

    def ban(self, ip: str, exp: float, reason: str) -> bool:
        return self.apiCaller.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason})

    def unban(self, ip: str) -> bool:
        return self.apiCaller.send_to_apis("POST", "/unban", data={"ip": ip})

    def reports(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)

    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)

    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)

    def ping(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("POST", f"/{plugin_id}/ping", response=True)

    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)


class Instances:
    def __init__(self, docker_client, kubernetes_client, integration: str, db):
        self.__docker_client = docker_client
        self.__kubernetes_client = kubernetes_client
        self.__integration = integration
        self.__db = db

    def __instance_from_id(self, _id) -> Instance:
        instances: list[Instance] = self.get_instances()
        for instance in instances:
            if instance.id == _id:
                return instance

        raise ValueError(f"Can't find instance with _id {_id}")

    def get_instances(self, override_instances=None) -> list[Instance]:
        instances = []
        # Override case : only return instances from DB
        if override_instances is None:
            config = self.__db.get_non_default_settings(global_only=True, filtered_settings=("OVERRIDE_INSTANCES",))
            override_instances = config.get("OVERRIDE_INSTANCES", "") != ""
        if override_instances:
            for instance in self.__db.get_instances():
                instances.append(
                    Instance(
                        instance["hostname"],
                        instance["hostname"],
                        instance["hostname"],
                        "override",
                        "up",
                        None,
                        ApiCaller(
                            [
                                API(
                                    f"http://{instance['hostname']}:{instance['port']}",
                                    instance["server_name"],
                                )
                            ]
                        ),
                    )
                )
            return instances
        # Docker instances (containers or services)
        if self.__docker_client is not None:
            for instance in self.__docker_client.containers.list(all=True, filters={"label": "bunkerweb.INSTANCE"}):
                env_variables = {x[0]: (x[1] if len(x) > 1 else "") for x in [env.split("=") for env in instance.attrs["Config"]["Env"]]}

                instances.append(
                    Instance(
                        instance.id,
                        instance.name,
                        instance.name,
                        "container",
                        "up" if instance.status == "running" else "down",
                        instance,
                        ApiCaller(
                            [
                                API(
                                    f"http://{instance.name}:{env_variables.get('API_HTTP_PORT', '5000')}",
                                    env_variables.get("API_SERVER_NAME", "bwapi"),
                                )
                            ]
                        ),
                    )
                )
        elif self.__integration == "Swarm":
            for instance in self.__docker_client.services.list(filters={"label": "bunkerweb.INSTANCE"}):
                status = "down"
                desired_tasks = instance.attrs["ServiceStatus"]["DesiredTasks"]
                running_tasks = instance.attrs["ServiceStatus"]["RunningTasks"]
                if desired_tasks > 0 and (desired_tasks == running_tasks):
                    status = "up"

                apiCaller = ApiCaller()
                api_http_port = None
                api_server_name = None

                for var in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
                    if var.startswith("API_HTTP_PORT="):
                        api_http_port = var.replace("API_HTTP_PORT=", "", 1)
                    elif var.startswith("API_SERVER_NAME="):
                        api_server_name = var.replace("API_SERVER_NAME=", "", 1)

                for task in instance.tasks():
                    apiCaller.append(
                        API(
                            f"http://{instance.name}.{task['NodeID']}.{task['ID']}:{api_http_port or '5000'}",
                            host=api_server_name or "bwapi",
                        )
                    )

                instances.append(
                    Instance(
                        instance.id,
                        instance.name,
                        instance.name,
                        "service",
                        status,
                        instance,
                        apiCaller,
                    )
                )
        elif self.__integration == "Kubernetes":
            for pod in self.__kubernetes_client.list_pod_for_all_namespaces(watch=False).items:
                if pod.metadata.annotations is not None and "bunkerweb.io/INSTANCE" in pod.metadata.annotations:
                    env_variables = {env.name: env.value or "" for env in pod.spec.containers[0].env}

                    status = "up"
                    if pod.status.phase != "Running":
                        status = "down"
                        break

                    instances.append(
                        Instance(
                            pod.metadata.uid,
                            pod.metadata.name,
                            pod.status.pod_ip,
                            "pod",
                            status,
                            pod,
                            ApiCaller(
                                [
                                    API(
                                        f"http://{pod.status.pod_ip}:{env_variables.get('API_HTTP_PORT', '5000')}",
                                        host=env_variables.get("API_SERVER_NAME", "bwapi"),
                                    )
                                ]
                            ),
                        )
                    )

        instances.sort(key=lambda x: x.name)

        # Local instance
        if Path(sep, "usr", "sbin", "nginx").exists():
            env_variables = dotenv_values(join(sep, "etc", "bunkerweb", "variables.env"))

            instances.insert(
                0,
                Instance(
                    "local",
                    "local",
                    "127.0.0.1",
                    "local",
                    "up" if Path(sep, "var", "run", "bunkerweb", "nginx.pid").exists() else "down",
                    None,
                    ApiCaller(
                        [
                            API(
                                f"http://127.0.0.1:{env_variables.get('API_HTTP_PORT', '5000')}",
                                env_variables.get("API_SERVER_NAME", "bwapi"),
                            )
                        ]
                    ),
                ),
            )

        return instances

    def reload_instances(self) -> Union[list[str], str]:
        not_reloaded: list[str] = []
        for instance in self.get_instances():
            if not instance.health:
                not_reloaded.append(instance.name)
                continue

            if self.reload_instance(instance=instance).startswith("Can't reload"):
                not_reloaded.append(instance.name)

        return not_reloaded or "Successfully reloaded instances"

    def reload_instance(self, _id: Optional[int] = None, instance: Optional[Instance] = None) -> str:
        if not instance:
            instance = self.__instance_from_id(_id)

        try:
            result = instance.reload()
        except BaseException as e:
            return f"Can't reload {instance.name}: {e}"

        if result:
            return f"Instance {instance.name} has been reloaded."

        return f"Can't reload {instance.name}"

    def start_instance(self, _id) -> str:
        instance = self.__instance_from_id(_id)

        try:
            result = instance.start()
        except BaseException as e:
            return f"Can't start {instance.name}: {e}"

        if result:
            return f"Instance {instance.name} has been started."

        return f"Can't start {instance.name}"

    def stop_instance(self, _id) -> str:
        instance = self.__instance_from_id(_id)

        try:
            result = instance.stop()
        except BaseException as e:
            return f"Can't stop {instance.name}: {e}"

        if result:
            return f"Instance {instance.name} has been stopped."

        return f"Can't stop {instance.name}"

    def restart_instance(self, _id) -> str:
        instance = self.__instance_from_id(_id)

        try:
            result = instance.restart()
        except BaseException as e:
            return f"Can't restart {instance.name}: {e}"

        if result:
            return f"Instance {instance.name} has been restarted."

        return f"Can't restart {instance.name}"

    def get_bans(self, _id: Optional[int] = None) -> List[dict[str, Any]]:
        if _id:
            instance = self.__instance_from_id(_id)
            try:
                resp, instance_bans = instance.bans()
            except:
                return []
            if not resp:
                return []
            return instance_bans[instance.name if instance.name != "local" else "127.0.0.1"].get("data", [])

        bans: List[dict[str, Any]] = []
        for instance in self.get_instances():
            try:
                resp, instance_bans = instance.bans()
            except:
                continue
            if not resp:
                continue
            bans.extend(instance_bans[instance.name if instance.name != "local" else "127.0.0.1"].get("data", []))

        bans.sort(key=itemgetter("exp"))

        unique_bans = {}

        return [unique_bans.setdefault(item["ip"], item) for item in bans if item["ip"] not in unique_bans]

    def ban(self, ip: str, exp: float, reason: str, _id: Optional[int] = None) -> Union[str, list[str]]:
        if _id:
            instance = self.__instance_from_id(_id)
            try:
                if instance.ban(ip, exp, reason):
                    return ""
            except BaseException as e:
                return f"Can't ban {ip} on {instance.name}: {e}"
            return f"Can't ban {ip} on {instance.name}"

        try:
            return [instance.name for instance in self.get_instances() if not instance.ban(ip, exp, reason)]
        except BaseException as e:
            return f"Can't ban {ip}: {e}"

    def unban(self, ip: str, _id: Optional[int] = None) -> Union[str, list[str]]:
        if _id:
            instance = self.__instance_from_id(_id)
            try:
                if instance.unban(ip):
                    return ""
            except BaseException as e:
                return f"Can't unban {ip} on {instance.name}: {e}"
            return f"Can't unban {ip} on {instance.name}"

        try:
            return [instance.name for instance in self.get_instances() if not instance.unban(ip)]
        except BaseException as e:
            return f"Can't unban {ip}: {e}"

    def get_reports(self, _id: Optional[int] = None) -> List[dict[str, Any]]:
        if _id:
            instance = self.__instance_from_id(_id)
            try:
                resp, instance_reports = instance.reports()
            except:
                return []
            if not resp:
                return []
            return (instance_reports[instance.name if instance.name != "local" else "127.0.0.1"].get("msg") or {"requests": []})["requests"]

        reports: List[dict[str, Any]] = []
        for instance in self.get_instances():
            try:
                resp, instance_reports = instance.reports()
            except:
                continue

            if not resp:
                continue
            reports.extend((instance_reports[instance.name if instance.name != "local" else "127.0.0.1"].get("msg") or {"requests": []})["requests"])

        reports.sort(key=itemgetter("date"), reverse=True)

        return reports

    def get_metrics(self, plugin_id: str):
        # Get metrics from all instances
        metrics = {}
        for instance in self.get_instances():
            instance_name = instance.name if instance.name != "local" else "127.0.0.1"

            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except:
                continue

            # filters
            if not resp:
                continue

            if (
                not isinstance(instance_metrics.get(instance_name, {"msg": None}).get("msg"), dict)
                or instance_metrics[instance_name].get("status", "error") != "success"
            ):
                continue

            metric_data = instance_metrics[instance_name]["msg"]

            # Update metrics looking for value type
            for key, value in metric_data.items():
                if key not in metrics:
                    metrics[key] = value
                    continue

                # Some value are the same for all instances, we don't need to update them
                # Example redis_nb_keys count
                if key == "redis_nb_keys":
                    continue

                # Case value is number, add it to the existing value
                if isinstance(value, (int, float)):
                    metrics[key] += value
                # Case value is string, replace the existing value
                elif isinstance(value, str):
                    metrics[key] = value
                # Case value is list, extend it to the existing value
                elif isinstance(value, list):
                    metrics[key].extend(value)
                # Case value is a dict, loop on it and update the existing value
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if k not in metrics[key]:
                            metrics[key][k] = v
                        elif isinstance(v, (int, float)):
                            metrics[key][k] += v
                        elif isinstance(v, list):
                            metrics[key][k].extend(v)
                        elif isinstance(v, str):
                            metrics[key][k] = v
        return metrics

    def get_ping(self, plugin_id: str):
        # Need at least one instance to get a success ping to return success
        ping = {"status": "error"}
        for instance in self.get_instances():
            instance_name = instance.name if instance.name != "local" else "127.0.0.1"

            try:
                resp, ping_data = instance.ping(plugin_id)
            except:
                continue

            if not resp:
                continue

            ping["status"] = ping_data[instance_name].get("status", "error")

            if ping["status"] == "success":
                break

        return ping

    def get_data(self, plugin_endpoint: str):
        # Need at least one instance to get a success ping to return success
        data = []
        for instance in self.get_instances():

            instance_name = instance.name if instance.name != "local" else "127.0.0.1"

            try:
                resp, instance_data = instance.data(plugin_endpoint)
            except:
                data.append({instance_name: {"status": "error"}})
                continue

            if not resp:
                data.append({instance_name: {"status": "error"}})
                continue

            if instance_data[instance_name].get("status", "error") == "error":
                data.append({instance_name: {"status": "error"}})
                continue

            data.append({instance_name: instance_data[instance_name].get("msg", {})})

        return data
