def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("whitelist")
        return {
            "counter_passed_whitelist": {
                "value": data.get("counter_passed_whitelist", 0),
                "title": "WHITELIST",
                "subtitle": "request passed",
                "subtitle_color": "success",
                "svg_color": "green",
            }
        }

    except:
        return {
            "counter_passed_whitelist": {
                "value": "unknown",
                "title": "WHITELIST",
                "subtitle": "request passed",
                "subtitle_color": "success",
                "svg_color": "green",
            }
        }


def whitelist(**kwargs):
    pass
