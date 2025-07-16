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
    title="country",
    log_file_path="/var/log/bunkerweb/country.log"
)

logger.debug("Debug mode enabled for country")


# Retrieves country metrics and prepares counter data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for country module")
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
        logger.debug("Getting country metrics")
        ret["counter_failed_country"]["value"] = kwargs["bw_instances_utils"].get_metrics("country").get("counter_failed_country", 0)
        logger.debug(f"Country counter value: {ret['counter_failed_country']['value']}")
    except BaseException as e:
        logger.exception("Exception while getting country metrics")
        ret["error"] = str(e)

    return ret


# Placeholder function for country-specific operations.
def country(**kwargs):
    logger.debug("country() called")
    pass
