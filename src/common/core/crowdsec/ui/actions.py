from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "ping_status": {
            "title": "CROWDSEC STATUS",
            "value": "error",
            "col-size": "col-12 col-md-6",
            "card-classes": "h-100",
        },
    }
    try:
        ping_data = kwargs["bw_instances_utils"].get_ping("crowdsec")
        ret["ping_status"]["value"] = ping_data["status"]
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get crowdsec ping: {e}")
        ret["error"] = str(e)

    if "error" in ret:
        return ret

    return ret


def crowdsec(**kwargs):
    pass
