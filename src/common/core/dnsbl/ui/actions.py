from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_dnsbl": {
            "value": 0,
            "title": "DNSBL",
            "title_i18n": "widgets.counter_failed_dnsbl.title",
            "subtitle": "Request blocked",
            "subtitle_i18n": "widgets.counter_failed_dnsbl.subtitle",
            "subtitle_color": "danger-emphasis",
            "svg_color": "danger-emphasis",
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
