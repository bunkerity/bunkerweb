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
    title="blacklist-actions",
    log_file_path="/var/log/bunkerweb/blacklist.log"
)

logger.debug("Debug mode enabled for blacklist")


# Retrieves blacklist metrics and prepares counter data for UI display.
# Processes denied requests by type: URL, IP, RDNS, ASN, and User Agent.
def pre_render(**kwargs):
    logger.debug("pre_render() called for blacklist module")
    logger.debug(f"pre_render() received {len(kwargs)} keyword arguments")
    
    # Initialize default counter structure for blacklist denials
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
    logger.debug(f"Initialized {len(ret)} blacklist counters with default values")

    try:
        # Validate required dependencies are available
        if "bw_instances_utils" not in kwargs:
            logger.error("bw_instances_utils not found in kwargs")
            ret["error"] = "Missing bw_instances_utils dependency"
            return ret
            
        logger.debug("Attempting to get blacklist metrics from bw_instances_utils")
        bw_utils = kwargs["bw_instances_utils"]
        logger.debug(f"bw_instances_utils type: {type(bw_utils)}")
        
        # Retrieve blacklist-specific metrics from the instances
        data = bw_utils.get_metrics("blacklist")
        logger.debug(f"Retrieved blacklist metrics: {data}")
        logger.debug(f"Metrics type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        logger.debug(f"Found {len(data)} metric keys")
        
        # Process each metric and update corresponding counters
        processed_count = 0
        skipped_count = 0
        
        for key in data:
            logger.debug(f"Processing metric key: {key} with value: {data[key]}")
            
            if key in ret:
                # Validate and set the counter value
                metric_value = data.get(key, 0)
                if isinstance(metric_value, (int, float)) and metric_value >= 0:
                    ret[key]["value"] = int(metric_value)
                    logger.debug(f"Set {key} value to: {ret[key]['value']}")
                    processed_count += 1
                else:
                    logger.warning(f"Invalid metric value for {key}: {metric_value}, keeping default 0")
                    ret[key]["value"] = 0
            else:
                logger.debug(f"Skipping unknown metric key: {key}")
                skipped_count += 1
                
        logger.debug(f"Metric processing completed: {processed_count} processed, {skipped_count} skipped")
                
    except KeyError as e:
        logger.exception(f"KeyError while accessing blacklist metrics: {e}")
        ret["error"] = f"Missing metric key: {e}"
    except AttributeError as e:
        logger.exception(f"AttributeError while calling get_metrics: {e}")
        ret["error"] = f"Invalid bw_instances_utils object: {e}"
    except BaseException as e:
        logger.exception("Unexpected exception while getting blacklist metrics")
        ret["error"] = str(e)

    # Log final counter values for verification
    counter_summary = {}
    for key in ret:
        if key != "error" and isinstance(ret[key], dict) and "value" in ret[key]:
            counter_summary[key] = ret[key]["value"]
    
    logger.debug(f"Final counter values: {counter_summary}")
    logger.debug(f"pre_render() completed successfully, returning data for {len(ret)} sections")
    return ret


# Placeholder function for blacklist-specific operations and denial processing.
# Currently implements no functionality but maintains interface compatibility
# for future blacklist feature implementations and security rule processing.
def blacklist(**kwargs):
    logger.debug("blacklist() called - currently no implementation")
    logger.debug(f"blacklist() received {len(kwargs)} keyword arguments: {list(kwargs.keys()) if kwargs else 'none'}")
    
    # Log available parameters for future development reference
    if kwargs:
        for key, value in kwargs.items():
            logger.debug(f"blacklist() parameter '{key}': type={type(value)}")
    
    logger.debug("blacklist() completed - no operations performed")
    pass
