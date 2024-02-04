def misc(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("misc")

        if "counter_failed_default" not in data:
            data["counter_failed_default"] = 0

        if "counter_failed_method" not in data:
            data["counter_failed_method"] = 0

        return data

    except:
        return {"counter_failed_default": 0, "counter_failed_method": 0}
