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
    except:
        return {"counter_failed_challenges": {"value": "unknown", "title": "Challenge", "subtitle": "Failed", "subtitle_color": "info", "svg_color": "blue"}}


def antibot(**kwargs):
    pass
