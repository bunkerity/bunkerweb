from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="bunkernet",
    log_file_path="/var/log/bunkerweb/bunkernet.log"
)

logger.debug("Debug mode enabled for bunkernet")


# Retrieves bunkernet metrics and prepares data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for bunkernet module")
    ret = {
        "ping_status": {
            "title": "BUNKERNET STATUS",
            "value": "error",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "info_instance_id": {
            "value": "Unknown",
            "title": "Instance ID",
            "subtitle_color": "primary",
            "svg_color": "primary",
            "col-size": "col-12 col-md-8",
            "card-classes": "h-100",
        },
        "list_bunkernet_ips": {
            "data": {},
            "types": {0: "ip-address"},
            "svg_color": "primary",
            "col-size": "col-12",
        },
    }
    try:
        logger.debug("Getting bunkernet ping status")
        ping_data = kwargs["bw_instances_utils"].get_ping("bunkernet")
        ret["ping_status"]["value"] = ping_data["status"]
        logger.debug(f"Ping status: {ping_data['status']}")

        logger.debug("Getting instance ID from cache")
        instance_id = kwargs["db"].get_job_cache_file("bunkernet-register", "instance.id")
        if instance_id:
            ret["info_instance_id"]["value"] = instance_id.decode("utf-8")
            logger.debug(f"Instance ID: {ret['info_instance_id']['value']}")

            logger.debug("Getting IP list from cache")
            ips_file = kwargs["db"].get_job_cache_file("bunkernet-data", "ip.list")
            logger.debug(f"IPs file: {ips_file}")
            if ips_file:
                ips_file = ips_file.decode("utf-8")
                ip_count = 0
                for ip in ips_file.split("\n"):
                    if ip.strip():  # Only process non-empty IPs
                        if "ip" not in ret["list_bunkernet_ips"]["data"]:
                            ret["list_bunkernet_ips"]["data"]["ip"] = []
                        ret["list_bunkernet_ips"]["data"]["ip"].append(ip)
                        ip_count += 1
                logger.debug(f"Processed {ip_count} IP addresses")
    except BaseException as e:
        logger.exception("Exception while getting bunkernet metrics")
        ret["error"] = str(e)

    logger.debug(f"pre_render() completed, returning bunkernet data")
    return ret


# Placeholder function for bunkernet-specific operations.
def bunkernet(**kwargs):
    logger.debug("bunkernet() called")
    pass
