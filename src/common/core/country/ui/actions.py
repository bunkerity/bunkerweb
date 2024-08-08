from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["app"].bw_instances_utils.get_metrics("country")
        return {
            "counter_failed_country": {
                "value": data.get("counter_failed_country", 0),
                "title": "Country",
                "subtitle": "request blocked",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except BaseException:
        print(format_exc(), flush=True)
        return {
            "counter_failed_country": {"value": "unknown", "title": "Country", "subtitle": "request blocked", "subtitle_color": "error", "svg_color": "red"},
            "error": format_exc(),
        }


def country(**kwargs):
    pass
