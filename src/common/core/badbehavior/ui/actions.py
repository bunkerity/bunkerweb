import os
from logging import getLogger
from operator import itemgetter
from traceback import format_exc
from datetime import datetime


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if os.getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def pre_render(**kwargs):
    # Process and format badbehavior metrics for UI rendering
    # Takes bw_instances_utils from kwargs to retrieve metrics data
    # Returns formatted data structure for dashboard visualization
    logger = getLogger("UI")
    debug_log(logger, "Starting pre_render function for badbehavior")
    
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
        debug_log(logger, "Retrieving badbehavior metrics from instances")
        metrics = kwargs["bw_instances_utils"].get_metrics("badbehavior")
        debug_log(logger, f"Retrieved {len(metrics)} metric entries")

        # Format data for top_bad_behavior_status
        debug_log(logger, "Processing status code metrics")
        format_data = [
            {
                "code": int(key.split("_")[2]),
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_status_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        debug_log(logger, f"Found {len(format_data)} status code entries")
        
        data = {"code": [], "count": []}
        for item in format_data:
            data["code"].append(item["code"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_status"]["data"] = data
        debug_log(logger, "Completed status code data formatting")

        # Format data for top_bad_behavior_ips
        debug_log(logger, "Processing IP address metrics")
        format_data = [
            {
                "ip": key.split("_")[2],
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_ip_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        debug_log(logger, f"Found {len(format_data)} IP address entries")
        
        data = {"ip": [], "count": []}
        for item in format_data:
            data["ip"].append(item["ip"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_ips"]["data"] = data
        debug_log(logger, "Completed IP address data formatting")

        # Format data for top_bad_behavior_urls
        debug_log(logger, "Processing URL metrics")
        format_data = [
            {
                # Use split with maxsplit=2 to handle URLs with underscores
                "url": key.split("_", 2)[2],
                "count": int(value),
            }
            for key, value in metrics.items()
            if key.startswith("counter_url_")
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        debug_log(logger, f"Found {len(format_data)} URL entries")
        
        data = {"url": [], "count": []}
        for item in format_data:
            data["url"].append(item["url"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_urls"]["data"] = data
        debug_log(logger, "Completed URL data formatting")

        # Format data for list_bad_behavior_history
        debug_log(logger, "Processing increment history data")
        list_data = {
            "date": [],
            "id": [],
            "ip": [],
            "server_name": [],
            "method": [],
            "url": [],
            "status": []
        }
        
        if "table_increments" in metrics:
            increment_count = len(metrics["table_increments"])
            debug_log(logger, f"Processing {increment_count} increment records")
            
            for increment in metrics["table_increments"]:
                list_data["date"].append(
                    datetime.fromtimestamp(increment["date"]).isoformat()
                )
                list_data["id"].append(increment["id"])
                list_data["ip"].append(increment["ip"])
                list_data["server_name"].append(increment["server_name"])
                list_data["method"].append(increment["method"])
                list_data["url"].append(increment["url"])
                list_data["status"].append(increment["status"])
        else:
            debug_log(logger, "No table_increments found in metrics")
            
        ret["list_bad_behavior_history"]["data"] = list_data
        debug_log(logger, "Completed increment history data formatting")
        debug_log(logger, "Successfully completed pre_render processing")

    except BaseException as e:
        debug_log(logger, f"Exception occurred during pre_render: {str(e)}")
        logger.debug(format_exc())
        logger.error(f"Failed to get badbehavior metrics: {e}")
        # Reset all data sections to empty state on error
        for section in ret.values():
            if isinstance(section, dict) and "data" in section:
                section["data"] = {}

    return ret


def badbehavior(**kwargs):
    # Placeholder function for badbehavior-specific actions
    # Currently empty but reserved for future badbehavior operations
    # Takes arbitrary keyword arguments for flexibility
    logger = getLogger("UI")
    debug_log(logger, "badbehavior function called")
    pass