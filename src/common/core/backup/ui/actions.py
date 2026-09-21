from json import loads
from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
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
        backup_file = kwargs["api_client"].get_cache_file_or_none(None, "backup", "backup-data", "backup.json", download=True)
        logger.debug(f"backup_file: {backup_file}")

        data = loads(backup_file or "{}")

        for backup_file in data.get("files", []):
            if "file name" not in ret["list_backup_files"]["data"]:
                ret["list_backup_files"]["data"]["file name"] = []
            ret["list_backup_files"]["data"]["file name"].append(backup_file)

        if data.get("date"):
            ret["date_last_backup"]["value"] = data["date"]
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get backup metrics: {e}")
        ret["error"] = str(e)

    return ret


def backup(**kwargs):
    pass
