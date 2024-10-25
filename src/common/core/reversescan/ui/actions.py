from logging import getLogger
from operator import itemgetter
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "top_reverse_scan": {
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "danger",
        },
    }
    try:
        format_data = [
            {
                "port": int(key.split("_")[-1]),
                "count": int(value),
            }
            for key, value in kwargs["bw_instances_utils"].get_metrics("reversescan").items()
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"port": [], "count": []}
        for item in format_data:
            data["port"].append(item["port"])
            data["count"].append(item["count"])
        ret["top_reverse_scan"]["data"] = data
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get reversescan metrics: {e}")
        ret["error"] = str(e)

    return ret


def reversescan(**kwargs):
    pass
