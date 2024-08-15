#!/usr/bin/env python3
from datetime import datetime
from operator import itemgetter
from typing import Any, List, Literal, Optional, Tuple, Union

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore


class Instance:
    hostname: str
    name: str
    method: Literal["ui", "scheduler", "autoconf", "manual"]
    status: Literal["loading", "up", "down"]
    type: Literal["static", "container", "pod"]
    creation_date: datetime
    last_seen: datetime
    apiCaller: ApiCaller

    def __init__(
        self,
        hostname: str,
        name: str,
        method: Literal["ui", "scheduler", "autoconf", "manual"],
        status: Literal["loading", "up", "down"],
        type: Literal["static", "container", "pod"],
        creation_date: datetime,
        last_seen: datetime,
        apiCaller: ApiCaller,
    ) -> None:
        self.hostname = hostname
        self.name = name
        self.method = method
        self.status = status
        self.type = type
        self.creation_date = creation_date
        self.last_seen = last_seen
        self.apiCaller = apiCaller or ApiCaller()

    @staticmethod
    def from_hostname(hostname: str, db) -> Optional["Instance"]:
        instance = db.get_instance(hostname)
        if not instance:
            return None

        return Instance(
            instance["hostname"],
            instance["server_name"],
            instance["method"],
            instance["status"],
            instance["type"],
            instance["creation_date"],
            instance["last_seen"],
            ApiCaller(
                [
                    API(
                        f"http://{instance['hostname']}:{instance['port']}",
                        instance["server_name"],
                    )
                ]
            ),
        )

    @property
    def id(self) -> str:
        return self.hostname

    def reload(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/reload")[0]
        except BaseException as e:
            return f"Can't reload {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been reloaded."
        return f"Can't reload {self.hostname}"

    def start(self) -> str:
        raise NotImplementedError("Method not implemented yet")
        try:
            result = self.apiCaller.send_to_apis("POST", "/start")[0]
        except BaseException as e:
            return f"Can't start {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been started."
        return f"Can't start {self.hostname}"

    def stop(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/stop")[0]
        except BaseException as e:
            return f"Can't stop {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been stopped."
        return f"Can't stop {self.hostname}"

    def restart(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/restart")[0]
        except BaseException as e:
            return f"Can't restart {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been restarted."
        return f"Can't restart {self.hostname}"

    def ban(self, ip: str, exp: float, reason: str) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason})[0]
        except BaseException as e:
            return f"Can't ban {ip} on {self.hostname}: {e}"

        if result:
            return f"IP {ip} has been banned on {self.hostname} for {exp} seconds{f' with reason: {reason}' if reason else ''}."
        return f"Can't ban {ip} on {self.hostname}"

    def unban(self, ip: str) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/unban", data={"ip": ip})[0]
        except BaseException as e:
            return f"Can't unban {ip} on {self.hostname}: {e}"

        if result:
            return f"IP {ip} has been unbanned on {self.hostname}."
        return f"Can't unban {ip} on {self.hostname}"

    def bans(self) -> Tuple[str, dict[str, Any]]:
        try:
            result = self.apiCaller.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return f"Can't get bans from {self.hostname}: {e}", result[1]

        if result[0]:
            return "", result[1]
        return f"Can't get bans from {self.hostname}", result[1]

    def reports(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)

    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)

    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)

    def ping(self, plugin_id: Optional[str] = None) -> Tuple[bool, dict[str, Any]]:
        if not plugin_id:
            try:
                result = self.apiCaller.send_to_apis("GET", "/ping")[0]
            except BaseException as e:
                return f"Can't ping {self.hostname}: {e}", {}

            if result:
                return f"Instance {self.hostname} is up", {}
            return f"Can't ping {self.hostname}", {}
        return self.apiCaller.send_to_apis("POST", f"/{plugin_id}/ping", response=True)

    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)


class InstancesUtils:
    def __init__(self, db):
        self.__db = db

    def get_instances(self) -> list[Instance]:
        return [
            Instance(
                instance["hostname"],
                instance["name"],
                instance["method"],
                instance["status"],
                instance["type"],
                instance["creation_date"],
                instance["last_seen"],
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

    def reload_instances(self, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [
            instance.name for instance in instances or self.get_instances() if instance.status == "down" or instance.reload().startswith("Can't reload")
        ] or "Successfully reloaded instances"

    def ban(self, ip: str, exp: float, reason: str, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [instance.name for instance in instances or self.get_instances() if instance.ban(ip, exp, reason).startswith("Can't ban")] or ""

    def unban(self, ip: str, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [instance.name for instance in instances or self.get_instances() if instance.unban(ip).startswith("Can't unban")] or ""

    def get_bans(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get unique bans from all instances or a specific instance and sort them by expiration date"""

        def get_instance_bans(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_bans = instance.bans()
            if resp:
                self.__db.logger.warning(resp)
                return []
            return instance_bans[instance.hostname].get("data", [])

        bans: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            bans = get_instance_bans(instance)
        else:
            for instance in instances or self.get_instances():
                bans.extend(get_instance_bans(instance))

        unique_bans = {}
        return [unique_bans.setdefault(item["ip"], item) for item in sorted(bans, key=itemgetter("exp")) if item["ip"] not in unique_bans]

    def get_reports(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get reports from all instances or a specific instance and sort them by date"""

        def get_instance_reports(instance: Instance) -> Tuple[bool, dict[str, Any]]:
            resp, instance_reports = instance.reports()
            if resp:
                self.__db.logger.warning(resp)
                return []
            return (instance_reports[instance.hostname].get("msg") or {"requests": []}).get("requests", [])

        reports: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            reports = get_instance_reports(instance)
        else:
            for instance in instances or self.get_instances():
                reports.extend(get_instance_reports(instance))

        return sorted(reports, key=itemgetter("date"), reverse=True)

    def get_metrics(self, plugin_id: str, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None):
        """Get metrics from all instances or a specific instance"""

        def update_metrics_from_instance(instance: Instance, metrics: dict) -> dict[str, Any]:
            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except BaseException as e:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}: {e}")
                return metrics

            # filters
            if not resp:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}")
                return metrics

            if (
                not isinstance(instance_metrics.get(instance.hostname, {"msg": None}).get("msg"), dict)
                or instance_metrics[instance.hostname].get("status", "error") != "success"
            ):
                self.__db.logger.warning(
                    f"Can't get metrics from {instance.hostname}: {instance_metrics[instance.hostname].get('msg')} - {instance_metrics[instance.hostname].get('status')}"
                )
                return metrics

            # Update metrics looking for value type
            for key, value in instance_metrics[instance.hostname]["msg"].items():
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
                            continue
                        elif isinstance(v, (int, float)):
                            metrics[key][k] += v
                            continue
                        elif isinstance(v, list):
                            metrics[key][k].extend(v)
                            continue
                        metrics[key][k] = v

            return metrics

        metrics = {}
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return {}
            return update_metrics_from_instance(instance, metrics.copy())

        for instance in instances or self.get_instances():
            metrics = update_metrics_from_instance(instance, metrics.copy())
        return metrics

    def get_ping(self, plugin_id: str, *, instances: Optional[List[Instance]] = None):
        """Get ping from all instances and return the first success"""
        ping = {"status": "error"}
        for instance in instances or self.get_instances():
            try:
                resp, ping_data = instance.ping(plugin_id)
            except:
                continue

            if not resp:
                continue

            ping["status"] = ping_data[instance.hostname].get("status", "error")

            if ping["status"] == "success":
                return ping
        return ping

    def get_data(self, plugin_endpoint: str, *, instances: Optional[List[Instance]] = None):
        """Get data from all instances and return the first success"""
        data = []
        for instance in instances or self.get_instances():
            try:
                resp, instance_data = instance.data(plugin_endpoint)
            except:
                data.append({instance.hostname: {"status": "error"}})
                continue

            if not resp:
                data.append({instance.hostname: {"status": "error"}})
                continue

            if instance_data[instance.hostname].get("status", "error") == "error":
                data.append({instance.hostname: {"status": "error"}})
                continue

            data.append({instance.hostname: instance_data[instance.hostname].get("msg", {})})
        return data
