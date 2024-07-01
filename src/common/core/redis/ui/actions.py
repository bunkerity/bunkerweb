from traceback import format_exc


def pre_render(**kwargs):
    ping = {}
    data = {}
    error = ""
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("redis")
        ping = {"ping_status": {"title": "REDIS STATUS", "value": ping_data["status"]}}
    except BaseException:
        print(format_exc(), flush=True)
        error = format_exc()
        ping = {"ping_status": {"title": "REDIS STATUS", "value": "error"}}

    try:
        metrics = kwargs["app"].config["INSTANCES"].get_metrics("redis")
        data = {
            "counter_redis_nb_keys": {
                "value": metrics.get("redis_nb_keys", 0),
                "title": "REDIS KEYS",
                "subtitle": "total number",
                "subtitle_color": "info",
                "svg_color": "sky",
            }
        }

    except BaseException:
        print(format_exc(), flush=True)
        error += format_exc()
        data = {"counter_redis_nb_keys": {"value": "unknown", "title": "REDIS KEYS", "subtitle": "total number", "subtitle_color": "info", "svg_color": "sky"}}

    if error:
        return ping | data | {"error": error}

    return ping | data


def redis(**kwargs):
    pass
