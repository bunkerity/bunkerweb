from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "ping_status": {
            "title": "REDIS STATUS",
            "value": "error",
            "col-size": "col-12 col-md-6",
            "card-classes": "h-100",
        },
        "counter_redis_nb_keys": {
            "value": 0,
            "title": "REDIS KEYS",
            "subtitle": "Keys number",
            "subtitle_color": "maroon",
            "svg_color": "maroon",
            "col-size": "col-12 col-md-6",
            "card-classes": "h-100",
        },
    }
    try:
        ping_data = kwargs["bw_instances_utils"].get_ping("redis")
        ret["ping_status"]["value"] = ping_data["status"]
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get redis ping: {e}")
        ret["error"] = str(e)

    if "error" in ret:
        return ret

    try:
        ret["counter_redis_nb_keys"]["value"] = kwargs["bw_instances_utils"].get_metrics("redis").get("redis_nb_keys", 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get redis metrics: {e}")
        ret["error"] = str(e)

    return ret


def redis(**kwargs):
    pass
