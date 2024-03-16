def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("misc")

        return {
            "counter_failed_default": {
                "value": data.get("counter_failed_default", 0),
                "title": "DEFAULT SERVER DISABLED",
                "subtitle": "total",
                "subtitle_color": "info",
                "svg_color": "sky",
            },
            "counter_failed_method": {
                "value": data.get("counter_failed_method", 0),
                "title": "DISALLOWED METHODS",
                "subtitle": "count",
                "subtitle_color": "info",
                "svg_color": "lime",
            },
        }

    except:
        return {
            "counter_failed_default": {
                "value": "unknown",
                "title": "DEFAULT SERVER DISABLED",
                "subtitle": "total",
                "subtitle_color": "info",
                "svg_color": "sky",
            },
            "counter_failed_method": {"value": "unknown", "title": "DISALLOWED METHODS", "subtitle": "count", "subtitle_color": "info", "svg_color": "lime"},
        }


def misc(**kwargs):
    pass
