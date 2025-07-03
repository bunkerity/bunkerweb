from logging import getLogger
from operator import itemgetter
from traceback import format_exc
from datetime import datetime


def pre_render(**kwargs):
    logger = getLogger("UI")
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
        metrics = kwargs["bw_instances_utils"].get_metrics("badbehavior")

        # Format data for top_bad_behavior_status
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

        # Format data for top_bad_behavior_ips
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

        # Format data for top_bad_behavior_urls
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

        # Format data for list_bad_behavior_history
        list_data = {"date": [], "id": [], "ip": [], "server_name": [], "method": [], "url": [], "status": []}
        if "table_increments" in metrics:
            seen_ids = set()
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
        ret["list_bad_behavior_history"]["data"] = list_data

    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get badbehavior metrics: {e}")
        ret["error"] = str(e)

    return ret


def badbehavior(**kwargs):
    pass
