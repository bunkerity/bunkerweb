from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "counter_failed_uri": {
            "value": 0,
            "title": "URI",
            "subtitle": "Denied",
            "subtitle_color": "error",
            "svg_color": "danger",
        },
        "counter_failed_ip": {
            "value": 0,
            "title": "IP",
            "subtitle": "Denied",
            "subtitle_color": "orange",
            "svg_color": "orange",
        },
        "counter_failed_rdns": {
            "value": 0,
            "title": "RDNS",
            "subtitle": "Denied",
            "subtitle_color": "amber",
            "svg_color": "amber",
        },
        "counter_failed_asn": {
            "value": 0,
            "title": "ASN",
            "subtitle": "Denied",
            "subtitle_color": "olive",
            "svg_color": "olive",
        },
        "counter_failed_ua": {
            "value": 0,
            "title": "UA",
            "subtitle": "Denied",
            "subtitle_color": "purple",
            "svg_color": "purple",
        },
    }

    try:
        data = kwargs["bw_instances_utils"].get_metrics("blacklist")
        logger.debug(f"Blacklist metrics: {data}")
        for key in data:
            ret[key]["value"] = data.get(key, 0)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get blacklist metrics: {e}")
        ret["error"] = str(e)

    return ret


def blacklist(**kwargs):
    pass
