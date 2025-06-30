from json import loads
from logging import getLogger
from os import getenv
from traceback import format_exc

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "").lower() == "debug"


def pre_render(**kwargs):
    # Prepare backup metrics and file list for UI rendering
    logger = getLogger("UI")
    
    if DEBUG_MODE:
        logger.debug("Starting pre_render function for backup plugin")
        logger.debug(f"Received kwargs keys: {list(kwargs.keys())}")
    
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
        
        if DEBUG_MODE:
            logger.debug(f"backup_file content: {backup_file}")
        
        # Parse backup data from cache
        data = loads(backup_file or "{}")
        
        if DEBUG_MODE:
            logger.debug(f"Parsed backup data: {data}")

        # Populate backup file list for UI display
        backup_files = data.get("files", [])
        
        if DEBUG_MODE:
            logger.debug(f"Found {len(backup_files)} backup files")
        
        for backup_file_name in backup_files:
            if "file name" not in ret["list_backup_files"]["data"]:
                ret["list_backup_files"]["data"]["file name"] = []
            ret["list_backup_files"]["data"]["file name"].append(backup_file_name)

        # Set last backup date if available
        if data.get("date"):
            ret["date_last_backup"]["value"] = data["date"]
            
            if DEBUG_MODE:
                logger.debug(f"Last backup date: {data['date']}")
        
        if DEBUG_MODE:
            logger.debug("pre_render completed successfully")
            logger.debug(f"Return data structure: {ret}")
            
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get backup metrics: {e}")
        ret["error"] = str(e)
        
        if DEBUG_MODE:
            logger.debug(f"Exception in pre_render: {type(e).__name__}")
            logger.debug(f"Exception details: {str(e)}")

    return ret


def backup(**kwargs):
    # Handle backup-related UI actions (placeholder for future implementation)
    logger = getLogger("UI")
    
    if DEBUG_MODE:
        logger.debug("backup function called")
        logger.debug(f"Received kwargs keys: {list(kwargs.keys())}")
    
    # This function is currently a placeholder for backup UI actions
    # Future implementations might include manual backup triggers,
    # backup configuration updates, or other interactive features
    
    pass