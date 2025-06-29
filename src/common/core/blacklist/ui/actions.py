from logging import getLogger
from os import getenv
from traceback import format_exc


def pre_render(**kwargs):
    # Prepare data for rendering blacklist metrics in the UI.
    # Args:
    #   **kwargs: Keyword arguments containing bw_instances_utils for 
    #            getting metrics data
    # Returns:
    #   Dictionary containing formatted counter data for UI display
    logger = getLogger("UI")
    ret = {
        "counter_failed_url": {
            "value": 0,
            "title": "URL",
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
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"Blacklist metrics: {data}")
        for key in data:
            if key in ret:
                ret[key]["value"] = data.get(key, 0)
    except BaseException as e:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(format_exc())
        logger.error(f"Failed to get blacklist metrics: {e}")
        # Store error message in a separate field with proper structure
        ret["error_info"] = {
            "value": 0,
            "title": "Error",
            "subtitle": str(e),
            "subtitle_color": "error",
            "svg_color": "danger",
        }

    return ret


def blacklist(**kwargs):
    # Handle blacklist-specific actions in the UI.
    # Args:
    #   **kwargs: Keyword arguments for blacklist action handling
    # Returns:
    #   None - placeholder function for future blacklist actions
    pass