def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("cors")
        return {
            "counter_failed_cors": {
                "value": data.get("counter_failed_cors", 0),
                "title": "CORS",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }

    except:
        return {"counter_failed_cors": {"value": "unknown", "title": "CORS", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"}}


def cors(**kwargs):
    pass
