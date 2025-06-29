import os
from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    # Pre-render function to get DNSBL metrics for the UI dashboard.
    # Returns counter information for failed DNSBL requests that were
    # blocked by the plugin.
    logger = getLogger("UI")
    
    # Check for debug logging
    if os.environ.get("LOG_LEVEL") == "debug":
        logger.debug("Starting pre_render for DNSBL plugin")
        logger.debug(f"Received kwargs keys: {list(kwargs.keys())}")
    
    ret = {
        "counter_failed_dnsbl": {
            "value": 0,
            "title": "DNSBL",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    
    try:
        if os.environ.get("LOG_LEVEL") == "debug":
            logger.debug("Attempting to get DNSBL metrics")
            
        metrics = (kwargs["bw_instances_utils"]
                  .get_metrics("dnsbl")
                  .get("counter_failed_dnsbl", 0))
        ret["counter_failed_dnsbl"]["value"] = metrics
        
        if os.environ.get("LOG_LEVEL") == "debug":
            logger.debug(f"Successfully retrieved metrics: {metrics}")
            
    except BaseException as e:
        if os.environ.get("LOG_LEVEL") == "debug":
            logger.debug(format_exc())
        logger.error(f"Failed to get dnsbl metrics: {e}")
        # Error is logged but not added to return dict to maintain type consistency

    if os.environ.get("LOG_LEVEL") == "debug":
        logger.debug(f"Returning pre_render result: {ret}")
        
    return ret


def dnsbl(**kwargs):
    # Main DNSBL action function.
    # Currently serves as a placeholder for future DNSBL-specific
    # actions that may be needed.
    logger = getLogger("UI")
    
    if os.environ.get("LOG_LEVEL") == "debug":
        logger.debug("DNSBL action function called")
        logger.debug(f"Received kwargs: {kwargs}")
    
    pass