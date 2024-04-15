from traceback import format_exc


def pre_render(**kwargs):
    try:
        data = kwargs["app"].config["INSTANCES"].get_metrics("antibot")
        return {
            "counter_failed_challenges": {
                "value": data.get("counter_failed_challenges", 0),
                "title": "Challenge",
                "subtitle": "Failed",
                "subtitle_color": "info",
                "svg_color": "blue",
            }
        }
    except BaseException:
        print(format_exc(), flush=True)
        return {"counter_failed_challenges": {"value": "unknown", "title": "Challenge", "subtitle": "Failed", "subtitle_color": "info", "svg_color": "blue"}, "error" : format_exc()}


def antibot(**kwargs):
    pass
