from operator import itemgetter
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
    title="errors",
    log_file_path="/var/log/bunkerweb/errors.log"
)

logger.debug("Debug mode enabled for errors")


# Retrieves error metrics and prepares data for UI display.
# Processes error code statistics and formats them for visualization.
def pre_render(**kwargs):
    logger.debug("pre_render() called for errors module")
    logger.debug(f"pre_render() received {len(kwargs)} keyword arguments")
    
    ret = {
        "top_errors": {
            "data": {},
            "order": {
                "column": 1,
                "dir": "desc",
            },
            "svg_color": "danger",
        },
    }
    logger.debug("Initialized errors data structure with default values")
    
    try:
        # Validate required dependencies are available
        if "bw_instances_utils" not in kwargs:
            logger.error("bw_instances_utils not found in kwargs")
            ret["error"] = "Missing bw_instances_utils dependency"
            return ret
            
        logger.debug("Getting error metrics from bw_instances_utils")
        bw_utils = kwargs["bw_instances_utils"]
        logger.debug(f"bw_instances_utils type: {type(bw_utils)}")
        
        # Retrieve error-specific metrics from instances
        metrics = bw_utils.get_metrics("errors")
        logger.debug(f"Retrieved error metrics: {metrics}")
        logger.debug(f"Metrics type: {type(metrics)}, keys: {list(metrics.keys()) if isinstance(metrics, dict) else 'N/A'}")
        logger.debug(f"Found {len(metrics)} error metric entries")
        
        # Format data for error code visualization
        logger.debug("Processing error code metrics")
        format_data = [
            {
                "code": int(key.split("_")[1]),
                "count": int(value),
            }
            for key, value in metrics.items()
        ]
        logger.debug(f"Extracted {len(format_data)} error code entries")
        
        # Sort by count in descending order
        format_data.sort(key=itemgetter("count"), reverse=True)
        logger.debug("Sorted error data by count (descending)")
        
        # Create formatted data structure for UI
        data = {"code": [], "count": []}
        for item in format_data:
            data["code"].append(item["code"])
            data["count"].append(item["count"])
            
        ret["top_errors"]["data"] = data
        logger.debug(f"Processed {len(data['code'])} error codes for display")
        
        # Log top error codes for monitoring
        if format_data:
            top_errors = format_data[:5]  # Show top 5 for debugging
            logger.debug(f"Top error codes: {[(item['code'], item['count']) for item in top_errors]}")
        
    except KeyError as e:
        logger.exception(f"KeyError while accessing error metrics: {e}")
        ret["error"] = f"Missing metric key: {e}"
    except ValueError as e:
        logger.exception(f"ValueError while parsing error metrics: {e}")
        ret["error"] = f"Invalid metric format: {e}"
    except AttributeError as e:
        logger.exception(f"AttributeError while calling get_metrics: {e}")
        ret["error"] = f"Invalid bw_instances_utils object: {e}"
    except BaseException as e:
        logger.exception("Unexpected exception while getting error metrics")
        ret["error"] = str(e)

    error_count = len(ret.get("top_errors", {}).get("data", {}).get("code", []))
    logger.debug(f"pre_render() completed, returning {error_count} error codes")
    return ret


# Placeholder function for errors-specific operations and error handling processing.
# Currently implements no functionality but maintains interface compatibility
# for future error management features and monitoring enhancements.
def errors(**kwargs):
    logger.debug("errors() called - currently no implementation")
    logger.debug(f"errors() received {len(kwargs)} keyword arguments: {list(kwargs.keys()) if kwargs else 'none'}")
    
    # Log available parameters for future development reference
    if kwargs:
        for key, value in kwargs.items():
            logger.debug(f"errors() parameter '{key}': type={type(value)}")
    
    logger.debug("errors() completed - no operations performed")
    pass
