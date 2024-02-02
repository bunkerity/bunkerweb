def antibot(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("antibot")

        if data.get("counter_failed_challenges") is None:
            data["counter_failed_challenges"] = 0

        return data

    except:
        return {"counter_failed_challenges": 0}
