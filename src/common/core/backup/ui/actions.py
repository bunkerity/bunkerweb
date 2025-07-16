from json import loads
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
    title="backup-actions",
    log_file_path="/var/log/bunkerweb/backup.log"
)

logger.debug("Debug mode enabled for backup")


# Retrieves backup metrics and prepares data for UI display.
def pre_render(**kwargs):
    logger.debug("pre_render() called for backup module")
    ret = {
        "date_last_backup": {
            "value": "N/A",
            "title": "Last Backup",
            "subtitle_color": "primary",
            "svg_color": "primary",
        },
        "list_backup_files": {
            "data": {},
            "svg_color": "primary",
        },
    }
    try:
        backup_file = kwargs["db"].get_job_cache_file("backup-data", "backup.json")
        logger.debug(f"backup_file: {backup_file}")

        data = loads(backup_file or "{}")
        logger.debug(f"Parsed backup data: {data}")

        for backup_file in data.get("files", []):
            if "file name" not in ret["list_backup_files"]["data"]:
                ret["list_backup_files"]["data"]["file name"] = []
            ret["list_backup_files"]["data"]["file name"].append(backup_file)

        if data.get("date"):
            ret["date_last_backup"]["value"] = data["date"]
            logger.debug(f"Set last backup date: {data['date']}")
            
    except BaseException as e:
        logger.exception("Exception while getting backup metrics")
        ret["error"] = str(e)

    logger.debug(f"pre_render() returning: {ret}")
    return ret


# Placeholder function for backup-specific operations.
def backup(**kwargs):
    logger.debug("backup() called")
    pass
