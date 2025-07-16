from operator import itemgetter
from datetime import datetime
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
    title="badbehavior",
    log_file_path="/var/log/bunkerweb/badbehavior.log"
)

logger.debug("Debug mode enabled for badbehavior")


# Retrieves badbehavior metrics and prepares data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for badbehavior module")
    ret = {
        "top_bad_behavior_status": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "top_bad_behavior_ips": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 2,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "top_bad_behavior_urls": {
            "col-size": "col-12 col-md-4",
            "data": {},
            "order": {
                "column": 3,
                "dir": "desc",
            },
            "svg_color": "primary",
        },
        "list_bad_behavior_history": {
            "col-size": "col-12",
            "data": {},
            "order": {
                "column": 4,
                "dir": "desc",
            },
            "svg_color": "warning",
        },
    }
    try:
        logger.debug("Attempting to get badbehavior metrics from bw_instances_utils")
        metrics = kwargs["bw_instances_utils"].get_metrics("badbehavior")
        logger.debug(f"Retrieved badbehavior metrics: {len(metrics)} items")

        # Format data for top_bad_behavior_status
        logger.debug("Processing status code metrics")
        format_data = [
            {
                "code": int(key.split("_")[2]),
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_status_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"code": [], "count": []}
        for item in format_data:
            data["code"].append(item["code"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_status"]["data"] = data
        logger.debug(f"Processed {len(format_data)} status code entries")

        # Format data for top_bad_behavior_ips
        logger.debug("Processing IP address metrics")
        format_data = [
            {
                "ip": key.split("_")[2],
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_ip_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"ip": [], "count": []}
        for item in format_data:
            data["ip"].append(item["ip"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_ips"]["data"] = data
        logger.debug(f"Processed {len(format_data)} IP address entries")

        # Format data for top_bad_behavior_urls
        logger.debug("Processing URL metrics")
        format_data = [
            {
                "url": key.split("_", 2)[2],  # Use split with maxsplit=2 to handle URLs with underscores
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_url_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"url": [], "count": []}
        for item in format_data:
            data["url"].append(item["url"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_urls"]["data"] = data
        logger.debug(f"Processed {len(format_data)} URL entries")

        # Format data for list_bad_behavior_history
        logger.debug("Processing bad behavior history table")
        list_data = {"date": [], "id": [], "ip": [], "server_name": [], "method": [], "url": [], "status": []}
        if "table_increments" in metrics:
            seen_ids = set()
            logger.debug(f"Found {len(metrics['table_increments'])} table increment records")
            for increment in metrics["table_increments"]:
                # Deduplicate based on ID only
                if increment["id"] not in seen_ids:
                    seen_ids.add(increment["id"])
                    list_data["date"].append(datetime.fromtimestamp(increment["date"]).isoformat())
                    list_data["id"].append(increment["id"])
                    list_data["ip"].append(increment["ip"])
                    list_data["server_name"].append(increment["server_name"])
                    list_data["method"].append(increment["method"])
                    list_data["url"].append(increment["url"])
                    list_data["status"].append(increment["status"])
            logger.debug(f"Processed {len(seen_ids)} unique history records after deduplication")
        ret["list_bad_behavior_history"]["data"] = list_data

    except BaseException as e:
        logger.exception("Exception while getting badbehavior metrics")
        ret["error"] = str(e)

    logger.debug(f"pre_render() completed, returning data structure with {len(ret)} sections")
    return ret


# Placeholder function for badbehavior-specific operations.
def badbehavior(**kwargs):
    logger.debug("badbehavior() called")
    pass
