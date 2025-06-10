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

        # Dictionaries to accumulate data
        status_counts = {}
        ips_counts = {}
        urls_counts = {}
        increments_data = []

        # Process all metrics in a single loop
        for key, value in metrics.items():
            if key.startswith("counter_status_"):
                # Process counters for top_bad_behavior_status
                code = int(key.split("_")[2])
                status_counts[code] = int(value)
            elif key.startswith("counter_ip_"):
                ip = key.split("_")[2]
                ips_counts[ip] = int(value)
            elif key.startswith("counter_url_"):
                url = key.split("_", 2)[2]  # Use split with maxsplit=2 to handle URLs with underscores
                urls_counts[url] = int(value)
            elif key == "table_increments":
                # Process increments for list_bad_behavior_history
                for increment in value:
                    increments_data.append(
                        {
                            "date": datetime.fromtimestamp(increment["date"]).isoformat(),
                            "id": increment["id"],
                            "ip": increment["ip"],
                            "server_name": increment["server_name"],
                            "method": increment["method"],
                            "url": increment["url"],
                            "status": increment["status"],
                        }
                    )

        # Format data for top_bad_behavior_status
        format_data = [
            {"code": code, "count": count}
            for code, count in status_counts.items()
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"code": [], "count": []}
        for item in format_data:
            data["code"].append(item["code"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_status"]["data"] = data

        # Format data for top_bad_behavior_ips
        format_data = [
            {"ip": ip, "count": count}
            for ip, count in ips_counts.items()
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"ip": [], "count": []}
        for item in format_data:
            data["ip"].append(item["ip"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_ips"]["data"] = data

        # Format data for top_bad_behavior_urls
        format_data = [
            {"url": url, "count": count}
            for url, count in urls_counts.items()
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"url": [], "count": []}
        for item in format_data:
            data["url"].append(item["url"])
            data["count"].append(item["count"])
        ret["top_bad_behavior_urls"]["data"] = data

        # Format data for list_bad_behavior_history
        ret["list_bad_behavior_history"]["data"] = increments_data

    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get badbehavior metrics: {e}")
        ret["error"] = str(e)

    return ret


def badbehavior(**kwargs):
    pass
