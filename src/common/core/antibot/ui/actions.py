from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_challenges": {
            "value": 0,
            "title": "Challenges",
            "title_i18n": "widgets.counter_failed_challenges.title",
            "subtitle": "Failed",
            "subtitle_i18n": "widgets.counter_failed_challenges.subtitle",
            "subtitle_color": "danger-emphasis",
            "svg_color": "danger-emphasis",
        },
    }
    try:
        ret["counter_failed_challenges"]["value"] = kwargs["bw_instances_utils"].get_metrics("antibot").get("counter_failed_challenges", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get antibot metrics: {e}")
        ret["error"] = str(e)

    return ret


def antibot(**kwargs):
    pass
