from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_default": {
            "value": 0,
            "title": "DEFAULT SERVER DISABLED",
            "subtitle": "Total",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
        "counter_failed_method": {
            "value": 0,
            "title": "DISALLOWED METHODS",
            "subtitle": "Count",
            "subtitle_color": "olive",
            "svg_color": "olive",
        },
        "counter_failed_content_type": {
            "value": 0,
            "title": "DISALLOWED CONTENT TYPES",
            "subtitle": "Count",
            "subtitle_color": "purple",
            "svg_color": "purple",
        },
    }
    try:
        data = kwargs["bw_instances_utils"].get_metrics("misc")
        ret["counter_failed_default"]["value"] = data.get("counter_failed_default", 0)
        ret["counter_failed_method"]["value"] = data.get("counter_failed_method", 0)
        ret["counter_failed_content_type"]["value"] = data.get("counter_failed_content_type", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get default metrics: {e}")
        ret["error"] = str(e)

    return ret


def misc(**kwargs):
    pass
