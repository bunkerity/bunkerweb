def cors(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("cors")

        if data.get("counter_failed_cors") is None:
            data["counter_failed_cors"] = 0

        return data

    except:
        return {"counter_failed_cors": 0}
