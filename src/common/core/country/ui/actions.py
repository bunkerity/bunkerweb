def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("country")
        return {
            "counter_failed_country": {
                "value": data.get("counter_failed_country", 0),
                "title": "Country",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except:
        return {
            "counter_failed_country": {"value": "unknown", "title": "Country", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"}
        }


def country(**kwargs):
    pass
