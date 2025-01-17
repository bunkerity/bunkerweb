from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_passed_whitelist": {
            "value": 0,
            "title": "WHITELIST",
            "subtitle": "Request passed",
            "subtitle_color": "success",
            "svg_color": "emerald",
        },
    }
    try:
        ret["counter_passed_whitelist"]["value"] = kwargs["bw_instances_utils"].get_metrics("whitelist").get("counter_passed_whitelist", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get whitelist metrics: {e}")
        ret["error"] = str(e)

    return ret


def whitelist(**kwargs):
    pass
