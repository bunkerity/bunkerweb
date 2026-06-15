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
        "info_connectivity": {
            "value": "Unknown",
            "description": "",
            "title": "Connectivity",
            "subtitle_color": "primary",
            "svg_color": "primary",
            "col-size": "col-12 col-md-4",
            "card-classes": "h-100",
        },
        "info_instance_id": {
            "value": "Unknown",
            "title": "Instance ID",
            "subtitle_color": "primary",
            "svg_color": "primary",
            "col-size": "col-12 col-md-4",
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
        status = ping_data.get("status", "error")
        ret["ping_status"]["value"] = status

        # The ping is a *live* connectivity check from the BunkerWeb instance to
        # the BunkerNet API; "Inactive" does not mean USE_BUNKERNET is off. Cross
        # check the registration cache so the page tells apart "not registered"
        # from "registered but the API is unreachable".
        ping_msg = ping_data.get("msg", "") or ""
        instance_id = kwargs["db"].get_job_cache_file("bunkernet-register", "instance.id")
        if instance_id:
            instance_id = instance_id.decode("utf-8")
            ret["info_instance_id"]["value"] = instance_id
            # The instance ID authenticates this instance against the BunkerNet
            # API, so mask it by default to avoid leaking it in screenshots.
            ret["info_instance_id"]["secret"] = True

            # The ping message embeds the instance ID (e.g. "... using instance ID
            # <id> is successful"); redact it so the reason can be shown without
            # leaking the ID we just masked.
            if status == "success":
                ret["info_connectivity"]["value"] = "Connected"
                ret["info_connectivity"]["svg_color"] = "success"
            else:
                ret["info_connectivity"]["value"] = "API unreachable"
                ret["info_connectivity"]["svg_color"] = "warning"
            ret["info_connectivity"]["description"] = ping_msg.replace(instance_id, "***") if ping_msg else ""

            ips_file = kwargs["db"].get_job_cache_file("bunkernet-data", "ip.list")
            logger.debug(f"IPs file: {ips_file}")
            if ips_file:
                ips_file = ips_file.decode("utf-8")
                for ip in ips_file.split("\n"):
                    if "ip" not in ret["list_bunkernet_ips"]["data"]:
                        ret["list_bunkernet_ips"]["data"]["ip"] = []
                    ret["list_bunkernet_ips"]["data"]["ip"].append(ip)
        else:
            ret["info_connectivity"]["value"] = "Not registered yet"
            ret["info_connectivity"]["svg_color"] = "warning"
            ret["info_connectivity"]["description"] = ping_msg or "No BunkerNet instance ID yet; registration runs hourly."
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get bunkernet metrics: {e}")
        ret["error"] = str(e)

    return ret


def bunkernet(**kwargs):
    pass
