#!/usr/bin/env python3
from datetime import datetime
from json import loads
from operator import itemgetter
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from typing import Any, List, Literal, Optional, Tuple, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-instance",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-instance")

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

    # Initialize BunkerWeb instance with connection details and API caller.
    # Sets up instance metadata and creates API communication interface.
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
        logger.debug(f"Instance.__init__() called for hostname={hostname}, name={name}")
        self.hostname = hostname
        self.name = name
        self.method = method
        self.status = status
        self.type = type
        self.creation_date = creation_date
        self.last_seen = last_seen
        self.apiCaller = apiCaller or ApiCaller()

    # Create Instance object from hostname by querying database.
    # Returns None if instance not found in database records.
    @staticmethod
    def from_hostname(hostname: str, db) -> Optional["Instance"]:
        logger.debug(f"Instance.from_hostname() called for hostname={hostname}")
        instance = db.get_instance(hostname)
        if not instance:
            logger.debug(f"No instance found for hostname={hostname}")
            return None

        logger.debug(f"Creating Instance object for {instance['server_name']}")
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

    # Reload instance configuration with optional testing.
    # Sends reload command via API and returns success/failure message.
    def reload(self) -> str:
        logger.debug(f"Instance.reload() called for {self.hostname}")
        try:
            result = self.apiCaller.send_to_apis("POST", f"/reload?test={'no' if getenv('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'}")[0]
        except BaseException as e:
            logger.exception(f"Exception during reload for {self.hostname}")
            return f"Can't reload instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been reloaded."
        return f"Can't reload instance {self.hostname}"

    # Start instance service (not yet implemented).
    # Placeholder method for future instance start functionality.
    def start(self) -> str:
        raise NotImplementedError("Method not implemented yet")
        try:
            result = self.apiCaller.send_to_apis("POST", "/start")[0]
        except BaseException as e:
            return f"Can't start instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been started."
        return f"Can't start instance {self.hostname}"

    # Stop instance service via API command.
    # Sends stop command and returns operation result message.
    def stop(self) -> str:
        logger.debug(f"Instance.stop() called for {self.hostname}")
        try:
            result = self.apiCaller.send_to_apis("POST", "/stop")[0]
        except BaseException as e:
            logger.exception(f"Exception during stop for {self.hostname}")
            return f"Can't stop instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been stopped."
        return f"Can't stop instance {self.hostname}"

    # Restart instance service via API command.
    # Sends restart command and returns operation result message.
    def restart(self) -> str:
        try:
            result = self.apiCaller.send_to_apis("POST", "/restart")[0]
        except BaseException as e:
            return f"Can't restart instance {self.hostname}: {e}"

        if result:
            return f"Instance {self.hostname} has been restarted."
        return f"Can't restart instance {self.hostname}"

    # Ban IP address on instance with specified duration and scope.
    # Supports global or service-specific bans with reason logging.
    def ban(self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global") -> str:
        logger.debug(f"Instance.ban() called for {self.hostname}: ip={ip}, scope={ban_scope}")
        try:
            # Ensure ban_scope is either 'global' or 'service'
            if ban_scope not in ("global", "service"):
                ban_scope = "global"

            # If ban_scope is service but no service provided, default to global
            if ban_scope == "service" and (not service or service == "Web UI"):
                ban_scope = "global"

            result = self.apiCaller.send_to_apis("POST", "/ban", data={"ip": ip, "exp": exp, "reason": reason, "service": service, "ban_scope": ban_scope})[0]
        except BaseException as e:
            logger.exception(f"Exception during ban for {self.hostname}")
            return f"Can't ban {ip} on instance {self.hostname}: {e}"

        if result:
            scope_text = "globally" if ban_scope == "global" else f"for service {service}"
            return f"IP {ip} has been banned {scope_text} on instance {self.hostname} for {exp} seconds{f' with reason: {reason}' if reason else ''}."
        return f"Can't ban {ip} on instance {self.hostname}"

    # Remove ban for IP address with optional service specification.
    # Supports both global and service-specific unban operations.
    def unban(self, ip: str, service: str = None) -> str:
        logger.debug(f"Instance.unban() called for {self.hostname}: ip={ip}, service={service}")
        try:
            # Prepare request data
            data = {"ip": ip}

            # Only include service if it's specified and not a placeholder
            if service and service not in ("unknown", "Web UI", "default server"):
                data["service"] = service
                data["ban_scope"] = "service"
            else:
                data["ban_scope"] = "global"

            result = self.apiCaller.send_to_apis("POST", "/unban", data=data)[0]
        except BaseException as e:
            logger.exception(f"Exception during unban for {self.hostname}")
            service_text = f" for service {service}" if service else ""
            return f"Can't unban {ip}{service_text} on instance {self.hostname}: {e}"

        if result:
            service_text = f" for service {service}" if service else ""
            return f"IP {ip} has been unbanned{service_text} on instance {self.hostname}."
        return f"Can't unban {ip} on instance {self.hostname}"

    # Retrieve current ban list from instance.
    # Returns success status and ban data dictionary.
    def bans(self) -> Tuple[str, dict[str, Any]]:
        logger.debug(f"Instance.bans() called for {self.hostname}")
        try:
            result = self.apiCaller.send_to_apis("GET", "/bans", response=True)
        except BaseException as e:
            logger.exception(f"Exception during bans retrieval for {self.hostname}")
            return f"Can't get bans from instance {self.hostname}: {e}", result[1]

        if result[0]:
            return "", result[1]
        return f"Can't get bans from instance {self.hostname}", result[1]

    # Get request reports from instance for monitoring.
    # Returns success status and reports data structure.
    def reports(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)

    # Get plugin-specific metrics from instance.
    # Returns success status and metrics data for specified plugin.
    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)

    # Get Redis statistics from instance.
    # Returns success status and Redis performance metrics.
    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)

    # Ping instance or specific plugin to check availability.
    # Returns success status and response data for health monitoring.
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

    # Get custom data from plugin endpoint.
    # Returns success status and plugin-specific data.
    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        return self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)


class InstancesUtils:
    # Initialize instances utility with database connection.
    # Provides centralized instance management and operations.
    def __init__(self, db):
        logger.debug("InstancesUtils.__init__() called")
        self.__db = db

    # Get all instances with optional status filtering.
    # Returns list of Instance objects matching specified criteria.
    def get_instances(self, status: Optional[Literal["loading", "up", "down"]] = None) -> List[Instance]:
        logger.debug(f"InstancesUtils.get_instances() called with status={status}")
        instances = [
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
        logger.debug(f"Found {len(instances)} instances")
        return instances

    # Reload all or specified instances and return failed instance names.
    # Returns list of failed instances or success message.
    def reload_instances(self, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        logger.debug("InstancesUtils.reload_instances() called")
        failed_instances = [
            instance.name for instance in instances or self.get_instances() if instance.status == "down" or instance.reload().startswith("Can't reload")
        ]
        logger.debug(f"Reload operation completed: {len(failed_instances)} failures")
        return failed_instances or "Successfully reloaded instances"

    # Ban IP across all or specified instances with scope control.
    # Returns list of failed instance names or empty string on success.
    def ban(
        self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None
    ) -> Union[list[str], str]:
        return [
            instance.name
            for instance in instances or self.get_instances(status="up")
            if instance.ban(ip, exp, reason, service, ban_scope).startswith("Can't ban")
        ] or ""

    # Unban IP across all or specified instances.
    # Returns list of failed instance names or empty string on success.
    def unban(self, ip: str, service: str = None, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        return [instance.name for instance in instances or self.get_instances(status="up") if instance.unban(ip, service).startswith("Can't unban")] or ""

    # Get unique bans from all instances or specific instance with deduplication.
    # Returns sorted list of unique bans by IP, scope, and service combination.
    def get_bans(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        # Get unique bans from all instances or a specific instance and sort them by expiration date
        logger.debug(f"InstancesUtils.get_bans() called with hostname={hostname}")

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

        logger.debug(f"Returning {len(unique_bans)} unique bans from {len(bans)} total")
        return list(unique_bans.values())

    # Get reports from all instances or specific instance sorted by date.
    # Returns consolidated list of request reports for monitoring.
    def get_reports(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        # Get reports from all instances or a specific instance and sort them by date

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

    # Get aggregated metrics from instances and Redis with intelligent deduplication.
    # Prioritizes Redis data for accuracy and aggregates across multiple sources.
    def get_metrics(self, plugin_id: str, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None):
        # Get metrics from all instances or a specific instance, with Redis integration
        logger.debug(f"InstancesUtils.get_metrics() called: plugin_id={plugin_id}, hostname={hostname}")
        from app.routes.utils import get_redis_client

        redis_client = get_redis_client()

        def aggregate_metrics(base_metrics: dict, new_metrics: dict) -> dict[str, Any]:
            # Aggregate metrics from different sources
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
            # Get aggregated metrics from Redis
            if not redis_client:
                return {}

            try:
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
                            logger.warning(f"Unsupported Redis data type {key_type} for key {key_str}")
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
                        logger.exception(f"Failed to process Redis metric key {key}")
                        continue

                return redis_metrics
            except Exception as e:
                logger.exception("Failed to get metrics from Redis")
                return {}

        def get_instance_metrics(instance: Instance) -> dict[str, Any]:
            # Get metrics from a single instance
            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except Exception as e:
                logger.warning(f"Can't get metrics from {instance.hostname}: {e}")
                return {}

            if not resp:
                logger.warning(f"Can't get metrics from {instance.hostname}")
                return {}

            instance_data = instance_metrics.get(instance.hostname, {})
            if not isinstance(instance_data.get("msg"), dict) or instance_data.get("status") != "success":
                logger.warning(f"Can't get metrics from {instance.hostname}: {instance_data.get('msg')} - {instance_data.get('status')}")
                return {}

            return instance_data["msg"]

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

    # Get ping status from plugin across all instances.
    # Returns first successful ping response for health monitoring.
    def get_ping(self, plugin_id: str, *, instances: Optional[List[Instance]] = None):
        # Get ping from all instances and return the first success
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

    # Get custom data from plugin endpoint across all instances.
    # Returns data from all instances with error handling.
    def get_data(self, plugin_endpoint: str, *, instances: Optional[List[Instance]] = None):
        # Get data from all instances and return the first success
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
