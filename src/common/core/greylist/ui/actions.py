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
    title="greylist",
    log_file_path="/var/log/bunkerweb/greylist.log"
)

logger.debug("Debug mode enabled for greylist")


# Retrieves greylist metrics and prepares counter data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for greylist module")
    ret = {
        "counter_failed_greylist": {
            "value": 0,
            "title": "GREYLIST",
            "subtitle": "Request blocked",
            "subtitle_color": "danger",
            "svg_color": "danger",
        },
    }
    try:
        logger.debug("Getting greylist metrics")
        ret["counter_failed_greylist"]["value"] = kwargs["bw_instances_utils"].get_metrics("greylist").get("counter_failed_greylist", 0)
        logger.debug(f"Greylist counter value: {ret['counter_failed_greylist']['value']}")
    except BaseException as e:
        logger.exception("Exception while getting greylist metrics")
        ret["error"] = str(e)

    return ret


# Placeholder function for greylist-specific operations.
def greylist(**kwargs):
    logger.debug("greylist() called")
    pass
