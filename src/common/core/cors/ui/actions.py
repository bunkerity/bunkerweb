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
    title="cors",
    log_file_path="/var/log/bunkerweb/cors.log"
)

logger.debug("Debug mode enabled for cors")


# Retrieves CORS metrics and prepares counter data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for cors module")
    ret = {
        "counter_failed_cors": {
            "value": 0,
            "title": "CORS",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        logger.debug("Getting cors metrics")
        ret["counter_failed_cors"]["value"] = kwargs["bw_instances_utils"].get_metrics("cors").get("counter_failed_cors", 0)
        logger.debug(f"CORS counter value: {ret['counter_failed_cors']['value']}")
    except BaseException as e:
        logger.exception("Exception while getting cors metrics")
        ret["error"] = str(e)

    return ret


# Placeholder function for cors-specific operations.
def cors(**kwargs):
    logger.debug("cors() called")
    pass
