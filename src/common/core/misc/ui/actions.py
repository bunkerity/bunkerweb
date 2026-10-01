from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_default": {
            "value": 0,
            "title": "DEFAULT SERVER DISABLED",
            "title_i18n": "widgets.counter_failed_default.title",
            "subtitle": "Total",
            "subtitle_i18n": "widgets.counter_failed_default.subtitle",
            "subtitle_color": "danger-emphasis",
            "svg_color": "danger-emphasis",
        },
        "counter_failed_method": {
            "value": 0,
            "title": "DISALLOWED METHODS",
            "title_i18n": "widgets.counter_failed_method.title",
            "subtitle": "Count",
            "subtitle_i18n": "widgets.counter_failed_method.subtitle",
            "subtitle_color": "olive",
            "svg_color": "olive",
        },
    }
    try:
        data = kwargs["bw_instances_utils"].get_metrics("misc")
        ret["counter_failed_default"]["value"] = data.get("counter_failed_default", 0)
        ret["counter_failed_method"]["value"] = data.get("counter_failed_method", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get default metrics: {e}")
        ret["error"] = str(e)

    return ret


def misc(**kwargs):
    pass
