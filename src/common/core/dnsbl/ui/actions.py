from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_dnsbl": {
            "value": 0,
            "title": "DNSBL",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        ret["counter_failed_dnsbl"]["value"] = kwargs["bw_instances_utils"].get_metrics("dnsbl").get("counter_failed_dnsbl", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get dnsbl metrics: {e}")
        ret["error"] = str(e)

    return ret


def dnsbl(**kwargs):
    pass
