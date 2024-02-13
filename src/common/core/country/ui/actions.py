def country(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("country")

        if data.get("counter_failed_country") is None:
            data["counter_failed_country"] = 0

        return data

    except:
        return {"counter_failed_country": 0}
