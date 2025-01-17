from logging import getLogger
from traceback import format_exc


def pre_render(**kwargs):
    logger = getLogger("UI")
    ret = {
        "ping_status": {
            "title": "BUNKERNET STATUS",
            "value": "error",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "info_instance_id": {
            "value": "Unknown",
            "title": "Instance ID",
            "subtitle_color": "primary",
            "svg_color": "primary",
            "col-size": "col-12 col-md-8",
            "card-classes": "h-100",
        },
        "list_bunkernet_ips": {
            "data": {},
            "types": {0: "ip-address"},
            "svg_color": "primary",
            "col-size": "col-12",
        },
    }
    try:
        ping_data = kwargs["bw_instances_utils"].get_ping("bunkernet")
        ret["ping_status"]["value"] = ping_data["status"]

        instance_id = kwargs["db"].get_job_cache_file("bunkernet-register", "instance.id")
        if instance_id:
            ret["info_instance_id"]["value"] = instance_id.decode("utf-8")

            ips_file = kwargs["db"].get_job_cache_file("bunkernet-data", "ip.list")
            logger.debug(f"IPs file: {ips_file}")
            if ips_file:
                ips_file = ips_file.decode("utf-8")
                for ip in ips_file.split("\n"):
                    if "ip" not in ret["list_bunkernet_ips"]["data"]:
                        ret["list_bunkernet_ips"]["data"]["ip"] = []
                    ret["list_bunkernet_ips"]["data"]["ip"].append(ip)
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get bunkernet metrics: {e}")
        ret["error"] = str(e)

    return ret


def bunkernet(**kwargs):
    pass
