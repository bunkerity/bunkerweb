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

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for instance module")


class Instance:
    hostname: str
    name: str
    method: Literal["ui", "scheduler", "autoconf", "manual"]
    status: Literal["loading", "up", "down"]
    type: Literal["static", "container", "pod"]
    creation_date: datetime
    last_seen: datetime
    apiCaller: ApiCaller

    # Initialize Instance with connection details and API caller for remote management.
    # Creates instance object with all necessary properties for BunkerWeb instance communication and control.
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
        if DEBUG_MODE:
            logger.debug(f"Instance.__init__() called for hostname: {hostname}, name: {name}, status: {status}")
        
        self.hostname = hostname
        self.name = name
        self.method = method
        self.status = status
        self.type = type
        self.creation_date = creation_date
        self.last_seen = last_seen
        self.apiCaller = apiCaller or ApiCaller()
        
        if DEBUG_MODE:
            logger.debug(f"Instance initialized: {hostname} ({name}) - {status}")

    # Create Instance object from hostname by querying database for instance details.
    # Retrieves instance configuration and creates API caller for remote communication and management.
    @staticmethod
    def from_hostname(hostname: str, db) -> Optional["Instance"]:
        if DEBUG_MODE:
            logger.debug(f"Instance.from_hostname() called for hostname: {hostname}")
        
        try:
            instance = db.get_instance(hostname)
            if not instance:
                if DEBUG_MODE:
                    logger.debug(f"No instance found for hostname: {hostname}")
                return None

            if DEBUG_MODE:
                logger.debug(f"Found instance in database: {instance.get('server_name', 'Unknown')} at {hostname}")

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
        except Exception as e:
            logger.exception(f"Failed to create instance from hostname: {hostname}")
            return None

    # Get unique identifier for instance.
    # Returns hostname for instance identification and management operations.
    @property
    def id(self) -> str:
        return self.hostname

    # Reload instance configuration with optional testing validation.
    # Triggers configuration reload on remote instance with test parameter based on environment settings.
    def reload(self) -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.reload() called for {self.hostname}")
        
        try:
            test_param = 'no' if getenv('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'
            if DEBUG_MODE:
                logger.debug(f"Reloading {self.hostname} with test={test_param}")
            
            result = self.apiCaller.send_to_apis("POST", f"/reload?test={test_param}")[0]
            
            if result:
                logger.info(f"Successfully reloaded instance: {self.hostname}")
                return f"Instance {self.hostname} has been reloaded."
            else:
                logger.warning(f"Failed to reload instance: {self.hostname}")
                return f"Can't reload instance {self.hostname}"
        except BaseException as e:
            logger.exception(f"Exception during reload of instance: {self.hostname}")
            return f"Can't reload instance {self.hostname}: {e}"

    # Start instance (not implemented yet).
    # Placeholder method for starting stopped BunkerWeb instances remotely.
    def start(self) -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.start() called for {self.hostname} (not implemented)")
        
        raise NotImplementedError("Method not implemented yet")
        try:
            result = self.apiCaller.send_to_apis("POST", "/start")[0]
        except BaseException as e:
            logger.exception(f"Exception during start of instance: {self.hostname}")
            return f"Can't start instance {self.hostname}: {e}"

        if result:
            logger.info(f"Successfully started instance: {self.hostname}")
            return f"Instance {self.hostname} has been started."
        return f"Can't start instance {self.hostname}"

    # Stop instance by sending stop command to remote API.
    # Gracefully stops BunkerWeb instance through remote API call with proper error handling.
    def stop(self) -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.stop() called for {self.hostname}")
        
        try:
            result = self.apiCaller.send_to_apis("POST", "/stop")[0]
            
            if result:
                logger.info(f"Successfully stopped instance: {self.hostname}")
                return f"Instance {self.hostname} has been stopped."
            else:
                logger.warning(f"Failed to stop instance: {self.hostname}")
                return f"Can't stop instance {self.hostname}"
        except BaseException as e:
            logger.exception(f"Exception during stop of instance: {self.hostname}")
            return f"Can't stop instance {self.hostname}: {e}"

    # Restart instance by sending restart command to remote API.
    # Performs full restart of BunkerWeb instance through remote API with status monitoring.
    def restart(self) -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.restart() called for {self.hostname}")
        
        try:
            result = self.apiCaller.send_to_apis("POST", "/restart")[0]
            
            if result:
                logger.info(f"Successfully restarted instance: {self.hostname}")
                return f"Instance {self.hostname} has been restarted."
            else:
                logger.warning(f"Failed to restart instance: {self.hostname}")
                return f"Can't restart instance {self.hostname}"
        except BaseException as e:
            logger.exception(f"Exception during restart of instance: {self.hostname}")
            return f"Can't restart instance {self.hostname}: {e}"

    # Ban IP address on instance with expiration time, reason, and scope.
    # Applies IP ban through remote API with global or service-specific scope and proper validation.
    def ban(self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global") -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.ban() called for {self.hostname} - IP: {ip}, scope: {ban_scope}, service: {service}")
        
        try:
            # Ensure ban_scope is either 'global' or 'service'
            if ban_scope not in ("global", "service"):
                if DEBUG_MODE:
                    logger.debug(f"Invalid ban_scope '{ban_scope}', defaulting to 'global'")
                ban_scope = "global"

            # If ban_scope is service but no service provided, default to global
            if ban_scope == "service" and (not service or service == "Web UI"):
                if DEBUG_MODE:
                    logger.debug(f"Service-specific ban requested but no valid service provided, defaulting to global")
                ban_scope = "global"

            result = self.apiCaller.send_to_apis("POST", "/ban", data={
                "ip": ip, 
                "exp": exp, 
                "reason": reason, 
                "service": service, 
                "ban_scope": ban_scope
            })[0]
            
            if result:
                scope_text = "globally" if ban_scope == "global" else f"for service {service}"
                logger.info(f"Successfully banned {ip} {scope_text} on instance {self.hostname}")
                return f"IP {ip} has been banned {scope_text} on instance {self.hostname} for {exp} seconds{f' with reason: {reason}' if reason else ''}."
            else:
                logger.warning(f"Failed to ban {ip} on instance {self.hostname}")
                return f"Can't ban {ip} on instance {self.hostname}"
        except BaseException as e:
            logger.exception(f"Exception during ban of {ip} on instance: {self.hostname}")
            return f"Can't ban {ip} on instance {self.hostname}: {e}"

    # Unban IP address on instance with optional service scope.
    # Removes IP ban through remote API with global or service-specific scope handling.
    def unban(self, ip: str, service: str = None) -> str:
        if DEBUG_MODE:
            logger.debug(f"Instance.unban() called for {self.hostname} - IP: {ip}, service: {service}")
        
        try:
            # Prepare request data
            data = {"ip": ip}

            # Only include service if it's specified and not a placeholder
            if service and service not in ("unknown", "Web UI", "default server"):
                data["service"] = service
                data["ban_scope"] = "service"
                if DEBUG_MODE:
                    logger.debug(f"Service-specific unban for {ip} on service: {service}")
            else:
                data["ban_scope"] = "global"
                if DEBUG_MODE:
                    logger.debug(f"Global unban for {ip}")

            result = self.apiCaller.send_to_apis("POST", "/unban", data=data)[0]
            
            if result:
                service_text = f" for service {service}" if service else ""
                logger.info(f"Successfully unbanned {ip}{service_text} on instance {self.hostname}")
                return f"IP {ip} has been unbanned{service_text} on instance {self.hostname}."
            else:
                logger.warning(f"Failed to unban {ip} on instance {self.hostname}")
                return f"Can't unban {ip} on instance {self.hostname}"
        except BaseException as e:
            service_text = f" for service {service}" if service else ""
            logger.exception(f"Exception during unban of {ip}{service_text} on instance: {self.hostname}")
            return f"Can't unban {ip}{service_text} on instance {self.hostname}: {e}"

    # Get list of banned IPs from instance.
    # Retrieves current ban list from remote instance through API call with error handling.
    def bans(self) -> Tuple[str, dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.bans() called for {self.hostname}")
        
        try:
            result = self.apiCaller.send_to_apis("GET", "/bans", response=True)
            
            if result[0]:
                if DEBUG_MODE:
                    ban_count = len(result[1].get(self.hostname, {}).get("data", []))
                    logger.debug(f"Successfully retrieved {ban_count} bans from {self.hostname}")
                return "", result[1]
            else:
                logger.warning(f"Failed to get bans from instance {self.hostname}")
                return f"Can't get bans from instance {self.hostname}", result[1]
        except BaseException as e:
            logger.exception(f"Exception during bans retrieval from instance: {self.hostname}")
            return f"Can't get bans from instance {self.hostname}: {e}", {}

    # Get request reports from instance for monitoring and analysis.
    # Retrieves request metrics and reports from remote instance through API call.
    def reports(self) -> Tuple[bool, dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.reports() called for {self.hostname}")
        
        try:
            result = self.apiCaller.send_to_apis("GET", "/metrics/requests", response=True)
            if DEBUG_MODE:
                logger.debug(f"Reports request completed for {self.hostname}, success: {result[0]}")
            return result
        except Exception as e:
            logger.exception(f"Exception during reports retrieval from instance: {self.hostname}")
            return False, {}

    # Get plugin-specific metrics from instance for monitoring.
    # Retrieves detailed metrics for specified plugin from remote instance through API call.
    def metrics(self, plugin_id) -> Tuple[bool, dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.metrics() called for {self.hostname} - plugin: {plugin_id}")
        
        try:
            result = self.apiCaller.send_to_apis("GET", f"/metrics/{plugin_id}", response=True)
            if DEBUG_MODE:
                logger.debug(f"Metrics request completed for {self.hostname} plugin {plugin_id}, success: {result[0]}")
            return result
        except Exception as e:
            logger.exception(f"Exception during metrics retrieval from instance: {self.hostname}")
            return False, {}

    # Get Redis statistics from instance for cache monitoring.
    # Retrieves Redis performance and usage statistics from remote instance.
    def metrics_redis(self) -> Tuple[bool, dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.metrics_redis() called for {self.hostname}")
        
        try:
            result = self.apiCaller.send_to_apis("GET", "/redis/stats", response=True)
            if DEBUG_MODE:
                logger.debug(f"Redis metrics request completed for {self.hostname}, success: {result[0]}")
            return result
        except Exception as e:
            logger.exception(f"Exception during Redis metrics retrieval from instance: {self.hostname}")
            return False, {}

    # Ping instance or specific plugin to check availability and status.
    # Tests connectivity and health of instance or plugin through API call with response handling.
    def ping(self, plugin_id: Optional[str] = None) -> Tuple[Union[bool, str], dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.ping() called for {self.hostname} - plugin: {plugin_id}")
        
        if not plugin_id:
            try:
                result = self.apiCaller.send_to_apis("GET", "/ping")
                
                if result[0]:
                    if DEBUG_MODE:
                        logger.debug(f"Instance {self.hostname} ping successful")
                    return f"Instance {self.hostname} is up", result[1]
                else:
                    if DEBUG_MODE:
                        logger.debug(f"Instance {self.hostname} ping failed")
                    return f"Can't ping instance {self.hostname}", result[1]
            except BaseException as e:
                logger.exception(f"Exception during ping of instance: {self.hostname}")
                return f"Can't ping instance {self.hostname}: {e}", {}
        
        try:
            result = self.apiCaller.send_to_apis("POST", f"/{plugin_id}/ping", response=True)
            if DEBUG_MODE:
                logger.debug(f"Plugin {plugin_id} ping completed for {self.hostname}, success: {result[0]}")
            return result
        except Exception as e:
            logger.exception(f"Exception during plugin {plugin_id} ping on instance: {self.hostname}")
            return False, {}

    # Get plugin-specific data from instance endpoint.
    # Retrieves custom data from plugin endpoints for specialized functionality and monitoring.
    def data(self, plugin_endpoint) -> Tuple[bool, dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"Instance.data() called for {self.hostname} - endpoint: {plugin_endpoint}")
        
        try:
            result = self.apiCaller.send_to_apis("GET", f"/{plugin_endpoint}", response=True)
            if DEBUG_MODE:
                logger.debug(f"Data request for endpoint {plugin_endpoint} completed for {self.hostname}, success: {result[0]}")
            return result
        except Exception as e:
            logger.exception(f"Exception during data retrieval from endpoint {plugin_endpoint} on instance: {self.hostname}")
            return False, {}


class InstancesUtils:
    # Initialize InstancesUtils with database connection for instance management operations.
    # Provides centralized utilities for managing multiple BunkerWeb instances with database integration.
    def __init__(self, db):
        if DEBUG_MODE:
            logger.debug("InstancesUtils.__init__() called")
        self.__db = db

    # Get list of instances from database with optional status filtering.
    # Returns Instance objects for all or filtered instances based on status with API caller setup.
    def get_instances(self, status: Optional[Literal["loading", "up", "down"]] = None) -> List[Instance]:
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_instances() called with status filter: {status}")
        
        try:
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
            
            if DEBUG_MODE:
                logger.debug(f"Retrieved {len(instances)} instances from database")
            
            return instances
        except Exception as e:
            logger.exception("Exception during instances retrieval from database")
            return []

    # Reload all instances and return list of failed reloads or success message.
    # Performs bulk reload operation on multiple instances with comprehensive error tracking.
    def reload_instances(self, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        target_instances = instances or self.get_instances()
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.reload_instances() called for {len(target_instances)} instances")
        
        failed_instances = []
        for instance in target_instances:
            if instance.status == "down":
                failed_instances.append(instance.name)
                if DEBUG_MODE:
                    logger.debug(f"Skipping reload of down instance: {instance.name}")
            elif instance.reload().startswith("Can't reload"):
                failed_instances.append(instance.name)
                if DEBUG_MODE:
                    logger.debug(f"Failed to reload instance: {instance.name}")
        
        if failed_instances:
            logger.warning(f"Failed to reload {len(failed_instances)} instances: {failed_instances}")
            return failed_instances
        else:
            logger.info(f"Successfully reloaded all {len(target_instances)} instances")
            return "Successfully reloaded instances"

    # Ban IP on all instances and return list of failed bans or empty string.
    # Performs bulk ban operation across multiple instances with scope and service validation.
    def ban(
        self, ip: str, exp: float, reason: str, service: str, ban_scope: str = "global", *, instances: Optional[List[Instance]] = None
    ) -> Union[list[str], str]:
        target_instances = instances or self.get_instances(status="up")
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.ban() called for IP {ip} on {len(target_instances)} instances, scope: {ban_scope}")
        
        failed_instances = []
        for instance in target_instances:
            if instance.ban(ip, exp, reason, service, ban_scope).startswith("Can't ban"):
                failed_instances.append(instance.name)
                if DEBUG_MODE:
                    logger.debug(f"Failed to ban {ip} on instance: {instance.name}")
        
        if failed_instances:
            logger.warning(f"Failed to ban {ip} on {len(failed_instances)} instances: {failed_instances}")
        else:
            logger.info(f"Successfully banned {ip} on all {len(target_instances)} instances")
        
        return failed_instances or ""

    # Unban IP on all instances and return list of failed unbans or empty string.
    # Performs bulk unban operation across multiple instances with service scope handling.
    def unban(self, ip: str, service: str = None, *, instances: Optional[List[Instance]] = None) -> Union[list[str], str]:
        target_instances = instances or self.get_instances(status="up")
        service_text = f" for service {service}" if service else ""
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.unban() called for IP {ip}{service_text} on {len(target_instances)} instances")
        
        failed_instances = []
        for instance in target_instances:
            if instance.unban(ip, service).startswith("Can't unban"):
                failed_instances.append(instance.name)
                if DEBUG_MODE:
                    logger.debug(f"Failed to unban {ip}{service_text} on instance: {instance.name}")
        
        if failed_instances:
            logger.warning(f"Failed to unban {ip}{service_text} on {len(failed_instances)} instances: {failed_instances}")
        else:
            logger.info(f"Successfully unbanned {ip}{service_text} on all {len(target_instances)} instances")
        
        return failed_instances or ""

    # Get unique bans from all instances or a specific instance and sort them by expiration date
    # Aggregates and deduplicates ban lists from multiple instances with proper scope handling.
    def get_bans(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_bans() called for hostname: {hostname}")

        def get_instance_bans(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_bans = instance.bans()
            if resp:
                return []
            return instance_bans[instance.hostname].get("data", [])

        bans: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                if DEBUG_MODE:
                    logger.debug(f"No instance found for hostname: {hostname}")
                return []
            bans = get_instance_bans(instance)
        else:
            target_instances = instances or self.get_instances(status="up")
            for instance in target_instances:
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

        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(unique_bans)} unique bans from {len(bans)} total bans")

        return list(unique_bans.values())

    # Get reports from all instances or a specific instance and sort them by date
    # Aggregates request reports from multiple instances for comprehensive monitoring and analysis.
    def get_reports(self, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None) -> List[dict[str, Any]]:
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_reports() called for hostname: {hostname}")

        def get_instance_reports(instance: Instance) -> List[dict[str, Any]]:
            resp, instance_reports = instance.reports()
            if not resp:
                return []
            return (instance_reports[instance.hostname].get("msg") or {"requests": []}).get("requests", [])

        reports: List[dict[str, Any]] = []
        if hostname:
            instance = Instance.from_hostname(hostname, self.__db)
            if not instance:
                if DEBUG_MODE:
                    logger.debug(f"No instance found for hostname: {hostname}")
                return []
            reports = get_instance_reports(instance)
        else:
            target_instances = instances or self.get_instances(status="up")
            for instance in target_instances:
                reports.extend(get_instance_reports(instance))

        sorted_reports = sorted(reports, key=itemgetter("date"), reverse=True)
        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(sorted_reports)} reports from instances")

        return sorted_reports

    # Get metrics from all instances or a specific instance, with Redis integration
    # Aggregates metrics from multiple sources with Redis priority and intelligent deduplication.
    def get_metrics(self, plugin_id: str, hostname: Optional[str] = None, *, instances: Optional[List[Instance]] = None):
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_metrics() called for plugin: {plugin_id}, hostname: {hostname}")
        
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

                if DEBUG_MODE:
                    logger.debug(f"Found {len(keys)} Redis metric keys for plugin {plugin_id}")

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

                if DEBUG_MODE:
                    logger.debug(f"Processed {len(redis_metrics)} Redis metrics for plugin {plugin_id}")
                return redis_metrics
            except Exception as e:
                logger.exception(f"Failed to get metrics from Redis for plugin {plugin_id}")
                return {}

        def get_instance_metrics(instance: Instance) -> dict[str, Any]:
            # Get metrics from a single instance
            try:
                if plugin_id == "redis":
                    resp, instance_metrics = instance.metrics_redis()
                else:
                    resp, instance_metrics = instance.metrics(plugin_id)
            except Exception as e:
                logger.exception(f"Can't get metrics from {instance.hostname}")
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
                    if DEBUG_MODE:
                        logger.debug(f"Using Redis metrics for {plugin_id}, skipping instance metrics")
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
                target_instances = instances or self.get_instances(status="up")
                for instance in target_instances:
                    instance_metrics = get_instance_metrics(instance)
                    metrics = aggregate_metrics(metrics, instance_metrics)

        if DEBUG_MODE:
            logger.debug(f"Aggregated metrics for plugin {plugin_id}: {len(metrics)} metric keys")

        return metrics

    # Get ping from all instances and return the first success
    # Tests connectivity across multiple instances and returns first successful ping response.
    def get_ping(self, plugin_id: str, *, instances: Optional[List[Instance]] = None):
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_ping() called for plugin: {plugin_id}")
        
        ping = {"status": "error"}
        target_instances = instances or self.get_instances(status="up")
        
        for instance in target_instances:
            try:
                resp, ping_data = instance.ping(plugin_id)
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Ping failed for instance {instance.hostname}: {e}")
                continue

            if not resp:
                continue

            ping["status"] = ping_data[instance.hostname].get("status", "error")

            if ping["status"] == "success":
                if DEBUG_MODE:
                    logger.debug(f"Successful ping response from instance: {instance.hostname}")
                return ping
        
        if DEBUG_MODE:
            logger.debug(f"No successful ping responses for plugin {plugin_id}")
        return ping

    # Get data from all instances and return the first success
    # Retrieves custom data from plugin endpoints across multiple instances with error handling.
    def get_data(self, plugin_endpoint: str, *, instances: Optional[List[Instance]] = None):
        if DEBUG_MODE:
            logger.debug(f"InstancesUtils.get_data() called for endpoint: {plugin_endpoint}")
        
        data = []
        target_instances = instances or self.get_instances(status="up")
        
        for instance in target_instances:
            try:
                resp, instance_data = instance.data(plugin_endpoint)
            except Exception as e:
                if DEBUG_MODE:
                    logger.debug(f"Data request failed for instance {instance.hostname}: {e}")
                data.append({instance.hostname: {"status": "error"}})
                continue

            if not resp:
                data.append({instance.hostname: {"status": "error"}})
                continue

            if instance_data[instance.hostname].get("status", "error") == "error":
                data.append({instance.hostname: {"status": "error"}})
                continue

            data.append({instance.hostname: instance_data[instance.hostname].get("msg", {})})
        
        if DEBUG_MODE:
            successful_responses = sum(1 for item in data if list(item.values())[0].get("status") != "error")
            logger.debug(f"Data request for {plugin_endpoint}: {successful_responses}/{len(data)} successful responses")
        
        return data
