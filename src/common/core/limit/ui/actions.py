from logging import getLogger
from operator import itemgetter
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "top_limit": {
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "amber",
        },
    }
    try:
        format_data = [
            {"URL": f"/{key.split('/', 1)[1] if '/' in key else ''}", "count": int(value)}
            for key, value in kwargs["bw_instances_utils"].get_metrics("limit").items()
        ]
        format_data.sort(key=itemgetter("count"), reverse=True)
        data = {"URL": [], "count": []}
        for item in format_data:
            data["URL"].append(item["URL"])
            data["count"].append(item["count"])
        ret["top_limit"]["data"] = data
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get limit metrics: {e}")
        ret["error"] = str(e)

    return ret


def limit(**kwargs):
    pass
