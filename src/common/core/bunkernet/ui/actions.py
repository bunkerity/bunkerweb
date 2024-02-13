def bunkernet(**kwargs):
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("bunkernet")
        return {"ping_status": ping_data["status"]}
    except:
        return {"ping_status": "error"}
