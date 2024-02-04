def whitelist(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("whitelist")

        if "counter_passed_whitelist" not in data:
            data["counter_passed_whitelist"] = 0

        return data

    except:
        return {"counter_passed_whitelist": 0}
