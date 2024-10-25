from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_country": {
            "value": 0,
            "title": "Country",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        ret["counter_failed_country"]["value"] = kwargs["bw_instances_utils"].get_metrics("country").get("counter_failed_country", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get country metrics: {e}")
        ret["error"] = str(e)

    return ret


def country(**kwargs):
    pass
