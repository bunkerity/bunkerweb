from logging import getLogger
from os import getenv
from traceback import format_exc


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def pre_render(**kwargs):
    # Prepare country metrics data for UI rendering with error handling and
    # debug logging support
    logger = getLogger("UI")
    debug_log(logger, "Starting pre_render for country plugin")
    
    ret = {
        "counter_failed_country": {
            "value": 0,
            "title": "Country",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    
    try:
        debug_log(logger, "Retrieving country metrics from bw_instances_utils")
        metrics = kwargs["bw_instances_utils"].get_metrics("country")
        counter_value = metrics.get("counter_failed_country", 0)
        ret["counter_failed_country"]["value"] = counter_value
        debug_log(logger, f"Successfully retrieved counter value: {counter_value}")
        
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get country metrics: {e}")
        debug_log(logger, f"Exception occurred while getting metrics: {str(e)}")
        ret["counter_failed_country"]["error"] = str(e)

    debug_log(logger, f"Returning metrics data: {ret}")
    return ret


def country(**kwargs):
    # Placeholder function for country-specific operations that may be
    # implemented in the future
    pass