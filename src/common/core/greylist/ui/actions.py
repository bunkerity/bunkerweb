def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("greylist")
        return {
            "counter_failed_greylist": {
                "value": data.get("counter_failed_greylist", 0),
                "title": "GREYLIST",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except:
        return {
            "counter_failed_greylist": {"value": "unknown", "title": "GREYLIST", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"}
        }


def greylist(**kwargs):
    pass
