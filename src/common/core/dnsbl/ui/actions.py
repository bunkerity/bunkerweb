from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="dnsbl",
    log_file_path="/var/log/bunkerweb/dnsbl.log"
)

logger.debug("Debug mode enabled for dnsbl")


# Retrieves DNSBL metrics and prepares counter data for UI display.
# Processes DNS blacklist blocking statistics for security monitoring.
def pre_render(**kwargs):
    logger.debug("pre_render() called for dnsbl module")
    logger.debug(f"pre_render() received {len(kwargs)} keyword arguments")
    
    ret = {
        "counter_failed_dnsbl": {
            "value": 0,
            "title": "DNSBL",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    logger.debug("Initialized DNSBL counter structure with default values")
    
    try:
        # Validate required dependencies are available
        if "bw_instances_utils" not in kwargs:
            logger.error("bw_instances_utils not found in kwargs")
            ret["error"] = "Missing bw_instances_utils dependency"
            return ret
            
        logger.debug("Getting dnsbl metrics from bw_instances_utils")
        bw_utils = kwargs["bw_instances_utils"]
        logger.debug(f"bw_instances_utils type: {type(bw_utils)}")
        
        # Retrieve DNSBL-specific metrics from instances
        metrics = bw_utils.get_metrics("dnsbl")
        logger.debug(f"Retrieved DNSBL metrics: {metrics}")
        logger.debug(f"Metrics type: {type(metrics)}, keys: {list(metrics.keys()) if isinstance(metrics, dict) else 'N/A'}")
        
        # Extract and validate the failed DNSBL counter
        dnsbl_value = metrics.get("counter_failed_dnsbl", 0)
        logger.debug(f"Extracted counter_failed_dnsbl: {dnsbl_value} (type: {type(dnsbl_value)})")
        
        # Ensure the value is numeric and non-negative
        if isinstance(dnsbl_value, (int, float)) and dnsbl_value >= 0:
            ret["counter_failed_dnsbl"]["value"] = int(dnsbl_value)
            logger.debug(f"Set counter_failed_dnsbl value to: {ret['counter_failed_dnsbl']['value']}")
        else:
            logger.warning(f"Invalid counter_failed_dnsbl value: {dnsbl_value}, using default 0")
            ret["counter_failed_dnsbl"]["value"] = 0
            
    except KeyError as e:
        logger.exception(f"KeyError while accessing DNSBL metrics: {e}")
        ret["error"] = f"Missing metric key: {e}"
    except AttributeError as e:
        logger.exception(f"AttributeError while calling get_metrics: {e}")
        ret["error"] = f"Invalid bw_instances_utils object: {e}"
    except BaseException as e:
        logger.exception("Unexpected exception while getting dnsbl metrics")
        ret["error"] = str(e)

    logger.debug(f"pre_render() completed, DNSBL counter: {ret['counter_failed_dnsbl']['value']}")
    return ret


# Placeholder function for dnsbl-specific operations and DNS blacklist processing.
# Currently implements no functionality but maintains interface compatibility
# for future DNSBL feature implementations and DNS security enhancements.
def dnsbl(**kwargs):
    logger.debug("dnsbl() called - currently no implementation")
    logger.debug(f"dnsbl() received {len(kwargs)} keyword arguments: {list(kwargs.keys()) if kwargs else 'none'}")
    
    # Log available parameters for future development reference
    if kwargs:
        for key, value in kwargs.items():
            logger.debug(f"dnsbl() parameter '{key}': type={type(value)}")
    
    logger.debug("dnsbl() completed - no operations performed")
    pass
