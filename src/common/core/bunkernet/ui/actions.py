from traceback import format_exc


def pre_render(**kwargs):
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("bunkernet")
        return {"ping_status": {"title": "BUNKERNET STATUS", "value": ping_data["status"]}}
    except BaseException:
        print(format_exc(), flush=True)
        return {"ping_status": {"title": "BUNKERNET STATUS", "value": "error"}, "error": format_exc()}


def bunkernet(**kwargs):
    pass
