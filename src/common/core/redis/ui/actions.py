def pre_render(**kwargs):
    ping = {}
    data = {}
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("redis")
        ping = {"ping_status": {"title": "REDIS STATUS", "value": ping_data["status"]}}
    except:
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

    except:
        data = {"counter_redis_nb_keys": {"value": "unknown", "title": "REDIS KEYS", "subtitle": "total number", "subtitle_color": "info", "svg_color": "sky"}}

    return ping | data


def redis(**kwargs):
    pass
