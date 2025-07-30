#!/usr/bin/env python3
from datetime import datetime
from json import loads
from operator import itemgetter
from os import getenv
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
            result = self.apiCaller.send_to_apis("POST", f"/reload?test={'no' if getenv('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'}")[0]
        except BaseException as e:
            return f"Can't reload instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been reloaded."
        return f"Can't reload instance {self.hostname}"

    def start(self) -> str:
        raise NotImplementedError("Method not implemented yet")
        try:
            result = self.apiCaller.send_to_apis("POST", "/start")[0]
        except BaseException as e:
            return f"Can't start instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been started."
        return f"Can't start instance {self.hostname}"

    def stop(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/stop")[0]
        except BaseException as e:
            return f"Can't stop instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been stopped."
        return f"Can't stop instance {self.hostname}"

    def restart(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/restart")[0]
        except BaseException as e:
            return f"Can't restart instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been restarted."
        return f"Can't restart instance {self.hostname}"

    def ban(self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global") -> str:
        try:
            # Ensure ban_scope is either 'global' or 'service'
            if ban_scope not in ("global", "service"):
                ban_scope = "global"

            # If ban_scope is service but no service provided, default to global
            if ban_scope == "service" and (not service or service == "Web UI"):
                ban_scope = "global"

            result = self.apiCaller.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason, "service": service, "ban_scope": ban_scope})[0]
        except BaseException as e:
            return f"Can't ban {ip} on instance {self.hostname}: {e}"

        if result:
            scope_text = "globally" if ban_scope == "global" else f"for service {service}"
            return f"IP {ip} has been banned {scope_text} on instance {self.hostname} for {exp} seconds{f' with reason: {reason}' if reason else ''}."
        return f"Can't ban {ip} on instance {self.hostname}"

    def unban(self, ip: str, service: str = None, ban_scope: str = "global") -> str:
        try:
            # Prepare request data
            data = {"ip": ip, "ban_scope": ban_scope}
            if service and service not in ("unknown", "Web UI", "default server"):
                data["service"] = service
            result = self.apiCaller.send_to_apis("POST", "/unban", data=data)[0]
        except BaseException as e:
            service_text = f" for service {service}" if service else ""
            return f"Can't unban {ip}{service_text} on instance {self.hostname}: {e}"

        if result:
            service_text = f" for service {service}" if service else ""
            return f"IP {ip} has been unbanned{service_text} on instance {self.hostname}."
        return f"Can't unban {ip} on instance {self.hostname}"

    def bans(self) -> Tuple[str, dict[str, Any]]:
        try:
            result = self.apiCaller.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            return f"Can't get bans from instance {self.hostname}: {e}", result[1]

        if result[0]:
            return "", result[1]
        return f"Can't get bans from instance {self.hostname}", result[1]

    def reports(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)

    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)

    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)

    def ping(self, plugin_id: Optional[str] = None) -> Tuple[Union[bool, str], dict[str, Any]]:
        if not plugin_id:
            try:
                result = self.apiCaller.send_to_apis("GET", "/ping")
            except BaseException as e:
                return f"Can't ping instance {self.hostname}: {e}", {}

            if result[0]:
                return f"Instance {self.hostname} is up", result[1]
            return f"Can't ping instance {self.hostname}", result[1]
        return self.apiCaller.send_to_apis("POST", f"/{plugin_id}/ping", response=True)

    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)


class InstancesUtils:
    def __init__(self, db):
        self.__db = db

    def get_instances(self, status: Optional[Literal["loading", "up", "down"]] = None) -> List[Instance]:
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
            if not status or instance["status"] == status
        ]

    def reload_instances(self, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [
            instance.name for instance in instances or self.get_instances() if instance.status == "down" or instance.reload().startswith("Can't reload")
        ] or "Successfully reloaded instances"

    def ban(
        self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None
    ) -> Union[list[str], str]:
        return [
            instance.name
            for instance in instances or self.get_instances(status="up")
            if instance.ban(ip, exp, reason, service, ban_scope).startswith("Can't ban")
        ] or ""

    def unban(self, ip: str, service: str = None, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [
            instance.name for instance in instances or self.get_instances(status="up") if instance.unban(ip, service, ban_scope).startswith("Can't unban")
        ] or ""

    def get_bans(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get unique bans from all instances or a specific instance and sort them by expiration date"""

        def get_instance_bans(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_bans = instance.bans()
            if resp:
                return []
            return instance_bans[instance.hostname].get("data", [])

        bans: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            bans = get_instance_bans(instance)
        else:
            for instance in instances or self.get_instances(status="up"):
                bans.extend(get_instance_bans(instance))

        # Improved deduplication that considers IP, scope, and service combination
        # A unique ban is defined by the combination of IP address, ban scope, and service
        unique_bans = {}
        for item in sorted(bans, key=itemgetter("exp")):
            # Normalize ban scope if not present
            if "ban_scope" not in item:
                if item.get("service", "_") == "_":
                    item["ban_scope"] = "global"
                else:
                    item["ban_scope"] = "service"

            # Create a unique key that combines IP, ban scope, and service
            ban_key = (item["ip"], item["ban_scope"], item.get("service", "_"))
            if ban_key not in unique_bans:
                unique_bans[ban_key] = item

        return list(unique_bans.values())

    def get_reports(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        """Get reports from all instances or a specific instance and sort them by date"""

        def get_instance_reports(instance: Instance) -> Tuple[bool, dict[str, Any]]:
            resp, instance_reports = instance.reports()
            if not resp:
                return []
            return (instance_reports[instance.hostname].get("msg") or {"requests": []}).get("requests", [])

        reports: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                return []
            reports = get_instance_reports(instance)
        else:
            for instance in instances or self.get_instances(status="up"):
                reports.extend(get_instance_reports(instance))

        return sorted(reports, key=itemgetter("date"), reverse=True)

    def get_metrics(self, plugin_id: str, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None):
        """Get metrics from all instances or a specific instance, with Redis integration"""
        from app.routes.utils import get_redis_client

        redis_client = get_redis_client()

        def aggregate_metrics(base_metrics: dict, new_metrics: dict) -> dict[str, Any]:
            """Aggregate metrics from different sources"""
            for key, value in new_metrics.items():
                if key not in base_metrics:
                    base_metrics[key] = value
                    continue

                # Some values are the same for all instances, don't aggregate them
                if key == "redis_nb_keys":
                    continue

                # Aggregate based on value type
                if isinstance(value, (int, float)):
                    base_metrics[key] += value
                elif isinstance(value, str):
                    base_metrics[key] = value
                elif isinstance(value, list):
                    if isinstance(base_metrics[key], list):
                        base_metrics[key].extend(value)
                    else:
                        base_metrics[key] = value
                elif isinstance(value, dict):
                    if not isinstance(base_metrics[key], dict):
                        base_metrics[key] = {}
                    for k, v in value.items():
                        if k not in base_metrics[key]:
                            base_metrics[key][k] = v
                        elif isinstance(v, (int, float)):
                            base_metrics[key][k] += v
                        elif isinstance(v, list):
                            if isinstance(base_metrics[key][k], list):
                                base_metrics[key][k].extend(v)
                            else:
                                base_metrics[key][k] = v
                        else:
                            base_metrics[key][k] = v
            return base_metrics

        def get_redis_metrics() -> dict[str, Any]:
            """Get aggregated metrics from Redis"""
            if not redis_client:
                return {}

            try:
                if plugin_id == "requests":
                    requests_data = redis_client.lrange("requests", 0, -1)
                    requests_list = []
                    seen_ids = set()
                    for item in requests_data:
                        try:
                            request = loads(item.decode("utf-8"))
                            req_id = request.get("id")
                            if req_id not in seen_ids:
                                seen_ids.add(req_id)
                                requests_list.append(request)
                        except Exception:
                            continue
                    return {"requests": requests_list}

                redis_metrics = {}
                # Get all metric keys for this plugin from all workers
                pattern = f"metrics:{plugin_id}_*"
                keys = redis_client.keys(pattern)

                for key in keys:
                    try:
                        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                        # Extract metric name from key (remove prefix and worker suffix)
                        metric_name = key_str.replace(f"metrics:{plugin_id}_", "").split(":")[0]

                        # Determine Redis data type and get value accordingly
                        key_type = redis_client.type(key)
                        if isinstance(key_type, bytes):
                            key_type = key_type.decode("utf-8")

                        decoded_value = None

                        if key_type == "string":
                            # Handle string values (counters and simple metrics)
                            value = redis_client.get(key)
                            if value is None:
                                continue

                            # Decode value based on its content
                            try:
                                decoded_value = loads(value.decode("utf-8"))
                            except (ValueError, UnicodeDecodeError):
                                # Try as number
                                try:
                                    decoded_value = float(value.decode("utf-8"))
                                    if decoded_value.is_integer():
                                        decoded_value = int(decoded_value)
                                except ValueError:
                                    # Fall back to string
                                    decoded_value = value.decode("utf-8")

                        elif key_type == "list":
                            # Handle list values (table metrics)
                            list_values = redis_client.lrange(key, 0, -1)
                            decoded_value = []
                            for item in list_values:
                                try:
                                    decoded_item = loads(item.decode("utf-8"))
                                    decoded_value.append(decoded_item)
                                except (ValueError, UnicodeDecodeError):
                                    # Fall back to string
                                    decoded_value.append(item.decode("utf-8"))

                        elif key_type == "none":
                            # Key doesn't exist
                            continue
                        else:
                            # Unsupported Redis data type, skip
                            self.__db.logger.warning(f"Unsupported Redis data type {key_type} for key {key_str}")
                            continue

                        if decoded_value is None:
                            continue

                        # Aggregate values for the same metric name across workers
                        if metric_name in redis_metrics:
                            if isinstance(redis_metrics[metric_name], (int, float)) and isinstance(decoded_value, (int, float)):
                                redis_metrics[metric_name] += decoded_value
                            elif isinstance(redis_metrics[metric_name], list) and isinstance(decoded_value, list):
                                redis_metrics[metric_name].extend(decoded_value)
                            # For other types, just use the latest value
                        else:
                            redis_metrics[metric_name] = decoded_value

                    except Exception as e:
                        self.__db.logger.warning(f"Failed to process Redis metric key {key}: {e}")
                        continue

                return redis_metrics
            except Exception as e:
                self.__db.logger.warning(f"Failed to get metrics from Redis: {e}")
                return {}

        def get_instance_metrics(instance: Instance) -> dict[str, Any]:
            """Get metrics from a single instance"""
            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except Exception as e:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}: {e}")
                return {}

            if not resp:
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}")
                return {}

            instance_data = instance_metrics.get(instance.hostname, {})
            if not isinstance(instance_data.get("data"), dict) or instance_data.get("status") != "success":
                self.__db.logger.warning(f"Can't get metrics from {instance.hostname}: {instance_data.get('msg')} - {instance_data.get('status')}")
                return {}

            return instance_data["data"]

        # Initialize metrics
        metrics = {}

        # If redis_client is available and we're not targeting a specific hostname,
        # prioritize Redis metrics as they're aggregated across all workers
        if redis_client and not hostname:
            redis_metrics = get_redis_metrics()
            if redis_metrics:
                # For requests specifically, if we have Redis data, don't fetch from instances
                # to avoid duplicates since Redis already contains the aggregated data
                if plugin_id == "requests" and redis_metrics:
                    return redis_metrics
                metrics = aggregate_metrics(metrics, redis_metrics)

        # Get instance metrics (either as fallback or for specific hostname)
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if instance:
                instance_metrics = get_instance_metrics(instance)
                metrics = aggregate_metrics(metrics, instance_metrics)
        else:
            # Only fetch from instances if we don't have Redis data for requests
            # or if we're looking for non-request metrics
            if not (redis_client and plugin_id == "requests" and metrics):
                for instance in instances or self.get_instances(status="up"):
                    instance_metrics = get_instance_metrics(instance)
                    metrics = aggregate_metrics(metrics, instance_metrics)

        return metrics

    def get_ping(self, plugin_id: str, *, instances: Optional[List[Instance]] = None):
        """Get ping from all instances and return the first success"""
        ping = {"status": "error"}
        for instance in instances or self.get_instances(status="up"):
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
        for instance in instances or self.get_instances(status="up"):
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
