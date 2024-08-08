from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["app"].bw_instances_utils.get_metrics("cors")
        return {
            "counter_failed_cors": {
                "value": data.get("counter_failed_cors", 0),
                "title": "CORS",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }

    except BaseException:
        print(format_exc(), flush=True)
        return {
            "counter_failed_cors": {"value": "unknown", "title": "CORS", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"},
            "error": format_exc(),
        }


def cors(**kwargs):
    pass
