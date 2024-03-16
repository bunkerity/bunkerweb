def pre_render(**kwargs):
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("bunkernet")
        return {"ping_status": {"title": "BUNKERNET STATUS", "value": ping_data["status"]}}
    except:
        return {"ping_status": {"title": "BUNKERNET STATUS", "value": "error"}}


def bunkernet(**kwargs):
    pass
