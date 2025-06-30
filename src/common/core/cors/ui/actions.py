import os
from os import getenv
from logging import getLogger
from traceback import format_exc


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def pre_render(**kwargs):
    # Prepare and collect UI metrics data for CORS plugin dashboard display.
    # This function aggregates statistics from BunkerWeb instances to show
    # blocked CORS requests and other relevant metrics in the web interface.
    # Returns a dictionary structure compatible with the UI rendering system.
    
    logger = getLogger("UI")
    
    debug_log(logger, "CORS pre_render: Starting metrics collection process")
    debug_log(logger, f"CORS pre_render: kwargs keys: "
              f"{list(kwargs.keys()) if kwargs else 'None'}")
    
    # Initialize default return structure with zero values
    ret = {
        "counter_failed_cors": {
            "value": 0,
            "title": "CORS",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    
    debug_log(logger, "CORS pre_render: Initialized default return structure")
    
    try:
        debug_log(logger, "CORS pre_render: Attempting to access "
                  "bw_instances_utils")
            
        # Check if required utilities are available
        if "bw_instances_utils" not in kwargs:
            raise KeyError("bw_instances_utils not found in kwargs")
            
        bw_utils = kwargs["bw_instances_utils"]
        
        debug_log(logger, "CORS pre_render: Successfully accessed "
                  "bw_instances_utils, getting metrics")
        
        # Retrieve metrics from BunkerWeb instances
        metrics = bw_utils.get_metrics("cors")
        
        debug_log(logger, f"CORS pre_render: Raw metrics received: {metrics}")
        debug_log(logger, f"CORS pre_render: Metrics type: {type(metrics)}")
        
        # Extract and validate counter value
        failed_cors_count = metrics.get("counter_failed_cors", 0)
        
        debug_log(logger, f"CORS pre_render: Extracted failed_cors count: "
                  f"{failed_cors_count} (type: {type(failed_cors_count)})")
        
        # Ensure the value is numeric
        if not isinstance(failed_cors_count, (int, float)):
            logger.warning(f"CORS pre_render: Non-numeric failed_cors "
                          f"count: {failed_cors_count}, defaulting to 0")
            failed_cors_count = 0
            
        ret["counter_failed_cors"]["value"] = int(failed_cors_count)
        
        debug_log(logger, f"CORS pre_render: Successfully set counter value "
                  f"to {ret['counter_failed_cors']['value']}")
            
    except KeyError as e:
        error_msg = f"Missing required parameter: {e}"
        debug_log(logger, f"CORS pre_render: KeyError - {error_msg}")
        debug_log(logger, f"CORS pre_render: Available kwargs: "
                  f"{list(kwargs.keys()) if kwargs else 'None'}")
        
        logger.error(f"Failed to get cors metrics: {error_msg}")
        ret["error_info"] = {
            "message": error_msg,
            "type": "parameter_missing"
        }
        
    except AttributeError as e:
        error_msg = f"Method not available: {e}"
        debug_log(logger, f"CORS pre_render: AttributeError - {error_msg}")
        debug_log(logger, f"CORS pre_render: bw_instances_utils methods: "
                  f"{dir(kwargs.get('bw_instances_utils', {}))}")
        
        logger.error(f"Failed to get cors metrics: {error_msg}")
        ret["error_info"] = {
            "message": error_msg,
            "type": "method_unavailable"
        }
        
    except BaseException as e:
        error_msg = str(e)
        debug_log(logger, f"CORS pre_render: Unexpected exception occurred")
        debug_log(logger, f"CORS pre_render: Exception type: {type(e)}")
        debug_log(logger, f"CORS pre_render: Full traceback: {format_exc()}")
        
        logger.error(f"Failed to get cors metrics: {error_msg}")
        ret["error_info"] = {
            "message": error_msg,
            "type": "unexpected_error"
        }

    debug_log(logger, f"CORS pre_render: Final return data structure: {ret}")
    debug_log(logger, "CORS pre_render: Metrics collection completed")

    return ret


def cors(**kwargs):
    # Handle CORS-specific UI actions and user interactions from web interface.
    # This function serves as an entry point for CORS configuration changes,
    # status updates, or other administrative actions triggered through the UI.
    # Currently serves as a placeholder for future CORS management features.
    
    logger = getLogger("UI")
    
    debug_log(logger, "CORS action: Function called for UI interaction")
    debug_log(logger, f"CORS action: Received kwargs keys: "
              f"{list(kwargs.keys()) if kwargs else 'None'}")
        
    # Log all provided parameters for debugging
    for key, value in (kwargs or {}).items():
        debug_log(logger, f"CORS action: Parameter {key} = "
                  f"{value} (type: {type(value)})")
    
    # Placeholder for future CORS management functionality
    # This could include:
    # - Updating CORS configuration
    # - Triggering policy reloads
    # - Managing origin whitelist/blacklist
    # - Generating CORS reports
    
    debug_log(logger, "CORS action: No action implemented, function complete")
    
    pass