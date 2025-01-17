from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_cors": {
            "value": 0,
            "title": "CORS",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        ret["counter_failed_cors"]["value"] = kwargs["bw_instances_utils"].get_metrics("cors").get("counter_failed_cors", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get cors metrics: {e}")
        ret["error"] = str(e)

    return ret


def cors(**kwargs):
    pass
