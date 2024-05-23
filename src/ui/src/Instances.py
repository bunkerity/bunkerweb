#!/usr/bin/env python3
from operator import itemgetter
from os import sep
from os.path import join
from subprocess import DEVNULL, STDOUT, run
from typing import Any, List, Optional, Tuple, Union

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore


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
    def __init__(self, db):
        self.__db = db

    def __instance_from_id(self, _id) -> Instance:
        instances: list[Instance] = self.get_instances()
        for instance in instances:
            if instance.id == _id:
                return instance

        raise ValueError(f"Can't find instance with _id {_id}")

    def get_instances(self) -> list[Instance]:
        return [
            Instance(
                instance["hostname"],
                instance["hostname"],
                instance["hostname"],
                instance["method"],
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
            for instance in self.__db.get_instances()
        ]

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
