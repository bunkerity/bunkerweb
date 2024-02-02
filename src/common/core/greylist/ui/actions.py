def greylist(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("greylist")

        if data.get("counter_failed_greylist") is None:
            data["counter_failed_greylist"] = 0

        return data

    except:
        return {"counter_failed_greylist": 0}
