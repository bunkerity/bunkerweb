def redis(**kwargs):
    ping = {}
    data = {}
    try:
        ping_data = kwargs["app"].config["INSTANCES"].get_ping("redis")
        ping = {"ping_status": ping_data["status"]}
    except:
        ping = {"ping_status": "error"}

    try:
        metrics = kwargs["app"].config["INSTANCES"].get_metrics("redis")

        if metrics.get("redis_nb_keys") is None:
            metrics["redis_nb_keys"] = 0

        data = metrics
    except:
        data = {"redis_nb_keys": 0}

    return ping | data
