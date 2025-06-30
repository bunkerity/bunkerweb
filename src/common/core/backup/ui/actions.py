from json import loads
from logging import getLogger
from os import getenv
from traceback import format_exc


def debug_log(logger, message):
    # Log debug messages only when LOG_LEVEL environment variable is set to
    # "debug"
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


def pre_render(**kwargs):
    # Prepare backup metrics and file list for UI rendering
    logger = getLogger("UI")
    
    debug_log(logger, "Starting pre_render function for backup plugin")
    debug_log(logger, f"Received kwargs keys: {list(kwargs.keys())}")
    
    # Initialize return structure with default values
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
        # Retrieve backup cache file from database
        backup_file = kwargs["db"].get_job_cache_file("backup-data", "backup.json")
        
        debug_log(logger, f"backup_file content: {backup_file}")
        
        # Parse backup data from cache
        data = loads(backup_file or "{}")
        
        debug_log(logger, f"Parsed backup data: {data}")

        # Populate backup file list for UI display
        backup_files = data.get("files", [])
        
        debug_log(logger, f"Found {len(backup_files)} backup files")
        
        for backup_file_name in backup_files:
            if "file name" not in ret["list_backup_files"]["data"]:
                ret["list_backup_files"]["data"]["file name"] = []
            ret["list_backup_files"]["data"]["file name"].append(backup_file_name)

        # Set last backup date if available
        if data.get("date"):
            ret["date_last_backup"]["value"] = data["date"]
            
            debug_log(logger, f"Last backup date: {data['date']}")
        
        debug_log(logger, "pre_render completed successfully")
        debug_log(logger, f"Return data structure: {ret}")
            
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get backup metrics: {e}")
        ret["error"] = str(e)
        
        debug_log(logger, f"Exception in pre_render: {type(e).__name__}")
        debug_log(logger, f"Exception details: {str(e)}")

    return ret


def backup(**kwargs):
    # Handle backup-related UI actions (placeholder for future implementation)
    logger = getLogger("UI")
    
    debug_log(logger, "backup function called")
    debug_log(logger, f"Received kwargs keys: {list(kwargs.keys())}")
    
    # This function is currently a placeholder for backup UI actions
    # Future implementations might include manual backup triggers,
    # backup configuration updates, or other interactive features
    
    pass