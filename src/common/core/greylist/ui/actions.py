from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_greylist": {
            "value": 0,
            "title": "GREYLIST",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        ret["counter_failed_greylist"]["value"] = kwargs["bw_instances_utils"].get_metrics("greylist").get("counter_failed_greylist", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get greylist metrics: {e}")
        ret["error"] = str(e)

    return ret


def greylist(**kwargs):
    pass
