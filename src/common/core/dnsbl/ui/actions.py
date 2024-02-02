def dnsbl(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("dnsbl")

        if data.get("counter_failed_dnsbl") is None:
            data["counter_failed_dnsbl"] = 0

        return data

    except:
        return {"counter_failed_dnsbl": 0}
