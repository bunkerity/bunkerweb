def blacklist(**kwargs):
    keys = [
        "counter_blacklist_url",
        "counter_blacklist_ip",
        "counter_blacklist_rdns",
        "counter_blacklist_asn",
        "counter_blacklist_usa",
    ]

    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("blacklist")

        for key in keys:
            if data.get(key) is None:
                data[key] = 0

        return data

    except:
        data = {}
        for key in keys:
            data[key] = 0
        return data
