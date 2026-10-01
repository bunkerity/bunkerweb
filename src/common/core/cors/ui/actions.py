from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_cors": {
            "value": 0,
            "title": "CORS",
            "title_i18n": "widgets.counter_failed_cors.title",
            "subtitle": "Request blocked",
            "subtitle_i18n": "widgets.counter_failed_cors.subtitle",
            "subtitle_color": "danger-emphasis",
            "svg_color": "danger-emphasis",
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
