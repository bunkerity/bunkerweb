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
    title="crowdsec",
    log_file_path="/var/log/bunkerweb/crowdsec.log"
)

logger.debug("Debug mode enabled for crowdsec")


# Retrieves crowdsec ping status and prepares data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for crowdsec module")
    ret = {
        "ping_status": {
            "title": "CROWDSEC STATUS",
            "value": "error",
            "col-size": "col-12 col-md-6",
            "card-classes": "h-100",
        },
    }
    try:
        logger.debug("Getting crowdsec ping status")
        ping_data = kwargs["bw_instances_utils"].get_ping("crowdsec")
        ret["ping_status"]["value"] = ping_data["status"]
        logger.debug(f"Crowdsec ping status: {ping_data['status']}")
    except BaseException as e:
        logger.exception("Exception while getting crowdsec ping")
        ret["error"] = str(e)

    if "error" in ret:
        logger.debug("Returning early due to error")
        return ret

    return ret


# Placeholder function for crowdsec-specific operations.
def crowdsec(**kwargs):
    logger.debug("crowdsec() called")
    pass
