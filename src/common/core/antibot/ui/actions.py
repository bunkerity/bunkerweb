from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["app"].bw_instances_utils.get_metrics("antibot")
        return {
            "counter_failed_challenges": {
                "value": data.get("counter_failed_challenges", 0),
                "title": "Challenge",
                "subtitle": "Failed",
                "subtitle_color": "error",
                "svg_color": "red",
            }
        }
    except BaseException:
        print(format_exc(), flush=True)
        return {
            "counter_failed_challenges": {"value": "unknown", "title": "Challenge", "subtitle": "Failed", "subtitle_color": "error", "svg_color": "red"},
            "error": format_exc(),
        }


def antibot(**kwargs):
    pass
